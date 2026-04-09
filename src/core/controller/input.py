"""
Input handling logic for the Orchestrator Controller.

Builds the messages array, resolves provider, streams inference tokens,
handles tool calls and DB persistence.
"""
import logging
import json as _json
import time as _time
from typing import AsyncGenerator, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.memory import MemoryManager
    from src.core.config_manager import ConfigManager
    from src.services.providers import ProviderManager

logger = logging.getLogger(__name__)


class JotaInputMixin:

    async def handle_input(self, payload: dict) -> AsyncGenerator[str | dict, None]:
        """
        Main inference flow:
          1. Resolve provider + model for this conversation.
          2. Build messages array (system + history + user).
          3. Stream tokens from provider adapter.
          4. Handle tool calls: execute, save, re-infer.
          5. Persist assistant response to DB.
        """
        content = payload.get("content")
        conversation_id = payload.get("conversation_id")
        client_id = payload.get("client_id")
        stateless = payload.get("stateless", False)
        system_prompt_override = payload.get("system_prompt_override")

        if not conversation_id or not client_id:
            logger.error("Missing conversation_id or client_id in payload")
            yield " [Error: Internal Context Missing]"
            return

        logger.info(f"Controller processing input for conversation {conversation_id}")

        try:
            # 1. Resolve provider + model
            provider_id, model_id = await self._resolve_provider(
                conversation_id, client_id, stateless
            )
            adapter = self.provider_manager.get_adapter(provider_id)

            # 2. Build system prompt
            from src.core.tool_manager import tool_manager
            tool_instructions = tool_manager.get_system_prompt_addition(client_id=client_id)
            base_prompt = system_prompt_override or self.config_manager.config.system_prompt
            system_prompt = base_prompt
            if tool_instructions:
                system_prompt += "\n\n" + tool_instructions

            # 3. Build messages array
            messages = [{"role": "system", "content": system_prompt}]
            if not stateless:
                history = await self.memory_manager.get_conversation_messages(
                    conversation_id, client_id
                )
                messages.extend(history)
            messages.append({"role": "user", "content": content})

            infer_params = {"temp": 0.7}

            # 4. First inference pass
            tool_executed = False
            pre_tool_thinking: list[str] = []
            response_buffer: list[str] = []

            async for token in adapter.infer(messages, model_id, infer_params):
                if isinstance(token, dict) and token.get("type") == "tool_call":
                    tc_payload = token.get("payload", {})
                    tool_name = tc_payload.get("name")
                    tool_args = tc_payload.get("arguments", {})

                    # Save pre-tool thinking to DB (not shown to user)
                    if pre_tool_thinking and not stateless:
                        thinking_text = "".join(pre_tool_thinking)
                        await self.memory_manager.save_message(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=thinking_text,
                            client_id=client_id,
                            metadata={"model_id": model_id, "thinking": True},
                        )
                    pre_tool_thinking.clear()
                    response_buffer.clear()

                    yield {"type": "status", "content": f"Buscando información usando {tool_name}..."}

                    try:
                        start_t = _time.time()
                        result = await tool_manager.execute_tool(
                            tool_name, client_id=client_id, **tool_args
                        )
                        duration = f"{_time.time() - start_t:.2f}s"
                        result_str = result if isinstance(result, str) else _json.dumps(result)

                        if not stateless:
                            await self.memory_manager.save_message(
                                conversation_id=conversation_id,
                                role="tool",
                                content=result_str,
                                client_id=client_id,
                                metadata={"tool_name": tool_name, "execution_time": duration},
                            )
                        yield {"type": "status", "content": f"Búsqueda completada en {duration}. Generando respuesta..."}
                        tool_executed = True
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        if not stateless:
                            await self.memory_manager.save_message(
                                conversation_id=conversation_id,
                                role="tool",
                                content=f"Error executing tool {tool_name}: {e}",
                                client_id=client_id,
                                metadata={"tool_name": tool_name, "error": True},
                            )
                        yield {"type": "status", "content": f"Error al ejecutar {tool_name}: {e}"}
                        tool_executed = True
                else:
                    if not tool_executed:
                        pre_tool_thinking.append(token)
                        response_buffer.append(token)

            # Flush buffered thinking if no tool call happened
            if not tool_executed:
                for chunk in pre_tool_thinking:
                    yield chunk
                if not stateless and response_buffer:
                    full_text = "".join(response_buffer)
                    await self.memory_manager.save_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_text,
                        client_id=client_id,
                        metadata={"model_id": model_id},
                    )
                return

            # 5. Re-inference after tool execution
            yield {"type": "status", "content": "Analizando resultados..."}

            followup_messages = [{"role": "system", "content": system_prompt}]
            if not stateless:
                updated_history = await self.memory_manager.get_conversation_messages(
                    conversation_id, client_id
                )
                followup_messages.extend(updated_history)
            followup_messages.append({
                "role": "user",
                "content": self.config_manager.config.tool_followup_prompt,
            })

            final_buffer: list[str] = []
            async for token in adapter.infer(followup_messages, model_id, infer_params):
                if isinstance(token, dict) and token.get("type") == "tool_call":
                    logger.warning("Nested tool call attempted — ignoring.")
                else:
                    final_buffer.append(token)
                    yield token

            if not stateless and final_buffer:
                await self.memory_manager.save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content="".join(final_buffer),
                    client_id=client_id,
                    metadata={"model_id": model_id},
                )

            logger.info("Inference stream complete.")

        except Exception as e:
            logger.error(f"Error during inference flow: {e}")
            await self.memory_manager.mark_conversation_error(conversation_id, client_id)
            yield f" [Error: {str(e)}]"

    async def _resolve_provider(
        self,
        conversation_id: str,
        client_id,
        stateless: bool,
    ) -> tuple[str, str]:
        """
        Resolves (provider_id, model_id) with this priority:
          1. conversation.provider_id + conversation.model_id  (DB, highest priority)
          2. client_config.preferred_model_id + default provider
          3. Global default provider + default model
        """
        # 1. Conversation-level provider
        if not stateless:
            conv = await self.memory_manager.get_conversation(conversation_id, client_id)
            if conv and conv.get("provider_id") and conv.get("model_id"):
                return conv["provider_id"], conv["model_id"]

        # 2. Client preferred model
        client_config = await self.memory_manager.get_client_config(str(client_id))
        default_provider_id, default_model_id = self.provider_manager.get_default()
        if client_config and client_config.get("preferred_model_id"):
            return default_provider_id, client_config["preferred_model_id"]

        # 3. Global default
        return default_provider_id, default_model_id

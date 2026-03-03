import asyncio
import sys
from typing import Dict, Any, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.core.tool_manager import ToolManager, tool_manager


class MCPClientManager:
    """
    Manages connections to MCP (Model Context Protocol) servers and registers
    their available tools with the JotaOrchestrator ToolManager.
    """

    def __init__(self):
        self._sessions: Dict[str, ClientSession] = {}
        # Keep references to the stdio contexts to keep them alive
        self._stdio_contexts: Dict[str, Any] = {}

    async def connect_stdio_server(self, server_name: str, command: str, args: List[str] = None, env: Dict[str, str] = None) -> None:
        """
        Connects to an MCP server using standard input/output (stdio).
        """
        if server_name in self._sessions:
            print(f"Warning: Already connected to MCP server '{server_name}'.")
            return

        server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env
        )

        try:
            # We must manage the context managers properly in async code
            stdio_ctx = stdio_client(server_params)
            read, write = await stdio_ctx.__aenter__()
            self._stdio_contexts[server_name] = stdio_ctx
            
            session = ClientSession(read, write)
            await session.__aenter__()
            self._sessions[server_name] = session
            
            # Initialize the connection
            await session.initialize()
            print(f"Successfully connected to MCP server '{server_name}' via stdio.")

        except Exception as e:
            print(f"Failed to connect to MCP server '{server_name}': {e}", file=sys.stderr)
            # Cleanup on failure
            if server_name in self._stdio_contexts:
                try:
                    await self._stdio_contexts[server_name].__aexit__(None, None, None)
                except Exception:
                    pass
                del self._stdio_contexts[server_name]
            raise RuntimeError(f"Could not connect to MCP server {server_name}: {e}")


    async def register_mcp_tools(self, server_name: str, tm: ToolManager = tool_manager) -> None:
        """
        Queries the MCP server for available tools and registers wrapper functions
        in the provided ToolManager that proxy execution to the server.
        """
        if server_name not in self._sessions:
            raise ValueError(f"Not connected to MCP server '{server_name}'.")

        session = self._sessions[server_name]
        
        try:
            tools_response = await session.list_tools()
        except Exception as e:
            print(f"Failed to list tools from MCP server '{server_name}': {e}", file=sys.stderr)
            raise RuntimeError(f"Could not list tools from {server_name}: {e}")

        for mcp_tool in tools_response.tools:
            # Reconstruct the JSON schema format expected by the Orchestrator
            tool_name = f"{server_name}_{mcp_tool.name}"
            description = mcp_tool.description or f"MCP tool from {server_name}"
            # The MCP tool inputSchema should already be a JSON schema object
            input_schema = mcp_tool.inputSchema
            
            # Create a proxy async function for the ToolManager wrapper
            # We use a closure factory to capture the values properly
            proxy_func = self._create_proxy_function(server_name, mcp_tool.name, tool_name, description)
            
            # Register manually with the ToolManager to bypass the @tool decorator's inspection
            # since the function signature doesn't match the dynamic schema
            tm._tools[tool_name] = proxy_func
            tm._schemas[tool_name] = {
                "name": tool_name,
                "description": description,
                "parameters": input_schema
            }
            print(f"Registered MCP tool: {tool_name}")

    def _create_proxy_function(self, server_name: str, mcp_tool_name: str, registered_name: str, description: str):
        """Creates a proxy function that calls the MCP server tool."""
        
        async def proxy_wrapper(**kwargs):
            if server_name not in self._sessions:
                raise RuntimeError(f"Connection to MCP server '{server_name}' was lost.")
            
            session = self._sessions[server_name]
            try:
                # kwargs represent the tool arguments required by the input_schema
                result = await session.call_tool(mcp_tool_name, arguments=kwargs)
                
                # Format the result nicely (MCP tools return specific content types)
                formatted_result = []
                for content in result.content:
                    if content.type == "text":
                        formatted_result.append(content.text)
                    elif content.type == "image":
                        formatted_result.append(f"[Image Data: {content.mimeType}]") # Basic placeholder
                    else:
                         formatted_result.append(str(content))
                
                return "\n".join(formatted_result) if formatted_result else "Tool executed successfully (no content returned)."
                
            except Exception as e:
                raise RuntimeError(f"Execution of MCP tool '{registered_name}' failed: {e}")
                
        # Give it a helpful name internally and docstring
        proxy_wrapper.__name__ = registered_name
        proxy_wrapper.__doc__ = description
        return proxy_wrapper

    async def close_all(self):
        """Closes all active MCP sessions."""
        for name, session in list(self._sessions.items()):
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                print(f"Error closing session for '{name}': {e}", file=sys.stderr)
            
        for name, ctx in list(self._stdio_contexts.items()):
            try:
                await ctx.__aexit__(None, None, None)
            except Exception as e:
                print(f"Error closing context for '{name}': {e}", file=sys.stderr)
                
        self._sessions.clear()
        self._stdio_contexts.clear()

# Global instance
mcp_manager = MCPClientManager()

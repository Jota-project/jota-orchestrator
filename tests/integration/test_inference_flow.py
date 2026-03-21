import pytest
import asyncio
import pytest_asyncio
from src.services.inference import InferenceClient
from tests.integration.mock_server import MockInferenceServer

@pytest_asyncio.fixture(scope="function")
async def mock_server():
    server = MockInferenceServer(port=8766)
    await server.start()
    yield server
    await server.stop()

@pytest.mark.asyncio
async def test_full_inference_flow(mock_server, mock_memory_manager):
    """
    Test the complete flow:
    Connect -> Create Session -> Infer -> Receive Tokens
    """
    client = InferenceClient(
        url="ws://localhost:8766",
        memory_manager=mock_memory_manager
    )

    try:
        await client.connect()
        connected = await client.verify_connection(timeout=5.0)
        assert connected

        session_id = await client.create_session()
        assert session_id == "mock_session_123"

        prompt = "Hello"
        received_tokens = []

        async for token in client.infer(
            session_id, prompt,
            conversation_id="conv_test_1",
            user_id="user_test_1"
        ):
            received_tokens.append(token)

        assert len(received_tokens) > 0
        assert "".join(received_tokens) == "This is a mock response."

    finally:
        await client.invoke_shutdown()

@pytest.mark.asyncio
async def test_concurrent_sessions(mock_server, mock_memory_manager):
    """
    Test multiple sequential inference sessions (serialized by session lock).
    """
    client = InferenceClient(
        url="ws://localhost:8766",
        memory_manager=mock_memory_manager
    )

    await client.connect()
    connected = await client.verify_connection(timeout=5.0)
    assert connected

    async def run_session(user_id):
        session_id = await client.create_session()
        tokens = []
        async for token in client.infer(
            session_id, "prompt",
            conversation_id=f"conv_{user_id}",
            user_id=user_id
        ):
            tokens.append(token)
        return "".join(tokens)

    results = await asyncio.gather(
        run_session("user_1"),
        run_session("user_2"),
        run_session("user_3")
    )

    for res in results:
        assert res == "This is a mock response."

    await client.invoke_shutdown()

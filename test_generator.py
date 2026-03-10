import asyncio
import sys
import os

# Configure sys.path so we can import src
sys.path.append(os.path.dirname(__file__))

from src.api.quick import _quick_stream_generator
from src.core.services import inference_client

async def _mock_infer(*args, **kwargs):
    yield "¡"
    await asyncio.sleep(0.1)
    yield "Hola"
    yield {
        "type": "tool_call",
        "payload": {
            "name": "get_current_time",
            "arguments": {}
        }
    }
    yield "Aquí tienes tu respuesta."

# Bypass inference client remote behavior completely
inference_client.infer = _mock_infer

async def mock_set_context(*args, **kwargs): pass
inference_client.set_context = mock_set_context

async def mock_close_session(*args, **kwargs): pass
inference_client.close_session = mock_close_session

async def main():
    print("Starting stream generator...")
    async for item in _quick_stream_generator(
        client_id=1,
        user_id="test",
        session_id="mock_sess",
        text="hola",
        model_id=None
    ):
        print("YIELDED:", repr(item))
    print("Finished!")

if __name__ == "__main__":
    asyncio.run(main())

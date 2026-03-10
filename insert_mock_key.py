import asyncio
from src.core.memory import MemoryManager
from src.core.config import settings

async def main():
    mm = MemoryManager()
    
    # We will use Orchestrator privileges to create a new client
    service_headers = {
         **mm.base_headers,
         "X-API-Key": settings.ORCHESTRATOR_API_KEY,
    }
    
    payload = {
        "name": "Test Quick Client",
        "client_type": "quick"
    }
    
    try:
        response = await mm.client.post(f"{mm.base_url}/auth/clients", json=payload, headers=service_headers)
        if response.status_code in (200, 201):
            client_data = response.json()
            print(f"Created QUICK client. Key: {client_data.get('api_key')}")
        else:
            print(f"Failed to create client: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mm.close()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from src.core.memory import MemoryManager
from src.core.config import settings

async def main():
    mm = MemoryManager()
    
    # We will use Orchestrator privileges to query the DB for clients
    service_headers = {
         **mm.base_headers,
         "X-API-Key": settings.ORCHESTRATOR_API_KEY,
    }
    
    # The actual endpoint might vary, assuming a standard REST pattern for now
    try:
        response = await mm.client.get(f"{mm.base_url}/auth/clients", headers=service_headers)
        if response.status_code == 200:
            clients = response.json()
            for c in clients:
                if c.get("client_type") == "quick":
                    print(f"Found QUICK client key: {c.get('api_key')}")
                    return
            print("No QUICK client found. Showing all keys:")
            for c in clients:
                print(f"Type: {c.get('client_type')}, Key: {c.get('api_key')}")
        else:
            print(f"Failed to fetch clients: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await mm.close()

if __name__ == "__main__":
    asyncio.run(main())

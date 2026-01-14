
import asyncio
from qdrant_client import AsyncQdrantClient, QdrantClient

async def test_async_migrate():
    client = AsyncQdrantClient(location=":memory:")
    # We need a destination.
    # AsyncQdrantClient migrate might expect a Sync destination or Async destination?
    # Let's try passing a sync client as destination.
    dest_client = QdrantClient(location=":memory:")
    
    try:
        # Check if migrate is awaitable
        res = client.migrate(dest_client)
        if asyncio.iscoroutine(res):
            print("migrate IS a coroutine")
            await res
        else:
            print("migrate IS NOT a coroutine")
            
    except Exception as e:
        print(f"Error: {repr(e)}")

if __name__ == "__main__":
    asyncio.run(test_async_migrate())

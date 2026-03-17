import asyncio
import time
from uuid import uuid4

# Setup test
ids = [uuid4().hex for _ in range(50000)]

async def batching():
    call_count = 0
    start = time.time()
    for i in range(0, len(ids), 1000):
        batch = ids[i : i + 1000]
        # Simulate network delay for API call
        await asyncio.sleep(0.005)
        call_count += 1
    end = time.time()
    print(f"Batching time: {end - start:.4f}s")
    print(f"Batching calls: {call_count}")

async def single():
    call_count = 0
    start = time.time()
    # Emulate the optimized code
    await asyncio.sleep(0.005)
    call_count += 1
    end = time.time()

    print(f"Single time: {end - start:.4f}s")
    print(f"Single calls: {call_count}")

async def main():
    await batching()
    await single()

if __name__ == "__main__":
    asyncio.run(main())

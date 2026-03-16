import asyncio
from codeweaver.core import Container

async def main():
    container = Container()
    try:
        from typing import Union
        result = await container.resolve(Union[None])
        print("Success:", result)
    except Exception as e:
        print("Error:", type(e), e)

asyncio.run(main())

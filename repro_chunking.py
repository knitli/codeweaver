import sys

from pathlib import Path


# Add src to PYTHONPATH
sys.path.insert(0, str(Path("src").absolute()))

from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.metadata import ChunkKind, ExtKind
from codeweaver.engine.chunking_service import ChunkingService


async def repro() -> None:
    from codeweaver.di import get_container

    container = get_container()

    print("Resolving ChunkingService via container...")
    try:
        service = await container.resolve(ChunkingService)
        print(f"Resolved service: {service}")
        print(f"Service tokenizer: {service.tokenizer}")
    except Exception as e:
        print(f"Resolution failed: {e}")
        import traceback

        traceback.print_exc()
        return

    # Create a dummy file to chunk
    from codeweaver.core import uuid7

    temp_file = Path("repro_test.py")
    temp_file.write_text("def hello():\n    print('world')\n")

    file_obj = DiscoveredFile(
        path=Path("repro_test.py"),
        absolute_path=temp_file.absolute(),
        source_id=uuid7(),
        ext_kind=ExtKind.from_language(SemanticSearchLanguage.PYTHON, ChunkKind.CODE),
    )

    print(f"Attempting to chunk {temp_file}...")
    try:
        results = list(service.chunk_files([file_obj]))
        print(f"Chunking results: {results}")
    except Exception as e:
        print(f"Repro caught exception: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if temp_file.exists():
            temp_file.unlink()


if __name__ == "__main__":
    import asyncio

    asyncio.run(repro())

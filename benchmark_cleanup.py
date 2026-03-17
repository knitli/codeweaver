import asyncio
from pathlib import Path
import time
from unittest.mock import MagicMock
from codeweaver.core import set_relative_path

from codeweaver.engine.services.indexing_service import IndexingService

class SlowVectorStore:
    async def delete_by_file(self, path: Path) -> None:
        await asyncio.sleep(0.01) # simulate 10ms network latency

    async def delete_by_files(self, paths: list[Path]) -> None:
        await asyncio.sleep(0.01) # simulate 10ms network latency for batch

async def _old_cleanup_deleted_files(self) -> None:
    for path in self._deleted_files:
        if self._vector_store:
            await self._vector_store.delete_by_file(path)
        rel_path = set_relative_path(path, base_path=self._project_path)
        if rel_path and self._file_manifest:
            async with self._manifest_lock:
                self._file_manifest.remove_file(rel_path)

    self._deleted_files = []

async def _new_cleanup_deleted_files(self) -> None:
    if self._vector_store and self._deleted_files:
        await self._vector_store.delete_by_files(self._deleted_files)

    for path in self._deleted_files:
        rel_path = set_relative_path(path, base_path=self._project_path)
        if rel_path and self._file_manifest:
            async with self._manifest_lock:
                self._file_manifest.remove_file(rel_path)

    self._deleted_files = []


async def main():
    service1 = IndexingService.__new__(IndexingService)
    service1._vector_store = SlowVectorStore()
    service1._deleted_files = [Path(f"file_{i}.py") for i in range(100)]
    service1._project_path = Path("/tmp")
    service1._file_manifest = MagicMock()
    service1._manifest_lock = asyncio.Lock()

    start_time = time.time()
    await _old_cleanup_deleted_files(service1)
    end_time = time.time()

    print(f"Old Cleanup took: {end_time - start_time:.4f} seconds")

    service2 = IndexingService.__new__(IndexingService)
    service2._vector_store = SlowVectorStore()
    service2._deleted_files = [Path(f"file_{i}.py") for i in range(100)]
    service2._project_path = Path("/tmp")
    service2._file_manifest = MagicMock()
    service2._manifest_lock = asyncio.Lock()

    start_time = time.time()
    await _new_cleanup_deleted_files(service2)
    end_time = time.time()

    print(f"New Cleanup took: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(main())

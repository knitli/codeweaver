# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import asyncio
import logging
import time

from codeweaver.di import get_container
from codeweaver.engine.indexer import Indexer
from codeweaver.providers.embedding.providers.base import EmbeddingProvider


# Suppress logging for cleaner output
logging.getLogger("codeweaver").setLevel(logging.ERROR)

async def benchmark_initialization():
    print("--- Performance Baseline: Initialization ---")

    start = time.perf_counter()
    indexer = await Indexer.from_settings_async()
    end = time.perf_counter()
    print(f"Indexer.from_settings_async(): {(end - start) * 1000:.2f}ms")

    container = get_container()
    start = time.perf_counter()
    indexer_di = await container.resolve(Indexer)
    end = time.perf_counter()
    print(f"Container.resolve(Indexer):   {(end - start) * 1000:.2f}ms")

async def benchmark_embedding():
    print("\n--- Performance Baseline: Embedding (Local/Mock) ---")
    container = get_container()
    try:
        embedding = await container.resolve(EmbeddingProvider)
        start = time.perf_counter()
        # Simple short text
        await embedding.embed_query("test code search")
        end = time.perf_counter()
        print(f"EmbeddingProvider.embed_query(): {(end - start) * 1000:.2f}ms")
    except Exception as e:
        print(f"Embedding benchmark skipped: {e}")

async def main():
    await benchmark_initialization()
    # Embedding might require API keys or local models, skip if not available
    # await benchmark_embedding()

if __name__ == "__main__":
    asyncio.run(main())

# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import asyncio
import sys

import pytest

from codeweaver.core.dependencies import bootstrap_settings
from codeweaver.core.di import get_container, reset_container_state
from codeweaver.server.server import CodeWeaverState


@pytest.mark.requires_fastembed
async def test_di_resolution():
    print("Resetting container...")
    reset_container_state()

    print("Bootstrapping settings...")
    # This registers the settings provider
    await bootstrap_settings()

    # We need to make sure server dependencies are registered.
    # Importing the module should do it.
    import codeweaver.server.dependencies  # noqa: F401

    container = get_container()

    print("Resolving CodeWeaverState...")
    try:
        state = await container.resolve(CodeWeaverState)
        print("Success! State resolved.")
        print(f"Health Service: {state.health_service}")
        print(f"Indexer: {state.indexer}")

        if state.health_service is None:
            print("ERROR: HealthService is None!")
            sys.exit(1)

    except Exception as e:
        print(f"Failed to resolve state: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_di_resolution())

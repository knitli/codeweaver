# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from mcp.shared.session import ProgressFnT

logger = ...
type ProgressHandler = ProgressFnT

async def default_progress_handler(
    progress: float, total: float | None, message: str | None
) -> None:
    ...

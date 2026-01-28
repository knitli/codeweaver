# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Failover configuration settings for CodeWeaver."""

from __future__ import annotations

import os

from typing import TYPE_CHECKING, Annotated, NotRequired, TypedDict

from pydantic import Field, PositiveInt

from codeweaver.core.di import INJECTED
from codeweaver.core.types import BasedModel
from codeweaver.providers import ProviderSettingsDep


if TYPE_CHECKING:
    from codeweaver.providers.config.providers import ProviderSettings


MAX_RAM_MB = 2048

FIVE_MINUTES_IN_SECONDS = 300


def _get_provider_settings(settings: ProviderSettingsDep = INJECTED) -> ProviderSettings:
    return settings


class FailoverSettings(BasedModel):
    """Settings for vector store failover and service resilience.

    CodeWeaver's backup system is intelligent in that it only activates if you may need it. It is automatically disabled if:
      - Your configured embedding provider is local.
      - Your vector store provider is local.

    ## Features

    - **Reranking**. Automatically injects a backup local reranking model, which is simply accessed at query time if the primary model is unavailable. This is *always* on.
    - **Backup Vectors**. If your embedding provider is remote, and your vector store is local, the system will add a backup vector to each stored point using the backup local model, ensuring that queries can still be served even if the primary embedding provider is unavailable. The system will automatically manage the synchronization of these backup vectors (it simply checks if all expected vectors are on all points and adds any missing ones).
    - **Write-Ahead Logging (WAL)**. If your embedding provider is remote, it uses write-ahead-logging (WAL) to store a local copy of the vectors each time it writes to the primary store. This uses Qdrant's built-in ability to use vectors stored in a directory using RocksDB. When the primary returns, the system will reconcile the local WAL with the primary store to ensure consistency.
    - **Resolves Asymmetric Models**. If your embedding model is capable of asymmetric retrieval (currently only `voyage-4` series models), the system will automatically switch from your primary to a locally compatible model (for voyage-4 series, `voyage-4-nano`). Since embeddings are compatible across these models, you can continue to retrieve and generate new embeddings without interruption, albeit at a slight loss of accuracy for generated embeddings assuming your primary is `voyage-4-large` (about 6 points on RTEB-Code from 86 to 80, which is still better than any other currently available alternative). The advantage here is that you don't need to generate and keep a third set of embeddings for the local model (the second being your sparse embeddings).
    """

    disable_failover: Annotated[
        bool,
        Field(
            description="Whether to disable automatic failover to backup vector store. If true, the system will not switch to the backup store on primary failure or keep it ready for failover."
        ),
    ] = os.environ.get("CODEWEAVER_DISABLE_BACKUP_SYSTEM", "0") in ("1", "true", "True")

    backup_sync: Annotated[
        PositiveInt,
        Field(description="PositiveInterval in seconds for syncing primary state to backup"),
    ] = FIVE_MINUTES_IN_SECONDS

    recovery_window_sec: Annotated[
        PositiveInt,
        Field(description="Seconds to wait after primary becomes healthy before restoring"),
    ] = FIVE_MINUTES_IN_SECONDS

    max_memory_mb: Annotated[
        PositiveInt,
        Field(
            description="Maximum memory usage in MB for backup store (only applies when using in-memory backup)"
        ),
    ] = MAX_RAM_MB

    def _telemetry_keys(self) -> None:
        """No telemetry keys for failover settings."""
        return

    @property
    def is_disabled(self) -> bool:
        """Check if failover is disabled."""
        return self._resolve_status_from_config()

    def _resolve_status_from_config(self, settings: ProviderSettings | None = None) -> bool:
        """Resolve the failover status from the current configuration."""
        if self.disable_failover:
            return True
        settings = settings or _get_provider_settings()
        return settings.embedding[0].is_local if settings.embedding else False


class FailoverSettingsDict(TypedDict, total=False):
    """TypedDict for failover settings."""

    disable_failover: NotRequired[bool]
    backup_sync: NotRequired[PositiveInt]
    auto_restore: NotRequired[bool]
    recovery_window_sec: NotRequired[PositiveInt]
    max_memory_mb: NotRequired[PositiveInt]


DefaultFailoverSettings: FailoverSettingsDict = FailoverSettings().model_dump()


__all__ = ("DefaultFailoverSettings", "FailoverSettings", "FailoverSettingsDict")

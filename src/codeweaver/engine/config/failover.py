# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Failover configuration settings for CodeWeaver."""

from __future__ import annotations

import functools
import os

from typing import TYPE_CHECKING, Annotated, NotRequired, TypedDict

from pydantic import Field, PositiveInt

from codeweaver.core.types import BasedModel


if TYPE_CHECKING:
    from codeweaver.engine.config.failover_detector import FailoverDetector


MAX_RAM_MB = 2048

FIVE_MINUTES_IN_SECONDS = 300


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

    reconciliation_interval_cycles: Annotated[
        PositiveInt,
        Field(
            description="Number of backup sync cycles between vector reconciliation runs. "
            "Reconciliation ensures all points have backup vectors. "
            "Default is 2 cycles (10 minutes with 5-minute backup_sync)."
        ),
    ] = 2

    reconciliation_batch_size: Annotated[
        PositiveInt,
        Field(description="Number of points to process per batch during reconciliation"),
    ] = 100

    reconciliation_detection_limit: Annotated[
        PositiveInt | None,
        Field(
            description="Maximum number of missing vectors to detect per reconciliation run. "
            "None means detect all missing vectors. Use a limit to avoid long detection times."
        ),
    ] = None

    # Snapshot configuration
    snapshot_interval_cycles: Annotated[
        PositiveInt,
        Field(
            description="Number of backup sync cycles between snapshot creation runs. "
            "Default is 1 cycle (5 minutes with 5-minute backup_sync)."
        ),
    ] = 1

    snapshot_retention_count: Annotated[
        PositiveInt,
        Field(
            description="Number of snapshots to retain. Older snapshots are automatically deleted. "
            "Default is 12 (1 hour of snapshots with 5-minute intervals)."
        ),
    ] = 12

    snapshot_storage_path: Annotated[
        str | None,
        Field(
            description="Path for local snapshot storage. If None, uses default path in user state directory. "
            "For cloud storage, configure through Qdrant settings."
        ),
    ] = None

    # WAL configuration for backup system
    wal_capacity_mb: Annotated[
        PositiveInt,
        Field(
            description="Write-ahead log capacity in MB. Controls maximum WAL size before rotation. "
            "Default is 256 MB. Increase for high-throughput scenarios."
        ),
    ] = 256

    wal_segments_ahead: Annotated[
        PositiveInt,
        Field(
            description="Number of WAL segments to keep ahead for recovery. "
            "Default is 2. Higher values provide more recovery history."
        ),
    ] = 2

    wal_retain_closed: Annotated[
        bool,
        Field(
            description="Whether to retain closed WAL segments for point-in-time recovery. "
            "Default is True to support snapshot restoration."
        ),
    ] = True

    def _telemetry_keys(self) -> None:
        """No telemetry keys for failover settings."""
        return

    @property
    def is_disabled(self) -> bool:
        """Check if failover is explicitly disabled.

        Note: This only checks the explicit disable_failover flag. For automatic
        detection based on provider configuration, callers should use
        _resolve_status_from_config() with a FailoverDetector instance.

        Returns:
            True if failover is explicitly disabled via disable_failover flag.
        """
        return self.disable_failover

    def _resolve_status_from_config(self, detector: FailoverDetector | None = None) -> bool:
        """Resolve the failover status from the current configuration.

        Args:
            detector: Optional detector to check if failover should be disabled.
                     If None, failover remains enabled (unless explicitly disabled).

        Returns:
            True if failover is disabled, False if enabled.
        """
        if self.disable_failover:
            return True
        if detector is None:
            return False
        return detector.should_disable_failover()


class FailoverSettingsDict(TypedDict, total=False):
    """TypedDict for failover settings."""

    disable_failover: NotRequired[bool]
    backup_sync: NotRequired[PositiveInt]
    auto_restore: NotRequired[bool]
    recovery_window_sec: NotRequired[PositiveInt]
    max_memory_mb: NotRequired[PositiveInt]
    reconciliation_interval_cycles: NotRequired[PositiveInt]
    reconciliation_batch_size: NotRequired[PositiveInt]
    reconciliation_detection_limit: NotRequired[PositiveInt | None]
    snapshot_interval_cycles: NotRequired[PositiveInt]
    snapshot_retention_count: NotRequired[PositiveInt]
    snapshot_storage_path: NotRequired[str | None]
    wal_capacity_mb: NotRequired[PositiveInt]
    wal_segments_ahead: NotRequired[PositiveInt]
    wal_retain_closed: NotRequired[bool]


@functools.cache
def get_default_failover_settings() -> FailoverSettingsDict:
    """Get default failover settings (cached lazy initialization).

    This function lazily initializes default failover settings only when first
    accessed, avoiding the circular import issue from module-level instantiation.

    Returns:
        Dictionary containing default failover settings.
    """
    return FailoverSettings().model_dump()


# Backward compatibility: Use function as constant
# This defers initialization until first access
DefaultFailoverSettings = get_default_failover_settings


__all__ = (
    "DefaultFailoverSettings",
    "FailoverSettings",
    "FailoverSettingsDict",
    "get_default_failover_settings",
)

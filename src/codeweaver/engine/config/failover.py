# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Failover configuration settings for CodeWeaver."""

from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from pydantic import Field, PositiveInt

from codeweaver.core import BasedModel


MAX_RAM_MB = 2048


class FailoverSettings(BasedModel):
    """Settings for vector store failover and service resilience.

    CodeWeaver's failover system uses the lightest weight models possible to create a backup vector store that can take over in the case of primary store failure -- usually because you are offline or have a poor connection to a cloud provider. By default, if you are using an on-system Qdrant instance as your primary vector store, CodeWeaver will create a second backup collection in that store to use as a failover (using local models for embeddings). If you are using qdrant cloud, then the backup is in-memory only but persists to disk between sessions.

    CodeWeaver creates this secondary backup automatically when your system is idle and keeps it up to date at regular PositiveIntervals. If one of your primary embedding or vector store providers become unreachable, CodeWeaver will automatically switch to the backup store to maPositiveIntain service continuity. When the primary store becomes reachable again, CodeWeaver can automatically restore it as the primary store after a short delay. (We switch on embedding failures because we don't want codeweaver to *ever* become stale -- even if the vector store is reachable, if we can't get new embeddings then the system can't learn new information.)

    When the primary returns to health, CodeWeaver will wait until the main providers are reachable *and caught up with changes from while they were offline* before switching back. This ensures that you don't lose any data or context during failover events.

    We designed the backup system to be very lightweight so that it can run on most systems without significant resource overhead. However, if you are running on a very constrained system or have specific requirements, you can adjust the settings below to better suit your needs. You may also want to disable the failover system if you are using all local providers as your primary providers.

    Importantly, while the system is lightweight, it's still extremely capable -- our backup is more robust than most search tools' primary systems. It maPositiveIntains full hybrid multivector search and reranking support, ensuring that your search experience remains seamless even during failover events.
    """

    disable_failover: Annotated[
        bool,
        Field(
            description="Whether to disable automatic failover to backup vector store. If true, the system will not switch to the backup store on primary failure or keep it ready for failover."
        ),
    ] = False

    backup_sync: Annotated[
        PositiveInt,
        Field(description="PositiveInterval in seconds for syncing primary state to backup"),
    ] = 300

    auto_restore: Annotated[
        bool,
        Field(
            description="Whether to automatically restore to primary store when it becomes healthy"
        ),
    ] = True

    restore_delay: Annotated[
        PositiveInt,
        Field(description="Seconds to wait after primary becomes healthy before restoring"),
    ] = 60

    max_memory_mb: Annotated[
        PositiveInt,
        Field(
            description="Maximum memory usage in MB for backup store (only applies when using in-memory backup)"
        ),
    ] = MAX_RAM_MB


class FailoverSettingsDict(TypedDict, total=False):
    """TypedDict for failover settings."""

    disable_failover: NotRequired[bool]
    backup_sync: NotRequired[PositiveInt]
    auto_restore: NotRequired[bool]
    restore_delay: NotRequired[PositiveInt]
    max_memory_mb: NotRequired[PositiveInt]


DefaultFailoverSettings: FailoverSettingsDict = FailoverSettings().model_dump()


__all__ = ("DefaultFailoverSettings", "FailoverSettings", "FailoverSettingsDict")

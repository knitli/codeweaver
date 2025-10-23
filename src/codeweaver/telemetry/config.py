# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Telemetry configuration settings.

Configuration sources (priority order):
1. Explicit config file setting (highest priority)
2. Environment variable
3. Install variant default

Environment Variables:
    CODEWEAVER_TELEMETRY_ENABLED: Enable/disable telemetry (default: true)
    CODEWEAVER_POSTHOG_API_KEY: PostHog API key
    CODEWEAVER_POSTHOG_HOST: PostHog host (default: https://app.posthog.com)
    CODEWEAVER_BATCH_SIZE: Event batch size (default: 10)
    CODEWEAVER_BATCH_INTERVAL_SECONDS: Batch interval (default: 60)
"""

from __future__ import annotations

from functools import cache
from typing import Annotated

from pydantic import Field, HttpUrl, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelemetrySettings(BaseSettings):
    """Telemetry configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="CODEWEAVER_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telemetry_enabled: Annotated[
        bool,
        Field(
            default=True,
            description="Enable or disable telemetry collection. Set to False to opt out.",
        ),
    ]

    posthog_api_key: Annotated[
        str | None,
        Field(
            default=None,
            description="PostHog API key. Required if telemetry is enabled.",
        ),
    ]

    posthog_host: Annotated[
        str,
        Field(
            default="https://app.posthog.com",
            description="PostHog host URL for telemetry events.",
        ),
    ]

    batch_size: Annotated[
        PositiveInt,
        Field(
            default=10,
            description="Number of events to batch before sending to PostHog.",
        ),
    ]

    batch_interval_seconds: Annotated[
        PositiveInt,
        Field(
            default=60,
            description="Maximum time in seconds to wait before sending batched events.",
        ),
    ]

    strict_privacy_mode: Annotated[
        bool,
        Field(
            default=True,
            description="Enable extra privacy validation checks on all telemetry events.",
        ),
    ]

    @property
    def is_configured(self) -> bool:
        """Check if telemetry is properly configured."""
        return self.telemetry_enabled and self.posthog_api_key is not None


@cache
def get_telemetry_settings() -> TelemetrySettings:
    """Get cached telemetry settings instance."""
    return TelemetrySettings()


__all__ = (
    "TelemetrySettings",
    "get_telemetry_settings",
)

# sourcery skip: name-type-suffix
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
PostHog telemetry client wrapper.

Provides a privacy-aware wrapper around the PostHog Python client with:
- Automatic privacy filtering
- Error handling (telemetry never crashes the application)
- Easy configuration and opt-out
- Event batching and throttling
"""

from __future__ import annotations

import logging

from functools import cache
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self


if TYPE_CHECKING:
    from posthog import Posthog

from codeweaver.telemetry.config import get_telemetry_settings


logger = logging.getLogger(__name__)


class PostHogClient:
    """
    Privacy-aware PostHog client wrapper.

    Handles telemetry event sending with automatic privacy filtering,
    error handling, and configuration management.

    Example:
        >>> client = PostHogClient.from_settings()
        >>> if client.enabled:
        ...     client.capture("session_summary", {"searches": 10})
    """

    # ---------------------------------------------------------------------------
    #!         THIS IS NOT AN API_KEY!! This key is a write-only project key
    #!         safe to include in public repositories. It cannot be used to
    #!         read data or access CodeWeaver's PostHog project.
    # ---------------------------------------------------------------------------
    def __init__(
        self,
        api_key: str | None = None,
        host: str = "https://app.posthog.com",
        *,
        enabled: bool = True,
        strict_privacy_mode: bool = True,
    ):
        """
        Initialize PostHog client.

        Args:
            api_key: PostHog project key (required if enabled)
            host: PostHog host URL
            enabled: Enable telemetry sending
            strict_privacy_mode: Enable strict privacy validation
        """
        import os

        # Prefer environment variable, fallback to hardcoded key if not provided
        if api_key is None:
            api_key = os.environ.get(
                "CODEWEAVER_POSTHOG_API_KEY", "phc_XKWSirBXZdxYEYRl98cJQzqvTcvQ7U1KWZYygLghhJg"
            )

        self.enabled = enabled and api_key is not None
        self.logger = logging.getLogger(__name__)
        self.privacy_filter = PrivacyFilter(strict_mode=strict_privacy_mode)

        self._client: Posthog | None = None

        if self.enabled and api_key:
            try:
                from posthog import Posthog

                self._client = Posthog(
                    project_api_key=api_key,
                    host=host,
                    # Disable debug mode in production
                    debug=False,
                )
                self.logger.info("PostHog telemetry client initialized")
            except ImportError:
                self.logger.warning(
                    "PostHog package not installed, telemetry disabled. "
                    "Install with: uv pip install 'codeweaver-mcp[recommended]'"  # type: ignore
                )
                self.enabled = False
                self._client = None
            except Exception:
                self.logger.exception("Failed to initialize PostHog client")
                self.enabled = False
                self._client = None
        else:
            self.logger.info("Telemetry disabled by configuration")

    @classmethod
    def from_settings(cls) -> PostHogClient:
        """
        Create PostHog client from telemetry settings.

        Returns:
            Configured PostHog client instance
        """
        settings = get_telemetry_settings()

        return cls(
            api_key=settings.posthog_api_key,
            host=settings.posthog_host,
            enabled=settings.telemetry_enabled,
            strict_privacy_mode=settings.strict_privacy_mode,
        )

    def capture(
        self, event: str, properties: dict[str, Any], *, distinct_id: str = "anonymous"
    ) -> None:
        """
        Send event to PostHog with privacy filtering.

        Args:
            event: Event name
            properties: Event properties dictionary
            distinct_id: User identifier (default: "anonymous" for privacy)

        Note:
            This method never raises exceptions. All errors are logged
            but do not affect application execution.
        """
        if not self.enabled or not self._client:
            self.logger.debug("Telemetry disabled, skipping event: %s", event)
            return

        try:
            # Validate event passes privacy requirements
            event_dict = {"event": event, "properties": properties}
            if not self.privacy_filter.validate_event(event_dict):
                self.logger.warning(
                    "Event '%s' failed privacy validation, not sending. "
                    "This may indicate a bug in event construction.",  # type: ignore
                    event,
                )
                return

            # Filter properties for extra safety
            filtered_properties = self.privacy_filter.filter_event(properties)

            # Send to PostHog
            _ = self._client.capture(
                distinct_id=distinct_id, event=event, properties=filtered_properties
            )

            self.logger.debug("Telemetry event sent: %s", event)

        except Exception:
            # Never fail application due to telemetry
            # Just log and continue
            self.logger.exception("Failed to send telemetry event '%s'", event)

    def capture_from_event(self, event_obj: Any) -> None:
        """
        Send event from a TelemetryEvent object.

        Args:
            event_obj: Object implementing TelemetryEvent protocol
        """
        try:
            event_name, properties = event_obj.to_posthog_event()
            self.capture(event_name, properties)
        except Exception:
            self.logger.exception("Failed to capture event from object")

    def shutdown(self) -> None:
        """
        Flush pending events and close client.

        Should be called at application shutdown to ensure all events
        are sent before exit.
        """
        if self._client:
            try:
                self._client.flush()
                self.logger.info("PostHog client shut down successfully")
            except Exception:
                self.logger.exception("Error during PostHog client shutdown")

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit with automatic shutdown."""
        self.shutdown()


@cache
def get_telemetry_client() -> PostHogClient:
    """
    Get singleton telemetry client instance.

    Returns:
        Cached PostHog client configured from settings
    """
    return PostHogClient.from_settings()


__all__ = ("PostHogClient", "get_telemetry_client")

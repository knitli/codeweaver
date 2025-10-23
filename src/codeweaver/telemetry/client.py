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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from posthog import Posthog

from codeweaver.telemetry.config import get_telemetry_settings
from codeweaver.telemetry.privacy import PrivacyFilter

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
            api_key: PostHog API key (required if enabled)
            host: PostHog host URL
            enabled: Enable telemetry sending
            strict_privacy_mode: Enable strict privacy validation
        """
        self.enabled = enabled and api_key is not None
        self.logger = logging.getLogger(__name__)
        self.privacy_filter = PrivacyFilter(strict_mode=strict_privacy_mode)

        self._client: Posthog | None = None

        if self.enabled:
            try:
                from posthog import Posthog

                self._client = Posthog(
                    project_api_key=api_key,
                    host=host,
                    # Disable debug mode in production
                    debug=False,
                    # Increase batch size for efficiency
                    batch_size=10,
                    # Flush every 60 seconds
                    max_batch_size=100,
                    # Use background thread for sending
                    send_asynchronously=True,
                )
                self.logger.info("PostHog telemetry client initialized")
            except ImportError:
                self.logger.warning(
                    "PostHog package not installed, telemetry disabled. "
                    "Install with: uv pip install 'codeweaver-mcp[recommended]'"
                )
                self.enabled = False
                self._client = None
            except Exception as e:
                self.logger.exception("Failed to initialize PostHog client: %s", e)
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
        self,
        event: str,
        properties: dict[str, Any],
        *,
        distinct_id: str = "anonymous",
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
                    "This may indicate a bug in event construction.",
                    event,
                )
                return

            # Filter properties for extra safety
            filtered_properties = self.privacy_filter.filter_event(properties)

            # Send to PostHog
            self._client.capture(
                distinct_id=distinct_id,
                event=event,
                properties=filtered_properties,
            )

            self.logger.debug("Telemetry event sent: %s", event)

        except Exception as e:
            # Never fail application due to telemetry
            # Just log and continue
            self.logger.exception("Failed to send telemetry event '%s': %s", event, e)

    def capture_from_event(self, event_obj: Any) -> None:
        """
        Send event from a TelemetryEvent object.

        Args:
            event_obj: Object implementing TelemetryEvent protocol
        """
        try:
            event_name, properties = event_obj.to_posthog_event()
            self.capture(event_name, properties)
        except Exception as e:
            self.logger.exception("Failed to capture event from object: %s", e)

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
            except Exception as e:
                self.logger.exception("Error during PostHog client shutdown: %s", e)

    def __enter__(self) -> PostHogClient:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
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


__all__ = (
    "PostHogClient",
    "get_telemetry_client",
)

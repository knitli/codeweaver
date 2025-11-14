# sourcery skip: name-type-suffix
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
PostHog telemetry client wrapper.

Provides a privacy-aware wrapper around the PostHog Python client with:
- Privacy filtering via serialize_for_telemetry() on data models
- Error handling (telemetry never crashes the application)
- Easy configuration and opt-out
- Event batching and throttling
"""

from __future__ import annotations

import logging

from functools import cache
from importlib.util import find_spec
from types import TracebackType
from typing import Any, Self

from pydantic import HttpUrl
from pydantic.types import SecretStr

from codeweaver.common.utils.utils import uuid7
from codeweaver.config._project import CODEWEAVER_POSTHOG_PROJECT_KEY
from codeweaver.core.types.aliases import UUID7HexT
from codeweaver.core.types.sentinel import Unset


NO_HOG = find_spec("posthog") is None

SESSION_ID = uuid7().hex

if NO_HOG:

    class Posthog:
        """Dummy Posthog client when package is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def capture(self, *args: Any, **kwargs: Any) -> None:
            pass

        def flush(self) -> None:
            pass

else:
    from posthog import Posthog

logger = logging.getLogger(__name__)


class PostHogClient:
    """
    Privacy-aware PostHog client wrapper.

    Handles telemetry event sending with error handling and configuration management.
    Privacy filtering is handled via serialize_for_telemetry() on BasedModel and
    DataclassSerializationMixin objects before passing to capture().

    Example:
        >>> client = PostHogClient.from_settings()
        >>> if client.enabled:
        ...     client.capture("session_summary", {"searches": 10})
    """

    def __init__(
        self,
        api_key: SecretStr | str | None = None,
        host: str = "https://us.i.posthog.com",
        *,
        enabled: bool = True,
    ):
        """
        Initialize PostHog client.

        Args:
            api_key: PostHog project key (required if enabled)
            host: PostHog host URL
            enabled: Enable telemetry sending
        """
        import os

        # Prefer environment variable, fallback to hardcoded key if not provided
        if api_key is None:
            api_key = os.environ.get("CODEWEAVER_POSTHOG_API_KEY", CODEWEAVER_POSTHOG_PROJECT_KEY)

        # Check at runtime if posthog is available (allows testing with mocked modules)
        if find_spec("posthog") is None:
            enabled = False

        self.enabled = bool(enabled and api_key)
        self.logger = logging.getLogger(__name__)

        self._client: Posthog | None = None

        if self.enabled and api_key:
            try:
                self._client = Posthog(
                    project_api_key=api_key
                    if isinstance(api_key, str)
                    else api_key.get_secret_value(),
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
        from codeweaver.config.settings import get_settings
        from codeweaver.config.telemetry import TelemetrySettings

        settings = get_settings().telemetry
        if not isinstance(settings, TelemetrySettings):
            from codeweaver.config.telemetry import DefaultTelemetrySettings

            settings = TelemetrySettings.model_validate(DefaultTelemetrySettings)
        if (
            not settings.enabled
            or not settings.posthog_project_key
            or not settings.posthog_host
            or settings.disable_telemetry
        ):
            return cls(enabled=False)
        posthog_host = (
            HttpUrl("https://us.i.posthog.com")
            if isinstance(settings.posthog_host, Unset)
            else settings.posthog_host
        )

        return cls(
            api_key=settings.posthog_project_key.get_secret_value(),
            host=posthog_host.encoded_string(),
            enabled=not settings.disable_telemetry,
        )

    def capture(
        self, event: str, properties: dict[str, Any], *, distinct_id: UUID7HexT = SESSION_ID
    ) -> None:
        """
        Send event to PostHog.

        Args:
            event: Event name
            properties: Event properties dictionary (should already be privacy-filtered)
            distinct_id: User identifier (default: "anonymous" for privacy)

        Note:
            This method never raises exceptions. All errors are logged
            but do not affect application execution.

            Properties should be privacy-safe. Use serialize_for_telemetry() on
            objects before passing properties to ensure sensitive data is filtered.
        """
        if not self.enabled or not self._client:
            self.logger.debug("Telemetry disabled, skipping event: %s", event)
            return

        try:
            # Send to PostHog
            _ = self._client.capture(distinct_id=distinct_id, event=event, properties=properties)

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

    def capture_with_serialization(
        self, event: str, data_obj: Any, *, distinct_id: UUID7HexT = SESSION_ID
    ) -> None:
        """
        Send event with automatic privacy serialization.

        Args:
            event: Event name
            data_obj: Object with serialize_for_telemetry() method (BasedModel or DataclassSerializationMixin)
            distinct_id: we generate a session_id

        Note:
            This method automatically calls serialize_for_telemetry() on the data object
            to ensure sensitive fields are filtered according to _telemetry_keys().
        """
        try:
            if hasattr(data_obj, "serialize_for_telemetry"):
                properties = data_obj.serialize_for_telemetry()
                self.capture(event, properties, distinct_id=distinct_id)
            else:
                self.logger.warning(
                    "Object %s does not have serialize_for_telemetry method, skipping event '%s'",
                    type(data_obj).__name__,
                    event,
                )
        except Exception:
            self.logger.exception("Failed to capture event with serialization for '%s'", event)

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

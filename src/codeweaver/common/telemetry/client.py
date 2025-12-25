# sourcery skip: name-type-suffix
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
PostHog telemetry client wrapper with context API support.

Provides a privacy-aware wrapper around the PostHog Python client with:
- PostHog v7 context API for session tracking and shared tags
- Privacy filtering via serialize_for_telemetry() on data models
- Error handling (telemetry never crashes the application)
- Easy configuration and opt-out
- Feature flag support for A/B testing
"""

from __future__ import annotations

import logging
import sys
import time

from functools import cache
from importlib.util import find_spec
from types import TracebackType
from typing import Any, Self

from pydantic import HttpUrl
from pydantic.types import SecretStr

from codeweaver.config._project import CODEWEAVER_POSTHOG_PROJECT_KEY
from codeweaver.core import uuid7
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

        def get_feature_flag(self, *args: Any, **kwargs: Any) -> str | None:
            return None

        def get_all_flags(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {}

    # Dummy context functions
    def new_context(*args: Any, **kwargs: Any) -> Any:
        from contextlib import nullcontext

        return nullcontext()

    def tag(*args: Any, **kwargs: Any) -> None:
        pass

    def set_context_session(*args: Any, **kwargs: Any) -> None:
        pass

    def identify_context(*args: Any, **kwargs: Any) -> None:
        pass

else:
    from posthog import Posthog, identify_context, new_context, set_context_session, tag

logger = logging.getLogger(__name__)


class PostHogClient:
    """
    Privacy-aware PostHog client wrapper with context API support.

    Handles telemetry event sending with error handling and configuration management.
    Uses PostHog v7 context API for session tracking and shared properties.
    Privacy filtering is handled via serialize_for_telemetry() on BasedModel and
    DataclassSerializationMixin objects before passing to capture().

    Example:
        >>> client = PostHogClient.from_settings()
        >>> client.start_session({"version": "0.5.0"})
        >>> if client.enabled:
        ...     client.capture("codeweaver_search", {"intent": "UNDERSTAND"})
        >>> client.end_session()
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
        self.session_id = SESSION_ID

        self._client: Posthog | None = None
        self._context: Any = None  # PostHog context manager
        self._session_started = False

        if self.enabled and api_key:
            try:
                self._client = Posthog(
                    project_api_key=api_key
                    if isinstance(api_key, str)
                    else api_key.get_secret_value(),
                    host=host,
                    # Disable debug mode in production
                    debug=False,
                    # Disable GeoIP - server IP isn't user IP
                    disable_geoip=True,
                )
                self.logger.info("PostHog telemetry client initialized")
            except ImportError:
                self.logger.warning(
                    "PostHog package not installed, telemetry disabled. "
                    "Install with: uv pip install 'code-weaver[recommended]'"  # type: ignore
                )
                self.enabled = False
                self._client = None
            except Exception:
                self.logger.warning("Failed to initialize PostHog client")
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

    def start_session(self, metadata: dict[str, Any] | None = None) -> None:
        """
        Initialize PostHog context for the session.

        Sets up session tracking and shared tags that will be inherited
        by all events captured during this session.

        Args:
            metadata: Optional metadata dict with keys like 'version', 'backend', etc.
        """
        if not self.enabled or self._session_started:
            return

        try:
            self._initialize_session_context(metadata)
        except Exception:
            self.logger.warning("Failed to start PostHog session context")

    def _initialize_session_context(self, metadata: dict[str, Any] | None) -> None:
        # Enter context
        self._context = new_context()
        self._context.__enter__()

        # Set session tracking (UUIDv7)
        set_context_session(self.session_id)
        identify_context(self.session_id)

        # Add shared tags for all events
        if metadata:
            for key, value in metadata.items():
                tag(key, value)

        # Add system info tags
        tag("python_version", f"{sys.version_info.major}.{sys.version_info.minor}")
        tag("os_platform", sys.platform)
        tag("system_locale", sys.getdefaultencoding())
        tag("system_timezone", time.tzname[0])

        self._session_started = True
        self.logger.debug("PostHog session started with ID: %s", self.session_id)

    def capture(
        self, event: str, properties: dict[str, Any], *, distinct_id: UUID7HexT | None = None
    ) -> None:
        """
        Send event to PostHog with privacy controls.

        Args:
            event: Event name
            properties: Event properties dictionary (should already be privacy-filtered)
            distinct_id: Optional user identifier (default: session_id for privacy)

        Note:
            This method never raises exceptions. All errors are logged
            but do not affect application execution.

            Properties should be privacy-safe. Use serialize_for_telemetry() on
            objects before passing properties to ensure sensitive data is filtered.

            The $process_person_profile property is automatically set to False
            to ensure privacy-respecting anonymous events.
        """
        if not self.enabled or not self._client:
            self.logger.debug("Telemetry disabled, skipping event: %s", event)
            return

        try:
            # Ensure privacy - no person profiles
            properties["$process_person_profile"] = False

            # Use session_id as distinct_id for privacy
            actual_distinct_id = distinct_id or self.session_id

            # Send to PostHog
            _ = self._client.capture(
                distinct_id=actual_distinct_id, event=event, properties=properties
            )

            self.logger.debug("Telemetry event sent: %s", event)

        except Exception:
            # Never fail application due to telemetry
            # Just log and continue
            self.logger.warning("Failed to send telemetry event '%s'", event)

    def get_feature_flag(self, flag_key: str) -> str | None:
        """
        Get feature flag value for the current session.

        Args:
            flag_key: Feature flag key

        Returns:
            Feature flag variant value or None if not found/disabled
        """
        if not self.enabled or not self._client:
            return None

        try:
            return self._client.get_feature_flag(flag_key, self.session_id)  # ty:ignore[invalid-return-type]
        except Exception:
            self.logger.warning("Failed to get feature flag '%s'", flag_key)
            return None

    def get_all_feature_flags(self) -> dict[str, Any]:
        """
        Get all feature flags for the current session.

        Returns:
            Dictionary of flag key to variant value
        """
        if not self.enabled or not self._client:
            return {}

        try:
            result = self._client.get_all_flags(self.session_id)
            return dict(result) if result else {}
        except Exception:
            self.logger.warning("Failed to get all feature flags")
            return {}

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
            self.logger.warning("Failed to capture event from object")

    def capture_with_serialization(
        self, event: str, data_obj: Any, *, distinct_id: UUID7HexT | None = None
    ) -> None:
        """
        Send event with automatic privacy serialization.

        Args:
            event: Event name
            data_obj: Object with serialize_for_telemetry() method (BasedModel or DataclassSerializationMixin)
            distinct_id: Optional distinct ID (defaults to session_id)

        Note:
            This method automatically calls serialize_for_telemetry() on the data object
            to ensure sensitive fields are filtered according to _telemetry_keys().
        """
        try:
            if hasattr(data_obj, "serialize_for_telemetry"):
                properties = data_obj.serialize_for_telemetry()
                self.capture(event, properties, distinct_id=distinct_id or self.session_id)  # ty:ignore[invalid-argument-type]
            else:
                self.logger.warning(
                    "Object %s does not have serialize_for_telemetry method, skipping event '%s'",
                    type(data_obj).__name__,
                    event,
                )
        except Exception:
            self.logger.warning("Failed to capture event with serialization for '%s'", event)

    def end_session(self) -> None:
        """
        Clean up context and flush pending events.

        Should be called at application shutdown to ensure all events
        are sent before exit.
        """
        # Exit context if active
        if self._context and self._session_started:
            try:
                self._context.__exit__(None, None, None)
                self._session_started = False
                self.logger.debug("PostHog session context closed")
            except Exception:
                self.logger.warning("Error closing PostHog session context")

        # Flush remaining events
        self.shutdown()

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
                self.logger.warning("Error during PostHog client shutdown")

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
        self.end_session()


@cache
def get_telemetry_client() -> PostHogClient:
    """
    Get singleton telemetry client instance.

    Returns:
        Cached PostHog client configured from settings
    """
    return PostHogClient.from_settings()


__all__ = ("SESSION_ID", "PostHogClient", "get_telemetry_client")

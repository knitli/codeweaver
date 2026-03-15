# SPDX-FileCopyrightText: 2026 Knitli Inc.
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

from types import TracebackType
from typing import Any, Self, cast

from pydantic import HttpUrl
from pydantic.types import SecretStr

from codeweaver.core import UUID7HexT, has_package, uuid7
from codeweaver.core.dependencies import TelemetrySettingsDep
from codeweaver.core.di import INJECTED, dependency_provider
from codeweaver.core.telemetry._project import CODEWEAVER_POSTHOG_PROJECT_KEY
from codeweaver.core.types import UNSET


NO_HOG = not has_package("posthog") or sys.modules.get("posthog") is None
SESSION_ID: UUID7HexT = uuid7().hex  # ty:ignore[invalid-assignment]
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


class TelemetryService:
    """
    Privacy-aware PostHog client wrapper with context API support.

    Handles telemetry event sending with error handling and configuration management.
    Uses PostHog v7 context API for session tracking and shared properties.
    Privacy filtering is handled via serialize_for_telemetry() on BasedModel and
    DataclassSerializationMixin objects before passing to capture().

    Example:
        >>> client = TelemetryService.from_settings()
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

        if api_key is None:
            api_key = (
                os.environ.get("CODEWEAVER_POSTHOG_API_KEY")
                or os.environ.get("CODEWEAVER__TELEMETRY__API_KEY")
                or os.environ.get("CODEWEAVER__TELEMETRY__POSTHOG_PROJECT_KEY")
                or CODEWEAVER_POSTHOG_PROJECT_KEY
            )
            if isinstance(api_key, SecretStr):
                api_key = api_key.get_secret_value()
        if NO_HOG:
            enabled = False
        self.enabled = bool(enabled and api_key)
        self.logger = logging.getLogger(__name__)
        self.session_id = SESSION_ID
        self._client: Posthog | None = None
        self._context: Any = None
        self._session_started = False
        if self.enabled and api_key:
            try:
                self._client = Posthog(
                    project_api_key=api_key
                    if isinstance(api_key, str)
                    else api_key.get_secret_value(),
                    host=host,
                    debug=False,
                    disable_geoip=True,
                )
                self.logger.info("PostHog telemetry client initialized")
            except ImportError:
                self.logger.warning(
                    "PostHog package not installed, telemetry disabled. Install with: uv pip install 'code-weaver[recommended]'"
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
    @dependency_provider("TelemetryService", scope="singleton")
    def from_settings(cls, settings: TelemetrySettingsDep = INJECTED) -> TelemetryService:
        """
        Create PostHog client from telemetry settings.

        Returns:
            Configured PostHog client instance
        """
        from codeweaver.core.config import TelemetrySettings

        if not isinstance(settings, TelemetrySettings):
            from codeweaver.core.config.telemetry import DefaultTelemetrySettings

            settings = TelemetrySettings.model_validate(DefaultTelemetrySettings)
        if (
            not settings.enabled
            or not settings.posthog_project_key
            or (not settings.posthog_host)
            or settings.disable_telemetry
        ):
            return cls(enabled=False)
        posthog_host = (
            HttpUrl("https://us.i.posthog.com")
            if settings.posthog_host is UNSET
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
        self._context = new_context()
        self._context.__enter__()
        set_context_session(self.session_id)
        identify_context(self.session_id)
        if metadata:
            for key, value in metadata.items():
                tag(key, value)
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
            properties["$process_person_profile"] = False
            actual_distinct_id = distinct_id or self.session_id
            _ = self._client.capture(
                distinct_id=actual_distinct_id, event=event, properties=properties
            )
            self.logger.debug("Telemetry event sent: %s", event)
        except Exception:
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
            return cast(str | None, self._client.get_feature_flag(flag_key, self.session_id))
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
        except Exception:
            self.logger.warning("Failed to get all feature flags")
            return {}
        else:
            return dict(result) if result else {}

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
                self.capture(event, properties, distinct_id=distinct_id or self.session_id)
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
        if self._context and self._session_started:
            try:
                self._context.__exit__(None, None, None)
                self._session_started = False
                self.logger.debug("PostHog session context closed")
            except Exception:
                self.logger.warning("Error closing PostHog session context")
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


async def get_telemetry_client() -> TelemetryService:
    """
    Get singleton telemetry client instance.

    Returns:
        Cached PostHog client configured from settings
    """
    from codeweaver.core.di import get_container

    return await get_container().resolve(TelemetryService)


__all__ = ("NO_HOG", "SESSION_ID", "TelemetryService", "get_telemetry_client")

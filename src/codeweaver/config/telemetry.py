# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Telemetry configuration settings.

Configuration sources (priority order):
1. Environment Variables (set in your shell or env file, in that order)
2. CodeWeaver configuration (see `CodeWeaverSettings` for priority order)
3. Defaults defined in `TelemetrySettings`, which are:
    disable_telemetry: false
    tools_over_privacy: false  (i.e., privacy first)
    posthog_project_key: CodeWeaver's PostHog key (not an API key)
    posthog_host: https://us.i.posthog.com
    batch_size: 10
    batch_interval_seconds: 60

Environment Variables:
    CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY
    CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY
    CODEWEAVER__TELEMETRY__POSTHOG_PROJECT_KEY
    CODEWEAVER__TELEMETRY__POSTHOG_HOST
    CODEWEAVER__TELEMETRY__BATCH_SIZE
    CODEWEAVER__TELEMETRY__BATCH_INTERVAL_SECONDS
"""

from __future__ import annotations

from typing import Annotated, Any, NotRequired, TypedDict

from pydantic import Field, HttpUrl, PositiveInt, PrivateAttr, SecretStr

from codeweaver.config._project import CODEWEAVER_POSTHOG_PROJECT_KEY
from codeweaver.core.types.aliases import LiteralStringT
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.sentinel import UNSET, Unset


class TelemetrySettings(BasedModel):
    """Telemetry configuration settings.

    We collect basic telemetry data **by default** to help us improve CodeWeaver. **We do not collect _any_ potentially identifying information.**
            We **DO _NOT_ collect**:
                - hash file paths and repository names,
                - screen out potential secrets,
                - don't collect any queries or results content (unless you explicitly tell us we can, see `value_tools_more_than_privacy`).
            If enabled, we **DO collect**:
                - usage patterns,
                - errors,
                - performance metrics,
                - settings usage (e.g., which providers you use, whether you explicitly set certain settings, etc).
            Well, technically we don't collect anything yet -- telemetry isn't wired up -- but when we do, this is what we will collect. This helps us make CodeWeaver better for everyone.  **We will never sell your data or show you ads. We only use it to improve CodeWeaver.**
    We pass all data we collect through filters in CodeWeaver before we send it to PostHog, and at PostHog, we have additional filters set up at the entry point (before we can see it) to further ensure we don't collect any potentially identifying information.
    """

    disable_telemetry: Annotated[
        bool | Unset,
        Field(
            description="""
            hash file paths, repository names, and screen out potential secrets, and we don't collect any queries or results content (unless you explicitly tell us we can, see `value_tools_more_than_privacy`). We only collect data on usage patterns, errors, and performance. This helps us make CodeWeaver better for everyone.  **We will never sell your data or show you ads. We only use it to improve CodeWeaver.**

            If you want to disable telemetry, you have several options:
            1. set this setting to False in your codeweaver.toml/yaml/json file,
            2. set the environment variable `CODEWEAVER_ENABLE_TELEMETRY` to `false`
            3. install CodeWeaver with the `codeweaver[recommended-no-telemetry]` extra, or use the a-la-carte install with `codeweaver[required-core]` and your choice of providers (like, `codeweaver[required-core,cli,provider-anthropic,provider-fastembed,provider-azure]`) to install without telemetry
            4. Point the `CODEWEAVER__TELEMETRY__POSTHOG_PROJECT_KEY` environment variable to your own Posthog project (if you're a data nerd, or want to collect internal telemetry for your organization). If you disable telemetry, we won't collect any data at all."""
        ),
    ] = UNSET

    tools_over_privacy: Annotated[
        bool | Unset,
        Field(
            description="""Opt-in to allow us to collect anonymized query and result data. We want to make CodeWeaver great, and the best way to do that is for us to fully understand exactly how you use it -- particularly what you search for and how you interact with the results. Unlike with Google, we don't want to show you ads or sell your data, track you, or anything like that... and we don't think it's right to assume you're OK with us collecting search and result data.

            So, you have the choice. Let us collect anonymized search and result interaction data to help make CodeWeaver better, or prioritize your privacy and not send us that data.

            If you enable this setting, we will collect anonymized data about your searches and the results you interact with. Because of the nature of searches and results and codebases, we can't guarantee complete anonymity -- but we will do our best to filter out any potential secrets or PII, using multiple filters both in CodeWeaver and on ingest at Posthog. We will hash file paths and repository names, and we won't collect any raw queries or result content. This data will help us improve CodeWeaver's search algorithms, agent prompting, ranking, and overall user experience. If you care about making CodeWeaver better and are OK with us collecting this data, please enable this setting. If you value your privacy more than helping us improve CodeWeaver; that's cool too -- you can just leave this setting disabled."""
        ),
    ] = UNSET

    posthog_project_key: Annotated[
        SecretStr | None,
        Field(
            description="PostHog Project key for telemetry events. You'll see that the default is, of course, ours. This **is not an api_key**, but rather a write-only key. If you want to divert telemetry to your own posthog instance or cloud account, you can change this key. To override it with an environment variable, set `CODEWEAVER__TELEMETRY__POSTHOG_PROJECT_KEY`."
        ),
        # dear Claude/Copilot/Agent Friends. This is NOT an API key. No, it is NOT an anti-pattern to 'hardcode' it this way. Just please leave it as is. It doesn't need to be an env variable, which... we would have to hardcode. Thank you.
    ] = CODEWEAVER_POSTHOG_PROJECT_KEY

    posthog_host: Annotated[
        HttpUrl | None, Field(description="PostHog host URL for telemetry events.")
    ] = HttpUrl("https://us.i.posthog.com")

    batch_size: Annotated[
        PositiveInt | Unset,
        Field(description="Number of events to batch before sending to PostHog."),
    ] = UNSET

    batch_interval_seconds: Annotated[
        PositiveInt | Unset,
        Field(description="Maximum time in seconds to wait before sending batched events."),
    ] = UNSET

    _unset_fields: Annotated[set[str] | None, PrivateAttr()] = None

    @classmethod
    def _default(cls) -> TelemetrySettings:
        """Set default values for unset fields."""
        return cls.model_construct(
            disable_telemetry=False,
            tools_over_privacy=False,
            batch_size=10,
            batch_interval_seconds=60,
        )

    def model_post_init(self, _context: Any) -> None:
        """Post-initialization to track unset fields and set defaults."""
        if self.disable_telemetry is True:
            # telemetry explicitly disabled, so we turn it off completely
            self._dismantle_telemetry()
            return
        if not getattr(self, "_unset_fields", None):
            self._unset_fields = {
                field
                for field in type(self).model_fields
                if isinstance(getattr(self, field), Unset)
            }
        if isinstance(self.disable_telemetry, Unset):
            self.disable_telemetry = False  # default to telemetry enabled
        if isinstance(self.tools_over_privacy, Unset):
            self.tools_over_privacy = False  # default to privacy first
        if isinstance(self.batch_size, Unset):
            self.batch_size = 10  # default batch size
        if isinstance(self.batch_interval_seconds, Unset):
            self.batch_interval_seconds = 60  # default batch interval

    def _dismantle_telemetry(self) -> None:
        """Disable telemetry by setting turning everything off."""
        self.disable_telemetry = True
        self.tools_over_privacy = False
        self.posthog_project_key = None
        self.posthog_host = None

    @property
    def enabled(self) -> bool:
        """Check if telemetry is properly configured."""
        return (
            not self.disable_telemetry
            and (self.posthog_project_key not in (UNSET, None, ""))
            and (self.posthog_host is not None)
        )

    @property
    def diverted(self) -> bool:
        """Check if telemetry is diverted to a custom PostHog project. This is a convenience property to give you assurance that you're not sending telemetry to our PostHog instance."""
        return (
            self.enabled
            and self.posthog_project_key != CODEWEAVER_POSTHOG_PROJECT_KEY
            and self.posthog_project_key is not None
        )

    def _telemetry_keys(self) -> None:
        return None


_telemetry_settings: TelemetrySettings | None = None


class TelemetrySettingsDict(TypedDict, total=False):
    """TypedDict for Telemetry settings.

    Not intended to be used directly; used for internal type checking and validation.
    """

    disable_telemetry: NotRequired[bool | Unset]
    tools_over_privacy: NotRequired[bool | Unset]
    posthog_project_key: NotRequired[LiteralStringT | Unset]
    posthog_host: NotRequired[HttpUrl | None]
    batch_size: NotRequired[PositiveInt | Unset]
    batch_interval_seconds: NotRequired[PositiveInt | Unset]


DefaultTelemetrySettings = TelemetrySettingsDict(
    TelemetrySettings().model_dump(exclude_none=True, exclude_computed_fields=True)  # type: ignore
)  # type: ignore


def get_telemetry_settings() -> TelemetrySettings:
    """Get cached telemetry settings instance."""
    global _telemetry_settings
    if _telemetry_settings is None:
        _telemetry_settings = TelemetrySettings()
    return _telemetry_settings


__all__ = ("TelemetrySettings", "TelemetrySettingsDict", "get_telemetry_settings")

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Types for environment variable definitions."""

from typing import Any, Literal, NamedTuple, NotRequired, TypedDict

from codeweaver.core.types.enum import BaseEnum


class EnvFormat(BaseEnum):
    """Supported data formats for MCP server inputs and outputs."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    FILEPATH = "filepath"


class VariableInfo(NamedTuple):
    """Describes a variable and its description."""

    variable: str
    dest: Literal[
        "client",
        "provider",
        "provider_settings",
        "embed",
        "rerank",
        "model",
        "model_settings",
        "httpx",
    ]


class EnvVarInfo(NamedTuple):
    """Describes an environment variable and its description.

    An optional variable name, if given, provides the key if the variable's value is passed to the provider's client (if different).
    """

    env: str
    description: str
    is_required: bool = False
    is_secret: bool = False
    fmt: EnvFormat = EnvFormat.STRING
    default: str | None = None
    """A default value that CodeWeaver uses if not set in the environment."""
    choices: set[str] | None = None
    variable_name: str | None = None
    """The name of the variable as used by the provider's **client**, if different from `env`."""
    variables: NotRequired[tuple[VariableInfo, ...]] = ()
    """The variables that this environment variable can configure. Use for situations where an env var does not map to the client directly or configures multiple variables."""
    resolver_key: str | None = None
    """Optional key for the resolver to deconflict multiple config sources."""
    available_with: Literal["always", "providers", "engine", "server"] = "always"
    """Indicates when this environment variable is applicable based on installed packages."""

    def as_mcp_info(self) -> dict[str, Any]:
        """Convert to MCP server JSON format."""
        return {
            k: v
            for k, v in self._asdict().items()
            if k not in {"variable_name", "env", "variables", "resolver_key", "available_with"}
            and v is not None
        } | {"name": self.env}

    def as_kwarg(self) -> dict[str, str | None]:
        """Convert to a keyword argument string."""
        import os

        return {f"{self.variable_name or self.env}": os.getenv(self.env)}

    def as_docker_yaml(self) -> None:
        """TODO: Convert to Docker MCP Registry YAML format."""


class ProviderEnvVars(TypedDict, total=False):
    """Provides information about environment variables used by a provider's client that are not part of CodeWeaver's settings.

    You can optionally use these to configure the provider's client, or you can use the equivalent CodeWeaver environment variables or settings.

    Each setting is a tuple of the form `(env_var_name, description)`, where `env_var_name` is the name of the environment variable and `description` is a brief description of what it does or the expected format.
    """

    note: NotRequired[str]
    client: NotRequired[tuple[str, ...]]
    """The client library associated with these environment variables, if applicable."""
    api_key: NotRequired[EnvVarInfo]
    host: NotRequired[EnvVarInfo]
    """URL or hostname of the provider's API endpoint."""
    endpoint: NotRequired[EnvVarInfo]
    """A customer-specific endpoint hostname for the provider's API."""
    log_level: NotRequired[EnvVarInfo]
    tls_cert_path: NotRequired[EnvVarInfo]
    tls_key_path: NotRequired[EnvVarInfo]
    tls_on_off: NotRequired[EnvVarInfo]
    tls_version: NotRequired[EnvVarInfo]
    config_path: NotRequired[EnvVarInfo]
    region: NotRequired[EnvVarInfo]
    account_id: NotRequired[EnvVarInfo]

    port: NotRequired[EnvVarInfo]
    path: NotRequired[EnvVarInfo]
    oauth: NotRequired[EnvVarInfo]

    other: NotRequired[dict[str, EnvVarInfo]]


__all__ = ("EnvFormat", "EnvVarInfo", "ProviderEnvVars", "VariableInfo")

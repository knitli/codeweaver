#!/usr/bin/env -S uv -s
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# ///script
# python-version = ">=3.12"
# dependencies = ["pydantic", "textcase"]
# ///
"""MCP server.json models."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, RootModel

from codeweaver import __version__
from codeweaver.config.envs import environment_variables
from codeweaver.core.file_extensions import ALL_LANGUAGES
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.types.models import EnvFormat
from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES
from codeweaver.providers.provider import (
    Provider,
    ProviderEnvVarInfo,
    ProviderEnvVars,
    ProviderKind,
)


class McpInputDict(TypedDict):
    """Dictionary representation of an MCP Input."""

    name: str
    description: str | None
    is_required: bool | None
    fmt: EnvFormat | None
    value: str | None
    is_secret: bool | None
    default: str | None
    choices: list[str] | None


def get_settings_env_vars() -> list[McpInputDict]:
    """Get all general codeweaver settings environment variables."""
    return sorted(
        (McpInputDict(**var.as_mcp_info()) for var in environment_variables()),  # ty: ignore[missing-typed-dict-key]
        key=lambda v: v["name"],
    )


def _all_var_infos() -> dict[Provider, set[ProviderEnvVarInfo]]:
    """Get all environment variable infos for all providers."""
    all_vars: dict[Provider, set[ProviderEnvVarInfo]] = {}
    for provider in Provider:
        var_infos: set[ProviderEnvVarInfo] = set()
        if envvars := _env_vars_for_provider(provider):
            var_infos |= {
                val for key, val in envvars.items() if key not in ("note", "other" and val)
            }
            if other := envvars.get("other"):
                var_infos |= set(other)
        all_vars[provider] = var_infos
    return all_vars


def get_provider_env_vars() -> dict[Provider, list[McpInputDict]]:
    """Get all provider-specific environment variables."""
    return {
        provider: sorted(
            (McpInputDict(**var.as_mcp_info()) for var in var_infos),  # type: ignore[missing-typed-dict-key]
            key=lambda v: v["name"],
        )
        for provider, var_infos in _all_var_infos().items()
    }


def _providers_for_kind(kind: ProviderKind) -> set[Provider]:
    return {prov for prov in Provider if kind in PROVIDER_CAPABILITIES[prov]}


def _shared_env_vars() -> dict[ProviderEnvVarInfo, set[Provider]]:
    """Get environment variables shared across multiple providers."""
    all_vars = _all_var_infos()
    shared_vars: dict[ProviderEnvVarInfo, set[Provider]] = {}
    for provider, var_infos in all_vars.items():
        for var_info in var_infos:
            if var_info not in shared_vars:
                shared_vars[var_info] = set()
            shared_vars[var_info].add(provider)
    # Filter to only those vars shared by multiple providers
    return {
        var_info: providers for var_info, providers in shared_vars.items() if len(providers) > 1
    }


def _generalized_provider_env_vars() -> list[ProviderEnvVarInfo]:
    """Get generalized environment variables shared across multiple providers."""
    generalized_vars: list[ProviderEnvVarInfo] = []
    for var_info, providers in _shared_env_vars().items():
        provider_names = ", ".join(sorted(prov.as_title for prov in providers))
        generalized_vars.append(
            ProviderEnvVarInfo._replace({
                "description": f"{var_info.description} (Used by: {provider_names})"
            })
        )
    return generalized_vars


def _env_vars_for_provider(provider: Provider) -> tuple[ProviderEnvVars, ...] | None:
    """Get the environment variables required for a given provider."""
    return provider.other_env_vars


def _languages() -> list[str]:
    """Get all supported programming languages."""
    return sorted(
        ALL_LANGUAGES
        | {lang.variable for lang in SemanticSearchLanguage}
        | {lang.variable for lang in ConfigLanguage}
    )


def capabilities() -> dict[str, Any]:
    """Get the server capabilities."""
    return {
        "languages_supported": len(_languages()),
        "embedding_providers": [
            prov.as_title for prov in _providers_for_kind(ProviderKind.EMBEDDING)
        ],
        "vector_store_providers": [
            prov.as_title for prov in _providers_for_kind(ProviderKind.VECTOR_STORE)
        ],
        "sparse_embedding_providers": [
            prov.as_title for prov in _providers_for_kind(ProviderKind.SPARSE_EMBEDDING)
        ],
        "reranking_providers": [
            prov.as_title for prov in _providers_for_kind(ProviderKind.RERANKING)
        ],
        # add when available:
        # "agent_providers": [prov.as_title for prov in _providers_for_kind(ProviderKind.AGENT)],
        # "data_providers": [prov.as_title for prov in _providers_for_kind(ProviderKind.DATA)],
    }


AGENT_PROVIDERS = _providers_for_kind(ProviderKind.AGENT)
DATA_PROVIDERS = _providers_for_kind(ProviderKind.DATA)
EMBEDDING_PROVIDERS = _providers_for_kind(ProviderKind.EMBEDDING)
SPARSE_EMBEDDING_PROVIDERS = _providers_for_kind(ProviderKind.SPARSE_EMBEDDING)
RERANKING_PROVIDERS = _providers_for_kind(ProviderKind.RERANKING)
VECTOR_STORE_PROVIDERS = _providers_for_kind(ProviderKind.VECTOR_STORE)


class Repository(BaseModel):
    """Repository metadata for MCP server source code."""

    url: AnyUrl = Field(
        AnyUrl("https://github.com/knitli/codeweaver"),
        description="Repository URL for browsing source code. Should support both web browsing and git clone operations.",
        examples=["https://github.com/modelcontextprotocol/servers"],
    )
    source: str = Field(
        "github",
        description="Repository hosting service identifier. Used by registries to determine validation and API access methods.",
        examples=["github"],
    )
    id: str | None = Field(
        "1024985391",
        description="Repository identifier from the hosting service (e.g., GitHub repo ID). Owned and determined by the source forge. Should remain stable across repository renames and may be used to detect repository resurrection attacks - if a repository is deleted and recreated, the ID should change. For GitHub, use: gh api repos/<owner>/<repo> --jq '.id'",
        examples=["b94b5f7e-c7c6-d760-2c78-a5e9b8a5b8c9"],
    )
    subfolder: str | None = Field(
        "src/codeweaver",
        description="Optional relative path from repository root to the server location within a monorepo or nested package structure. Must be a clean relative path.",
        examples=["src/everything"],
    )


REPOSITORY = Repository(
    url="https://github.com/knitli/codeweaver",
    source="github",
    id="1024985391",
    subfolder="src/codeweaver",
)


class Status(Enum):
    """Lifecycle status of the MCP server."""

    active = "active"
    deprecated = "deprecated"
    deleted = "deleted"


class Server(BaseModel):
    """MCP server metadata."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(
        "com.knitli/codeweaver",
        pattern=r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$",
        min_length=3,
        max_length=200,
        description="Server name in reverse-DNS format. Must contain exactly one forward slash separating namespace from server name.",
        examples=["io.github.user/weather"],
    )
    description: str = Field(
        "Semantic code search built for AI agents. Hybrid AST-aware embeddings for 170+ languages.",
        max_length=100,
        min_length=1,
        description="Clear human-readable explanation of server functionality. Should focus on capabilities, not implementation details.",
        examples=["MCP server providing weather data and forecasts via OpenWeatherMap API"],
    )
    status: Status | None = Field(
        Status.active,
        description="Server lifecycle status. 'deprecated' indicates the server is no longer recommended for new usage. 'deleted' indicates the server should never be installed and existing installations should be uninstalled - this is rare, and usually indicates malware or a legal takedown.",
    )
    repository: Repository | None = Field(
        REPOSITORY,
        description="Optional repository metadata for the MCP server source code. Recommended for transparency and security inspection.",
    )
    version: str = Field(
        __version__,
        description="Version string for this server. SHOULD follow semantic versioning (e.g., '1.0.2', '2.1.0-alpha'). Equivalent of Implementation.version in MCP specification. Non-semantic versions are allowed but may not sort predictably. Version ranges are rejected (e.g., '^1.2.3', '~1.2.3', '>=1.2.3', '1.x', '1.*').",
        max_length=255,
        examples=["1.0.2"],
    )
    website_url: AnyUrl | None = Field(
        AnyUrl("https://github.com/knitli/codeweaver"),
        description="Optional URL to the server's homepage, documentation, or project website. This provides a central link for users to learn more about the server. Particularly useful when the server has custom installation instructions or setup requirements.",
        alias="websiteUrl",
        examples=["https://modelcontextprotocol.io/examples"],
    )


class Input(BaseModel):
    """MCP server input metadata."""

    model_config = ConfigDict(populate_by_name=True)

    description: str | None = Field(
        None,
        description="A description of the input, which clients can use to provide context to the user.",
    )
    is_required: bool | None = Field(
        False,
        alias="isRequired",
        description="Indicates whether the input is required. If true, clients should prompt the user to provide a value if one is not already set.",
    )
    fmt: EnvFormat | None = Field(
        EnvFormat.string,
        description='Specifies the input format. Supported values include `filepath`, which should be interpreted as a file on the user\'s filesystem.\n\nWhen the input is converted to a string, booleans should be represented by the strings "true" and "false", and numbers should be represented as decimal values.',
        alias="format",
    )
    value: str | None = Field(
        None,
        description="The default value for the input. If this is not set, the user may be prompted to provide a value. If a value is set, it should not be configurable by end users.\n\nIdentifiers wrapped in `{curly_braces}` will be replaced with the corresponding properties from the input `variables` map. If an identifier in braces is not found in `variables`, or if `variables` is not provided, the `{curly_braces}` substring should remain unchanged.\n",
    )
    is_secret: bool | None = Field(
        False,
        description="Indicates whether the input is a secret value (e.g., password, token). If true, clients should handle the value securely.",
        alias="isSecret",
    )
    default: str | None = Field(None, description="The default value for the input.")
    choices: list[str] | None = Field(
        None,
        description="A list of possible values for the input. If provided, the user must select one of these values.",
    )


class InputWithVariables(Input):
    """MCP server input metadata with variable substitution support."""

    variables: dict[str, Input] | None = Field(
        None,
        description="A map of variable names to their values. Keys in the input `value` that are wrapped in `{curly_braces}` will be replaced with the corresponding variable values.",
    )


class PositionalArgumentType(Enum):
    """Argument type for positional arguments."""

    positional = "positional"


class PositionalArgument(InputWithVariables):
    """A positional input is a value inserted verbatim into the command line."""

    type_: PositionalArgumentType = Field(..., examples=["positional"], alias="type")
    value_hint: str | None = Field(
        None,
        description="An identifier-like hint for the value. This is not part of the command line, but can be used by client configuration and to provide hints to users.",
        alias="valueHint",
        examples=["file_path"],
    )
    is_repeated: bool | None = Field(
        False,
        description="Whether the argument can be repeated multiple times in the command line.",
        alias="isRepeated",
    )


class NamedArgumentType(Enum):
    """Argument type for named arguments."""

    named = "named"


class NamedArgument(InputWithVariables):
    """A named argument with a flag prefix (e.g., --port)."""

    type_: NamedArgumentType = Field(..., examples=["named"], alias="type")
    name: str = Field(
        ..., description="The flag name, including any leading dashes.", examples=["--port"]
    )
    is_repeated: bool | None = Field(
        False,
        description="Whether the argument can be repeated multiple times.",
        alias="isRepeated",
    )


class KeyValueInput(InputWithVariables):
    """Input for headers or environment variables."""

    name: str = Field(
        ..., description="Name of the header or environment variable.", examples=["SOME_VARIABLE"]
    )


class Argument(RootModel[PositionalArgument | NamedArgument]):
    """
    Warning: Arguments construct command-line parameters that may contain user-provided input.
    This creates potential command injection risks if clients execute commands in a shell environment.
    For example, a malicious argument value like ';rm -rf ~/Development' could execute dangerous commands.
    Clients should prefer non-shell execution methods (e.g., posix_spawn) when possible to eliminate
    injection risks entirely. Where not possible, clients should obtain consent from users or agents
    to run the resolved command before execution.
    """


class StdioTransportType(Enum):
    """Transport type for stdio."""

    stdio = "stdio"


class StdioTransport(BaseModel):
    """Standard I/O transport configuration."""

    model_config = ConfigDict(populate_by_name=True)

    type_: StdioTransportType = Field(
        StdioTransportType.stdio, description="Transport type", examples=["stdio"], alias="type"
    )


class StreamableHttpTransportType(Enum):
    """Transport type for streamable HTTP."""

    streamable_http = "streamable-http"


class StreamableHttpTransport(BaseModel):
    """Streamable HTTP transport configuration."""

    model_config = ConfigDict(populate_by_name=True)

    type_: StreamableHttpTransportType = Field(
        StreamableHttpTransportType.streamable_http,
        description="Transport type",
        examples=["streamable-http"],
        alias="type",
    )
    url: str = Field(
        ...,
        description="URL template for the streamable-http transport. Variables in {curly_braces} reference argument valueHints, argument names, or environment variable names. After variable substitution, this should produce a valid URI.",
        examples=["https://api.example.com/mcp"],
    )
    headers: list[KeyValueInput] | None = Field(None, description="HTTP headers to include")


class SseTransportType(Enum):
    """Transport type for Server-Sent Events."""

    sse = "sse"


class SseTransport(BaseModel):
    """Server-Sent Events transport configuration."""

    model_config = ConfigDict(populate_by_name=True)

    type_: SseTransportType = Field(
        SseTransportType.sse, description="Transport type", examples=["sse"], alias="type"
    )
    url: AnyUrl = Field(
        ...,
        description="Server-Sent Events endpoint URL",
        examples=["https://mcp-fs.example.com/sse"],
    )
    headers: list[KeyValueInput] | None = Field(None, description="HTTP headers to include")


class FieldMeta(BaseModel):
    """Extension metadata using reverse DNS namespacing for vendor-specific data."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    io_modelcontextprotocol_registry_publisher_provided: dict[str, Any] | None = Field(
        None,
        alias="io.modelcontextprotocol.registry/publisher-provided",
        description="Publisher-provided metadata for downstream registries",
    )
    io_modelcontextprotocol_registry_official: dict[str, Any] | None = Field(
        None,
        alias="io.modelcontextprotocol.registry/official",
        description="Official MCP registry metadata (read-only, added by registry)",
    )


class Package(BaseModel):
    """Package distribution configuration for an MCP server."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    registry_type: str = Field(
        ...,
        description="Registry type indicating how to download packages (e.g., 'npm', 'pypi', 'oci', 'nuget', 'mcpb')",
        examples=["npm", "pypi", "oci", "nuget", "mcpb"],
        alias="registryType",
    )
    registry_base_url: AnyUrl | None = Field(
        None,
        description="Base URL of the package registry",
        examples=[
            "https://registry.npmjs.org",
            "https://pypi.org",
            "https://docker.io",
            "https://api.nuget.org",
            "https://github.com",
            "https://gitlab.com",
        ],
        alias="registryBaseUrl",
    )
    identifier: str = Field(
        "codeweaver",
        description="Package identifier - either a package name (for registries) or URL (for direct downloads)",
        examples=[
            "@modelcontextprotocol/server-brave-search",
            "https://github.com/example/releases/download/v1.0.0/package.mcpb",
        ],
    )
    version: str = Field(
        __version__,
        description="Package version. Must be a specific version. Version ranges are rejected (e.g., '^1.2.3', '~1.2.3', '>=1.2.3', '1.x', '1.*').",
        examples=["1.0.2"],
        min_length=1,
    )
    file_sha256: str | None = Field(
        None,
        pattern=r"^[a-f0-9]{64}$",
        alias="fileSha256",
        description="SHA-256 hash of the package file for integrity verification. Required for MCPB packages and optional for other package types. Authors are responsible for generating correct SHA-256 hashes when creating server.json. If present, MCP clients must validate the downloaded file matches the hash before running packages to ensure file integrity.",
        examples=["fe333e598595000ae021bd27117db32ec69af6987f507ba7a63c90638ff633ce"],
    )
    runtime_hint: str | None = Field(
        "uvx",
        alias="runtimeHint",
        description="A hint to help clients determine the appropriate runtime for the package. This field should be provided when `runtimeArguments` are present.",
        examples=["npx", "uvx", "docker", "dnx"],
    )
    transport: StdioTransport | StreamableHttpTransport | SseTransport = Field(
        ..., description="Transport protocol configuration for the package"
    )
    runtime_arguments: list[Argument] | None = Field(
        None,
        alias="runtimeArguments",
        description="A list of arguments to be passed to the package's runtime command (such as docker or npx). The `runtimeHint` field should be provided when `runtimeArguments` are present.",
    )
    package_arguments: list[Argument] | None = Field(
        None,
        description="A list of arguments to be passed to the package's binary.",
        alias="packageArguments",
    )
    environment_variables: list[KeyValueInput] | None = Field(
        None,
        description="A mapping of environment variables to be set when running the package.",
        alias="environmentVariables",
    )


class ServerDetail(Server):
    """Complete MCP server definition including packages and remotes."""

    field_schema: AnyUrl | None = Field(
        AnyUrl("https://static.modelcontextprotocol.io/schemas/2025-09-16/server.schema.json"),
        alias="$schema",
        description="JSON Schema URI for this server.json format",
        examples=["https://static.modelcontextprotocol.io/schemas/2025-09-16/server.schema.json"],
    )
    packages: list[Package] | None = Field(None)
    remotes: list[StreamableHttpTransport | SseTransport] | None = Field(None)
    field_meta: FieldMeta | None = Field(
        None,
        alias="_meta",
        description="Extension metadata using reverse DNS namespacing for vendor-specific data",
    )


class McpServerDetail(RootModel[ServerDetail]):
    """Root model for MCP Server Detail JSON."""


def all_env_vars() -> list[McpInputDict]:
    """Get all environment variables, both general and provider-specific."""
    general_vars = get_settings_env_vars()
    generalized_provider_vars = sorted(
        (McpInputDict(**var.as_mcp_info()) for var in _generalized_provider_env_vars()),  # type: ignore[missing-typed-dict-key]
        key=lambda v: v["env"],
    )
    return (
        general_vars
        + generalized_provider_vars
        + sorted(
            (var for provider_vars in get_provider_env_vars().values() for var in provider_vars),
            key=lambda v: v["name"],
        )
    )


def load_server_detail() -> ServerDetail:
    """Load the MCP server detail from server.json."""
    file_path = Path(__file__).parent.parent.parent / "server.json"
    return ServerDetail.model_validate_json(file_path.read_text())

#!/usr/bin/env -S uv -s
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# ///script
# python-version = ">=3.12"
# dependencies = ["pydantic", "textcase", "jsonschema", "httpx"]
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
        (McpInputDict(**var.as_mcp_info()) for var in environment_variables().values()),  # type: ignore[misc]
        key=lambda v: v["name"],
    )


def _all_var_infos() -> dict[Provider, list[ProviderEnvVarInfo]]:
    """Get all environment variable infos for all providers."""
    all_vars: dict[Provider, list[ProviderEnvVarInfo]] = {}
    for provider in Provider:
        var_infos: list[ProviderEnvVarInfo] = []
        if envvars_tuple := _env_vars_for_provider(provider):
            # envvars_tuple is a tuple of ProviderEnvVars dicts
            for envvars in envvars_tuple:
                var_infos.extend([
                    val for key, val in envvars.items()
                    if key not in ("note", "other") and isinstance(val, ProviderEnvVarInfo)
                ])
                if other := envvars.get("other"):
                    var_infos.extend([v for v in other if isinstance(v, ProviderEnvVarInfo)])
        all_vars[provider] = var_infos
    return all_vars


def get_provider_env_vars() -> dict[Provider, list[McpInputDict]]:
    """Get all provider-specific environment variables."""
    return {
        provider: sorted(
            (McpInputDict(**var.as_mcp_info()) for var in var_infos),  # type: ignore[misc]
            key=lambda v: v["name"],
        )
        for provider, var_infos in _all_var_infos().items()
    }


def _providers_for_kind(kind: ProviderKind) -> set[Provider]:
    return {prov for prov in Provider if prov in PROVIDER_CAPABILITIES and kind in PROVIDER_CAPABILITIES[prov]}


def _shared_env_vars() -> dict[str, tuple[ProviderEnvVarInfo, list[Provider]]]:
    """Get environment variables shared across multiple providers."""
    all_vars = _all_var_infos()
    # Use env name as key since ProviderEnvVarInfo is not hashable
    shared_vars: dict[str, tuple[ProviderEnvVarInfo, list[Provider]]] = {}
    for provider, var_infos in all_vars.items():
        for var_info in var_infos:
            if var_info.env not in shared_vars:
                shared_vars[var_info.env] = (var_info, [])
            shared_vars[var_info.env][1].append(provider)
    # Filter to only those vars shared by multiple providers
    return {
        env: (var_info, providers)
        for env, (var_info, providers) in shared_vars.items()
        if len(providers) > 1
    }


def _generalized_provider_env_vars() -> list[ProviderEnvVarInfo]:
    """Get generalized environment variables shared across multiple providers."""
    generalized_vars: list[ProviderEnvVarInfo] = []
    for (var_info, providers) in _shared_env_vars().values():
        provider_names = ", ".join(sorted(prov.as_title for prov in providers))
        # Create a new ProviderEnvVarInfo with updated description
        generalized_vars.append(
            ProviderEnvVarInfo(
                env=var_info.env,
                description=f"{var_info.description} (Used by: {provider_names})",
                is_required=var_info.is_required,
                is_secret=var_info.is_secret,
                fmt=var_info.fmt,
                default=var_info.default,
                choices=var_info.choices,
                variable_name=var_info.variable_name,
            )
        )
    return generalized_vars


def _env_vars_for_provider(provider: Provider) -> tuple[ProviderEnvVars, ...] | None:
    """Get the environment variables required for a given provider."""
    return provider.other_env_vars


def _languages() -> list[str]:
    """Get all supported programming languages."""
    semantic = {lang.variable for lang in SemanticSearchLanguage}
    all_languages = {str(lang) for lang in ALL_LANGUAGES if str(lang).lower() not in semantic}
    return sorted(
        all_languages
        | {f"{lang} (AST support)" for lang in SemanticSearchLanguage}
        | {lang.variable for lang in ConfigLanguage if not lang.is_semantic_search_language}
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
        f"Semantic code search built for AI agents. Hybrid AST-aware embeddings for {len(_languages())} languages.",
        max_length=100,
        min_length=1,
        description="Clear human-readable explanation of server functionality. Should focus on capabilities, not implementation details.",
        examples=["MCP server providing weather data and forecasts via OpenWeatherMap API"],
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
        None,
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
    value_hint: str | None = Field(
        None,
        description="An identifier-like hint for the value. This is not part of the command line, but can be used by client configuration and to provide hints to users.",
        alias="valueHint",
        examples=["host", "port"],
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
        description="Package identifier - package name for npm/pypi/nuget, full image reference with tag for OCI (e.g., ghcr.io/owner/repo:v1.0.0), or download URL for MCPB",
        examples=[
            "@modelcontextprotocol/server-brave-search",
            "ghcr.io/modelcontextprotocol/server-example:v1.2.3",
            "https://github.com/example/releases/download/v1.0.0/package.mcpb",
        ],
    )
    version: str | None = Field(
        None,
        description="Package version. Required for npm/pypi/nuget packages. Optional for MCPB packages (can be embedded in download URL). Not used for OCI packages (version included in identifier tag). Must be a specific version. Version ranges are rejected (e.g., '^1.2.3', '~1.2.3', '>=1.2.3', '1.x', '1.*').",
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
        AnyUrl("https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json"),
        alias="$schema",
        description="JSON Schema URI for this server.json format",
        examples=["https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json"],
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
        (McpInputDict(**var.as_mcp_info()) for var in _generalized_provider_env_vars()),  # type: ignore[misc]
        key=lambda v: v["name"],
    )

    # Deduplicate provider vars by name
    seen_names: set[str] = set()
    unique_provider_vars: list[McpInputDict] = []
    for provider_vars in get_provider_env_vars().values():
        for var in provider_vars:
            if var["name"] not in seen_names:
                seen_names.add(var["name"])
                unique_provider_vars.append(var)

    return (
        general_vars
        + generalized_provider_vars
        + sorted(unique_provider_vars, key=lambda v: v["name"])
    )


def load_server_detail() -> ServerDetail:
    """Load the MCP server detail from server.json."""
    file_path = Path(__file__).parent.parent.parent / "server.json"
    return ServerDetail.model_validate_json(file_path.read_text())


def _create_uvx_package() -> Package:
    """Create the uvx (PyPI) package configuration."""
    env_vars = all_env_vars()

    return Package(
        registry_type="pypi",
        registry_base_url=AnyUrl("https://pypi.org"),
        identifier="code-weaver",
        version=__version__,
        runtime_hint="uvx",
        transport=StdioTransport(
            type_=StdioTransportType.stdio,

        ),

        package_arguments=[
            # Subcommand
            PositionalArgument(
                type_=PositionalArgumentType.positional,
                description="Start the MCP server",
                value="server",
                is_required=True,
            ),
            # Server command flags (from server.py CLI)
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--project",
                description="Path to the code repository to index and search",
                is_required=False,
                value_hint="path",
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--config",
                description="Path to configuration file (TOML, YAML or JSON format)",
                is_required=False,
                value_hint="file_path",
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--host",
                description="Host address for MCP server",
                is_required=False,
                default="127.0.0.1",
                value_hint="host",
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--port",
                description="Port for MCP server",
                is_required=False,
                default="9328",
                fmt=EnvFormat.NUMBER,
                value_hint="port",
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--transport",
                description="Transport type for MCP communication (only streamable-http supported for persistent state)",
                is_required=False,
                default="streamable-http",
                choices=["streamable-http"],
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--verbose",
                description="Enable verbose logging with timestamps",
                is_required=False,
                fmt=EnvFormat.BOOLEAN,
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--debug",
                description="Enable debug logging",
                is_required=False,
                fmt=EnvFormat.BOOLEAN,
            ),
        ],
        environment_variables=[
            KeyValueInput.model_validate(var)
            for var in env_vars
        ],
    )


def _get_docker_env_vars() -> list[KeyValueInput]:
    """Get environment variables for Docker package from actual code."""
    # Start with CodeWeaver settings variables
    settings_vars = get_settings_env_vars()

    # Get common provider API keys that Docker users will need
    provider_vars = get_provider_env_vars()

    # Common provider API keys to include
    common_api_keys = {
        "VOYAGE_API_KEY",
        "COHERE_API_KEY",
        "OPENAI_API_KEY",
        "MISTRAL_API_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "QDRANT_API_KEY",
        "QDRANT__SERVICE__API_KEY",
    }

    docker_vars = []

    # Add all CodeWeaver settings (already filtered for Docker relevance)
    docker_vars.extend(
        KeyValueInput(
            name=var["name"],
            description=var.get("description", ""),
            is_required=var.get("is_required", False),
            is_secret=var.get("is_secret", False),
            default=var.get("default"),
            fmt=var.get("fmt"),
        )
        for var in settings_vars
    )
    # Add common provider API keys
    seen_keys = {v["name"] for v in settings_vars}
    for provider_var_list in provider_vars.values():
        for var in provider_var_list:
            if var["name"] in common_api_keys and var["name"] not in seen_keys:
                docker_vars.append(KeyValueInput(
                    name=var["name"],
                    description=var.get("description", ""),
                    is_required=var.get("is_required", False),
                    is_secret=var.get("is_secret", False),
                    default=var.get("default"),
                    fmt=var.get("fmt"),
                ))
                seen_keys.add(var["name"])

    return docker_vars


def _create_docker_package() -> Package:
    """Create the Docker (OCI) package configuration."""
    env_vars = all_env_vars()
    as_keyvalues = [KeyValueInput(
        **(var)
    ) for var in env_vars]

    return Package(
        registry_type="oci",
        registry_base_url=AnyUrl("https://docker.io"),
        identifier=f"knitli/codeweaver:{__version__}",
        runtime_hint="docker",
        transport=StreamableHttpTransport(
            type_=StreamableHttpTransportType.streamable_http,
            url="http://localhost:{host_port}",
        ),
        runtime_arguments=[
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--rm",
                description="Automatically remove container when it exits",
                is_required=False,
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="-v",
                description="Mount workspace directory as read-only",
                is_required=False,
                value="{workspace}:/workspace:ro",
                variables={
                    "workspace": Input(
                        description="Path to your codebase to index and search",
                        is_required=True,
                    )
                },
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="-e",
                description="Set repository path inside container",
                is_required=False,
                value="CODEWEAVER_PROJECT_PATH=/workspace",
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="-p",
                description="Port mapping for MCP server",
                is_required=False,
                value="{host_port}:9328",
                variables={
                    "host_port": Input(
                        description="Host port to expose MCP server",
                        default="9328",
                    )
                },
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--network",
                description="Docker network for Qdrant connectivity",
                is_required=False,
                value="{network}",
                variables={
                    "network": Input(
                        description="Docker network name (use 'host' for local Qdrant or custom network)",
                        default="bridge",
                    )
                },
            ),
        ],
        package_arguments=[
            # Subcommand
            PositionalArgument(
                type_=PositionalArgumentType.positional,
                description="Start CodeWeaver MCP server",
                value="server",
            ),
            # Server command flags (from server.py CLI)
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--host",
                description="Bind to all interfaces in container",
                value="0.0.0.0", # noqa: S104
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--port",
                description="MCP server port inside container",
                value="9328",
            ),
            NamedArgument(
                type_=NamedArgumentType.named,
                name="--transport",
                description="Use streamable-http for persistent state and continuous indexing",
                value="streamable-http",
            ),
        ],
        environment_variables=as_keyvalues,
    )


def _create_field_meta() -> FieldMeta:
    """Create the _meta field with capabilities and build info."""
    caps = capabilities()

    # Add tags based on capabilities
    tags = [
        "agent-tools",
        "ast-parsing",
        "code-search",
        "code-understanding",
        "developer-tools",
        "embeddings",
        "hybrid-search",
        "multi-language",
        "natural-language-processing",
        "reranking",
        "semantic-search",
        "sparse-embeddings",
        "vector-database",
    ]

    # Add search types
    caps["search_types"] = ["semantic", "hybrid", "traditional"]

    # Add chunking strategies
    caps["chunking_strategies"] = ["semantic", "semantically-aware-delimiters"]

    return FieldMeta(
        io_modelcontextprotocol_registry_publisher_provided={
            "build_info": {
                "framework": "fastmcp",
                "package_manager": "uv",
                "python_version": ">=3.12",
            },
            "capabilities": caps,
            "tags": tags,
            "all_supported_languages": _languages(),
        }
    )


def generate_server_detail() -> ServerDetail:
    """Generate the complete ServerDetail object from code."""
    return ServerDetail(
        field_schema=AnyUrl("https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json"),
        name="com.knitli/codeweaver",
        description=f"Semantic code search built for AI agents. Hybrid AST-aware context for {len(_languages())} languages.",
        title="CodeWeaver - Code Search for AI Agents",
        version=__version__,
        repository=REPOSITORY,
        website_url=AnyUrl("https://github.com/knitli/codeweaver"),
        packages=[_create_uvx_package(), _create_docker_package()],
        field_meta=_create_field_meta(),
    )


def validate_against_official_schema(server_detail: ServerDetail) -> None:
    """Validate the generated server.json against the official MCP schema.

    Args:
        server_detail: The ServerDetail object to validate

    Raises:
        ValueError: If validation fails with details about the validation errors
    """
    import json

    import httpx

    from jsonschema import Draft202012Validator, ValidationError

    # Get schema URL from the server detail
    schema_url = str(server_detail.field_schema)

    print(f"🔍 Fetching official schema from {schema_url}...")

    try:
        # Fetch the official schema
        response = httpx.get(schema_url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        schema = response.json()

        print("✅ Schema fetched successfully")
    except httpx.HTTPError as e:
        raise ValueError(f"Failed to fetch schema from {schema_url}: {e}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON schema at {schema_url}: {e}") from e

    # Convert server_detail to dict for validation
    server_json = json.loads(
        server_detail.model_dump_json(
            by_alias=True,
            exclude_none=True,
        )
    )

    print("🔍 Validating against official MCP schema...")

    # Create validator and check
    validator = Draft202012Validator(schema)

    try:
        if errors := list(validator.iter_errors(server_json)):
            error_messages = []
            for error in errors:
                path = " → ".join(str(p) for p in error.path) if error.path else "root"
                error_messages.append(f"  • {path}: {error.message}")

            raise ValueError(
                f"Schema validation failed with {len(errors)} error(s):\n" + "\n".join(error_messages)
            )

        print("✅ Schema validation passed")

    except ValidationError as e:
        path = " → ".join(str(p) for p in e.path) if e.path else "root"
        raise ValueError(f"Schema validation failed at {path}: {e.message}") from e


def save_server_detail(server_detail: ServerDetail | None = None) -> Path:
    """Save the generated server detail to server.json."""
    if server_detail is None:
        server_detail = generate_server_detail()

    file_path = Path(__file__).parent.parent.parent / "server.json"

    # Write with proper formatting
    json_content = server_detail.model_dump_json(
        by_alias=True,
        exclude_none=True,
        indent=2,
    )

    file_path.write_text(json_content + "\n")
    return file_path


if __name__ == "__main__":
    import sys

    # Generate the server.json
    print("🔄 Generating server.json from code...")
    try:
        server_detail = generate_server_detail()
        assert server_detail is not None  # noqa: S101
        # Validate against official schema before saving
        validate_against_official_schema(server_detail)
        assert server_detail.field_meta.io_modelcontextprotocol_registry_publisher_provided is not None  # noqa: S101
        # Save to file
        file_path = save_server_detail(server_detail)
        print(f"✅ Successfully generated server.json at {file_path}")
        print(f"📦 Version: {__version__}")
        print(f"🌐 Languages supported: {server_detail.field_meta.io_modelcontextprotocol_registry_publisher_provided['capabilities']['languages_supported']}")
        print(f"🔧 Embedding providers: {', '.join(server_detail.field_meta.io_modelcontextprotocol_registry_publisher_provided['capabilities']['embedding_providers'])}")
        print(f"💾 Vector stores: {', '.join(server_detail.field_meta.io_modelcontextprotocol_registry_publisher_provided['capabilities']['vector_store_providers'])}")
    except Exception as e:
        print(f"❌ Error generating server.json: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)

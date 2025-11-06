# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Types for the registry package."""

from __future__ import annotations

from collections.abc import Callable
from enum import IntFlag, auto
from typing import Annotated, Any, Literal, NotRequired, Required, TypedDict, override

from pydantic import ConfigDict, Field, computed_field

from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.models import BasedModel
from codeweaver.providers.provider import ProviderKind


type ServiceName = Annotated[
    str,
    Field(description="""The name of the service""", max_length=100, pattern=r"^[a-zA-Z0-9_]+$"),
]

type LiteralKinds = Literal[
    ProviderKind.AGENT,
    "agent",
    ProviderKind.DATA,
    "data",
    ProviderKind.EMBEDDING,
    "embedding",
    ProviderKind.SPARSE_EMBEDDING,
    "sparse_embedding",
    ProviderKind.RERANKING,
    "reranking",
    ProviderKind.VECTOR_STORE,
    "vector_store",
]

type LiteralModelKinds = Literal[
    ProviderKind.AGENT,
    "agent",
    ProviderKind.EMBEDDING,
    "embedding",
    ProviderKind.SPARSE_EMBEDDING,
    "sparse_embedding",
    ProviderKind.RERANKING,
    "reranking",
]

type LiteralDataKinds = Literal[ProviderKind.DATA, "data"]

type LiteralVectorStoreKinds = Literal[ProviderKind.VECTOR_STORE, "vector_store"]


@override
class Feature(IntFlag, BaseEnum):  # pyright: ignore[reportIncompatibleVariableOverride, reportIncompatibleMethodOverride]
    # We intentionally override BaseEnum here to get the IntFlag behavior where they overlap
    """Features supported by the CodeWeaver server.

    `Feature` uses `IntFlag` to allow bitwise operations to resolve dependencies and available feature sets.

    Example usage:
    ```python
    # merge features
    requested_features = Feature.HYBRID_SEARCH | Feature.RERANKING
    print(f"Requested: {requested_features}")

    # Get all required features including dependencies
    required = requested_features.resolve_all_dependencies()
    print(f"Required (with deps): {required}")

    # Check what's missing
    current_features = Feature.FILE_DISCOVERY | Feature.BASIC_SEARCH
    # calculate difference
    missing = required & ~current_features
    print(f"Missing: {missing}")

    # Validate a configuration
    config = Feature.VECTOR_SEARCH | Feature.BASIC_SEARCH | Feature.FILE_DISCOVERY
    print(f"Config valid: {config.validate_dependencies()}")

    # Get minimal set for specific features
    minimal = Feature.minimal_set_for(Feature.PRECONTEXT_AGENT)
    print(f"Minimal for PRECONTEXT_AGENT: {minimal}")
    ```
    """

    # Infrastructure
    FILE_DISCOVERY = auto()
    FILE_FILTER = auto()
    FILE_WATCHER = auto()
    LOGGING = auto()
    HEALTH = auto()
    ERROR_HANDLING = auto()
    RATE_LIMITING = auto()
    STATISTICS = auto()

    # Indexing
    SPARSE_INDEXING = auto()
    VECTOR_INDEXING = auto()
    AUTOMATIC_INDEXING = auto()

    # Search
    BASIC_SEARCH = auto()
    SEMANTIC_SEARCH = auto()
    VECTOR_SEARCH = auto()
    HYBRID_SEARCH = auto()
    RERANKING = auto()

    # AI/Agents
    AGENT = auto()
    MCP_CONTEXT_AGENT = auto()
    PRECONTEXT_AGENT = auto()
    WEB_SEARCH = auto()

    UNKNOWN = auto()

    @classmethod
    def get_dependencies(cls, feature: Feature) -> set[Feature]:
        """Get individual feature dependencies."""
        deps = {
            cls.BASIC_SEARCH: {cls.FILE_DISCOVERY},
            cls.SEMANTIC_SEARCH: {cls.BASIC_SEARCH},
            cls.VECTOR_SEARCH: {cls.BASIC_SEARCH, cls.VECTOR_INDEXING},
            cls.HYBRID_SEARCH: {cls.SPARSE_INDEXING, cls.VECTOR_INDEXING, cls.BASIC_SEARCH},
            cls.RERANKING: {cls.BASIC_SEARCH, cls.VECTOR_SEARCH},
            cls.AUTOMATIC_INDEXING: {cls.FILE_DISCOVERY, cls.FILE_WATCHER},
            cls.FILE_WATCHER: {cls.FILE_DISCOVERY, cls.FILE_FILTER},
            cls.MCP_CONTEXT_AGENT: {cls.VECTOR_SEARCH, cls.RERANKING},
            cls.PRECONTEXT_AGENT: {cls.VECTOR_SEARCH, cls.RERANKING, cls.AGENT},
            cls.WEB_SEARCH: {cls.AGENT},
        }
        return deps.get(feature, set())

    def resolve_all_dependencies(self) -> Feature:
        """Resolve all dependencies for the enabled features."""
        resolved = Feature(0)
        to_process = {
            feature for feature in Feature if feature in self and feature != Feature.UNKNOWN
        }
        # Recursively resolve dependencies
        while to_process:
            feature = to_process.pop()
            if feature not in resolved:
                resolved |= feature
                # Add dependencies to process
                deps = self.get_dependencies(feature)
                to_process.update(deps - set(resolved))

        return resolved

    def validate_dependencies(self) -> bool:
        """Check if all dependencies are satisfied."""
        resolved = self.resolve_all_dependencies()
        return (resolved & self) == resolved

    def missing_dependencies(self) -> Feature:
        """Get the missing dependencies."""
        resolved = self.resolve_all_dependencies()
        return resolved & ~self

    @classmethod
    def minimal_set_for(cls, *features: Feature) -> Feature:
        """Get minimal feature set including dependencies."""
        requested = cls(0)
        for feature in features:
            requested |= feature
        return requested.resolve_all_dependencies()


class ServiceCardDict(TypedDict, total=False):
    """Dictionary representing a service and its status."""

    name: Required[ServiceName]
    provider_kind: Required[ProviderKind]
    feature: Required[
        Feature
        | Literal[
            "agent",
            "automatic indexing",
            "basic search",
            "error handling",
            "file discovery",
            "file filter",
            "file watcher",
            "health",
            "hybrid search",
            "logging",
            "mcp context agent",
            "precontext agent",
            "rate limiting",
            "reranking",
            "semantic search",
            "sparse indexing",
            "statistics",
            "vector indexing",
            "vector search",
            "web search",
        ]
    ]
    base_class: Required[type]
    import_path: Required[str]
    enabled: Required[bool]
    dependencies: NotRequired[list[Feature] | None]

    status_hook: NotRequired[Callable[..., Any] | None]
    instance: NotRequired[Any | None]


class ServiceCard(BasedModel):
    """Card representing a service and its status."""

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True, defer_build=True)

    name: ServiceName
    feature: Annotated[Feature, Field(description="""The feature enum identifier""")]
    base_class: type
    import_path: str
    enabled: bool
    dependencies: list[Feature]

    status_hook: Annotated[
        Callable[..., Any] | None, Field(description="""Hook to call for status updates""")
    ] = None
    instance: Annotated[Any | None, Field(description="""The service instance""")] = None

    def _telemetry_keys(self) -> None:
        return None

    @classmethod
    def from_dict(cls, data: ServiceCardDict) -> ServiceCard:
        """Create a ServiceCard from a dictionary."""
        if isinstance(data["feature"], str):
            data["feature"] = Feature.from_string(data["feature"])
        dependencies = data.get("dependencies", [])  # type: ignore
        return cls(**{**data, "dependencies": dependencies})  # type: ignore

    @computed_field
    @property
    def fully_available(self) -> bool:
        """Check if the service is fully available (enabled and dependencies met)."""
        return self.enabled and all(
            dep in Feature(0) or dep in self.dependencies for dep in self.dependencies
        )


__all__ = ("Feature", "ServiceCard", "ServiceCardDict", "ServiceName")

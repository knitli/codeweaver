"""Annotated getters for dependency injection of core dependencies."""

from codeweaver.core.types import LiteralProviderKind, SDKClient


dependency_provider(SDKClient)


def get_sdk_client(kind: LiteralProviderKind) -> SDKClient:
    """Get the SDK client dependency."""
    return get_client()

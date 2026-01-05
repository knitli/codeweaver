"""Provider configuration exports."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.config.providers import ProviderSettings
    from codeweaver.providers.config.root_settings import CodeWeaverProviderSettings


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CodeWeaverProviderSettings": (__spec__.parent, "root_settings"),
    "ProviderSettings": (__spec__.parent, "providers"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "CodeWeaverProviderSettings",
    "ProviderSettings",
)


def __dir__() -> list[str]:
    return list(__all__)

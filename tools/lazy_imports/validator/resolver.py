"""Import resolution logic for lazy import validation.

Resolves imports to verify they exist and are correctly specified.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import sys

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..common.types import ImportResolution


class ImportResolver:
    """Resolves imports to validate correctness.

    Uses Python's import machinery to check if imports will work at runtime.
    """

    def __init__(self, project_root: Path) -> None:
        """Initialize resolver.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self._src_path = project_root / "src"
        if self._src_path.exists() and str(self._src_path) not in sys.path:
            sys.path.insert(0, str(self._src_path))

    def resolve_import(self, module: str, obj: str | None = None) -> ImportResolution:
        """Resolve an import to check if it exists.

        Args:
            module: Module path (e.g., 'codeweaver.core.chunks')
            obj: Object name (e.g., 'CodeChunk'), None for module-level

        Returns:
            ImportResolution with exists=True if import works
        """
        from ..common.types import ImportResolution

        try:
            mod = importlib.import_module(module)
        except ImportError as e:
            return ImportResolution(
                module=module,
                obj=obj or "",
                exists=False,
                path=None,
                error=f"Module not found: {e}",
            )
        except Exception as e:
            return ImportResolution(
                module=module,
                obj=obj or "",
                exists=False,
                path=None,
                error=f"Error importing module: {e}",
            )
        if obj is None:
            return ImportResolution(
                module=module, obj="", exists=True, path=self._get_module_path(mod), error=None
            )
        if not hasattr(mod, obj):
            return ImportResolution(
                module=module,
                obj=obj,
                exists=False,
                path=self._get_module_path(mod),
                error=f"Object '{obj}' not found in module '{module}'",
            )
        return ImportResolution(
            module=module, obj=obj, exists=True, path=self._get_module_path(mod), error=None
        )

    def _get_module_path(self, module) -> Path | None:
        """Get the file path for a module.

        Args:
            module: Imported module object

        Returns:
            Path to module file, or None if not found
        """
        with contextlib.suppress(Exception):
            if hasattr(module, "__file__") and module.__file__:
                return Path(module.__file__)
        return None

    def resolve_lazy_import(self, module: str, obj: str) -> ImportResolution:
        """Resolve a lazy_import(module, obj) call.

        Args:
            module: Module path
            obj: Object name

        Returns:
            ImportResolution with exists=True if valid
        """
        return self.resolve_import(module, obj)

    def check_type_checking_import(self, module: str, obj: str) -> bool:
        """Check if an import is valid for TYPE_CHECKING.

        TYPE_CHECKING imports are only loaded by type checkers, so we verify
        they exist without trying to import them at runtime.

        Args:
            module: Module path
            obj: Object name

        Returns:
            True if import is valid for TYPE_CHECKING
        """
        try:
            spec = importlib.util.find_spec(module)
            if spec is None:
                return False
        except (ImportError, ModuleNotFoundError, ValueError):
            return False
        else:
            return True

    def validate_package_consistency(self, package: str) -> list[str]:
        """Validate package __all__ exports exist.

        Args:
            package: Package path (e.g., 'codeweaver.core')

        Returns:
            List of missing exports (empty if all exist)
        """
        missing = []
        try:
            mod = importlib.import_module(package)
        except ImportError:
            return [f"Package '{package}' not found"]
        all_exports = getattr(mod, "__all__", [])
        missing.extend(f"{package}.{name}" for name in all_exports if not hasattr(mod, name))
        return missing

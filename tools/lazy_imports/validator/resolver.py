# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Import resolution for validation.

Resolves import statements to verify they are valid and accessible.
"""

from __future__ import annotations

import importlib.util

from pathlib import Path

from tools.lazy_imports.common.types import ImportResolution


class ImportResolver:
    """Resolves imports to verify they exist and are accessible.

    Caches resolution results for efficiency.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize resolver.

        Args:
            project_root: Root directory of the project for relative imports
        """
        self.project_root = project_root or Path.cwd()
        self._cache: dict[tuple[str, str], ImportResolution] = {}

    def resolve(self, module: str, obj: str) -> ImportResolution:
        """Resolve import to verify module and object exist.

        Args:
            module: Module path (e.g., "pathlib")
            obj: Object name (e.g., "Path")

        Returns:
            ImportResolution with exists=True if valid, False otherwise
        """
        cache_key = (module, obj)

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try to import the module
        try:
            # Check if module exists
            spec = importlib.util.find_spec(module)
            if spec is None:
                result = ImportResolution(
                    module=module,
                    obj=obj,
                    exists=False,
                    path=None,
                    error=f"Module '{module}' not found",
                )
                self._cache[cache_key] = result
                return result

            # Module exists, try to import it
            try:
                mod = importlib.import_module(module)

                # Check if object exists in module
                if not hasattr(mod, obj):
                    result = ImportResolution(
                        module=module,
                        obj=obj,
                        exists=False,
                        path=Path(spec.origin) if spec.origin else None,
                        error=f"Object '{obj}' not found in module '{module}'",
                    )
                    self._cache[cache_key] = result
                    return result

                # Success - both module and object exist
                result = ImportResolution(
                    module=module,
                    obj=obj,
                    exists=True,
                    path=Path(spec.origin) if spec.origin else None,
                    error=None,
                )
                self._cache[cache_key] = result

            except Exception as e:
                # Module found but import failed
                result = ImportResolution(
                    module=module,
                    obj=obj,
                    exists=False,
                    path=Path(spec.origin) if spec.origin else None,
                    error=f"Failed to import module '{module}': {e}",
                )
                self._cache[cache_key] = result
                return result
            else:
                return result

        except Exception as e:
            # Module lookup failed
            result = ImportResolution(
                module=module,
                obj=obj,
                exists=False,
                path=None,
                error=f"Failed to resolve module '{module}': {e}",
            )
            self._cache[cache_key] = result
            return result


__all__ = ["ImportResolver"]

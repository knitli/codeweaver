# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from pathlib import Path
from typing import Any

from rignore import Walker

from codeweaver.settings import FileFilterSettings


class FileFilter(Walker):
    def __init__(
        self, project_path: Path, settings: FileFilterSettings, **kwargs: dict[str, Any] | None
    ) -> None:
        super().__init__(project_path, **dict(settings))

    def adjust_settings(
        self, settings: FileFilterSettings, **kwargs: FileFilterSettings | dict[str, Any] | None
    ) -> FileFilterSettings:
        """Adjusts a few settings, primarily to reform keywords. `rignore`'s choice of keywords is a bit odd, so we wrapped them in clearer alternatives."""
        return FileFilterSettings.model_validate({
            "forced_includes": None,
            "excludes": "additional_ignores",
            "excluded_extensions": "additional_ignores",
            "use_gitignore": "read_git_ignore",
            "use_other_ignore_files": "read_ignore_files",
            "ignore_hidden": "ignore_hidden",
            **settings.model_dump(),
            **(kwargs or {}),
        })


__all__ = ("FileFilter",)

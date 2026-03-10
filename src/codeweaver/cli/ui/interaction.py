# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""User interaction abstractions for CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Protocol, runtime_checkable

from codeweaver.core.di import depends


if TYPE_CHECKING:
    from rich.console import Console


@runtime_checkable
class UserInteraction(Protocol):
    """Protocol for user interaction."""

    def confirm(self, message: str, *, default: bool = False) -> bool:
        """Ask for confirmation.

        Args:
            message: The message to display.
            default: The default value if the user just presses enter.

        Returns:
            True if the user confirmed, False otherwise.
        """
        ...


class RichUserInteraction:
    """Rich-based user interaction implementation."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize with an optional rich console."""
        self._console = console

    def confirm(self, message: str, *, default: bool = False) -> bool:
        """Ask for confirmation using rich.prompt.Confirm."""
        from rich.prompt import Confirm

        return Confirm.ask(message, default=default, console=self._console)


def _get_default_interaction() -> UserInteraction:
    """Default interaction factory."""
    from codeweaver.core._logging import get_rich_console

    return RichUserInteraction(console=get_rich_console())


type UserInteractionDep = Annotated[UserInteraction, depends(_get_default_interaction)]


__all__ = ("RichUserInteraction", "UserInteraction", "UserInteractionDep")

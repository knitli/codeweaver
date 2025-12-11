# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Types for environment variable definitions."""

from typing import Any, NamedTuple

from codeweaver.core.types.enum import BaseEnum


class EnvFormat(BaseEnum):
    """Supported data formats for MCP server inputs and outputs."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    FILEPATH = "filepath"


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

    def as_mcp_info(self) -> dict[str, Any]:
        """Convert to MCP server JSON format."""
        return {
            k: v
            for k, v in self._asdict().items()
            if k not in {"variable_name", "env"} and v is not None
        } | {"name": self.env}

    def as_kwarg(self) -> dict[str, str | None]:
        """Convert to a keyword argument string."""
        import os

        return {f"{self.variable_name or self.env}": os.getenv(self.env)}

    def as_docker_yaml(self) -> None:
        """TODO: Convert to Docker MCP Registry YAML format."""


__all__ = ("EnvFormat", "EnvVarInfo")

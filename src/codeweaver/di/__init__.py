# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency Injection for CodeWeaver.

Provides a FastAPI-inspired declarative injection system.
"""

from codeweaver.di.container import Container, get_container
from codeweaver.di.depends import INJECTED, Depends, DependsPlaceholder, depends


__all__ = ("INJECTED", "Container", "Depends", "DependsPlaceholder", "depends", "get_container")

# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Exceptions for providers."""

from __future__ import annotations

from codeweaver.core import ProviderError


class CircuitBreakerOpenError(ProviderError):
    """Raised when circuit breaker is open and rejecting requests."""


__all__ = (CircuitBreakerOpenError,)

"""We separate circuit breaker here because this keeps the universe from imploding. Or, circular imports, at least."""

from __future__ import annotations

from codeweaver.core.types import BaseEnum


class CircuitBreakerState(BaseEnum):
    """Circuit breaker states for provider resilience."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


__all__ = ("CircuitBreakerState",)

# app/engine/cost_tracker.py
from __future__ import annotations


class CostLimitExceeded(Exception):
    """Raised when adding cost would breach a configured limit."""


class CostTracker:
    """Accumulates cost for a workflow execution and enforces per-execution and daily limits."""

    def __init__(self, max_per_execution: float, max_per_day: float) -> None:
        self._max_per_execution = max_per_execution
        self._max_per_day = max_per_day
        self._total: float = 0.0
        self._daily_total: float = 0.0

    @property
    def total(self) -> float:
        return self._total

    def set_daily_total(self, daily_total: float) -> None:
        """Inject the tenant's daily accumulated cost from an external source (e.g. Redis)."""
        self._daily_total = daily_total

    def add(self, cost: float) -> None:
        """Add cost. Raises CostLimitExceeded if either limit would be breached.
        Does NOT mutate state if a limit would be exceeded.
        Execution limit is checked before daily limit — a dual-breach raises the execution error.
        """
        new_total = self._total + cost
        new_daily = self._daily_total + cost

        if new_total > self._max_per_execution:
            raise CostLimitExceeded(
                f"Cost ${new_total:.4f} exceeds per-execution limit ${self._max_per_execution:.2f}"
            )
        if new_daily > self._max_per_day:
            raise CostLimitExceeded(
                f"Daily cost ${new_daily:.4f} exceeds daily limit ${self._max_per_day:.2f}"
            )
        # Only mutate after all checks pass
        self._total = new_total
        self._daily_total = new_daily

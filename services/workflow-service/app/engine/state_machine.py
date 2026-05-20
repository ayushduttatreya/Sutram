from __future__ import annotations
from sutram_core.models.execution import ExecutionStatus

# Valid transitions: {current_status: {trigger: next_status}}
_TRANSITIONS: dict[ExecutionStatus, dict[str, ExecutionStatus]] = {
    ExecutionStatus.PENDING: {
        "submit": ExecutionStatus.RUNNING,
    },
    ExecutionStatus.RUNNING: {
        "all_steps_done": ExecutionStatus.COMPLETED,
        "error": ExecutionStatus.PAUSED,
        "cost_exceeded": ExecutionStatus.PAUSED,
        "manual_pause": ExecutionStatus.PAUSED,
        "fatal_error": ExecutionStatus.FAILED,
        "max_retries_exceeded": ExecutionStatus.FAILED,
    },
    ExecutionStatus.PAUSED: {
        "resume": ExecutionStatus.RUNNING,
        "cancel": ExecutionStatus.CANCELLED,
    },
    # COMPLETED, FAILED, CANCELLED are terminal — no valid outbound transitions
}


class InvalidTransitionError(Exception):
    """Raised when a state transition is not valid for the current status."""


class ExecutionFSM:
    """Finite state machine for workflow execution status."""

    def __init__(self, current_status: ExecutionStatus) -> None:
        self._status = current_status

    @property
    def status(self) -> ExecutionStatus:
        return self._status

    def transition(self, trigger: str) -> ExecutionStatus:
        """Apply trigger and return the new status. Raises InvalidTransitionError if invalid."""
        valid = _TRANSITIONS.get(self._status, {})
        if trigger not in valid:
            raise InvalidTransitionError(
                f"Cannot apply trigger '{trigger}' to execution in state '{self._status.value}'. "
                f"Valid triggers: {list(valid.keys()) or 'none (terminal state)'}"
            )
        self._status = valid[trigger]
        return self._status

    def can_transition(self, trigger: str) -> bool:
        return trigger in _TRANSITIONS.get(self._status, {})

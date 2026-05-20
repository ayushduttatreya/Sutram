import pytest
from sutram_core.models.execution import ExecutionStatus
from app.engine.state_machine import ExecutionFSM, InvalidTransitionError


def test_pending_to_running():
    fsm = ExecutionFSM(ExecutionStatus.PENDING)
    new_status = fsm.transition("submit")
    assert new_status == ExecutionStatus.RUNNING


def test_running_to_completed():
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    assert fsm.transition("all_steps_done") == ExecutionStatus.COMPLETED


def test_running_to_paused_on_error():
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    assert fsm.transition("error") == ExecutionStatus.PAUSED


def test_running_to_paused_on_cost_exceeded():
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    assert fsm.transition("cost_exceeded") == ExecutionStatus.PAUSED


def test_running_to_paused_on_manual_pause():
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    assert fsm.transition("manual_pause") == ExecutionStatus.PAUSED


def test_running_to_failed_on_fatal_error():
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    assert fsm.transition("fatal_error") == ExecutionStatus.FAILED


def test_running_to_failed_on_max_retries():
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    assert fsm.transition("max_retries_exceeded") == ExecutionStatus.FAILED


def test_paused_to_running_on_resume():
    fsm = ExecutionFSM(ExecutionStatus.PAUSED)
    assert fsm.transition("resume") == ExecutionStatus.RUNNING


def test_paused_to_cancelled_on_cancel():
    fsm = ExecutionFSM(ExecutionStatus.PAUSED)
    assert fsm.transition("cancel") == ExecutionStatus.CANCELLED


def test_invalid_transition_raises():
    fsm = ExecutionFSM(ExecutionStatus.COMPLETED)
    with pytest.raises(InvalidTransitionError):
        fsm.transition("submit")


def test_cannot_cancel_running_execution():
    """RUNNING -> CANCELLED is invalid. Must pause first."""
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    with pytest.raises(InvalidTransitionError):
        fsm.transition("cancel")


def test_cannot_resume_completed_execution():
    fsm = ExecutionFSM(ExecutionStatus.COMPLETED)
    with pytest.raises(InvalidTransitionError):
        fsm.transition("resume")


def test_invalid_transition_error_includes_state_and_trigger():
    fsm = ExecutionFSM(ExecutionStatus.PENDING)
    with pytest.raises(InvalidTransitionError) as exc:
        fsm.transition("cancel")
    assert "PENDING" in str(exc.value)
    assert "cancel" in str(exc.value)


def test_fsm_status_property_reflects_current_state():
    fsm = ExecutionFSM(ExecutionStatus.PENDING)
    assert fsm.status == ExecutionStatus.PENDING
    fsm.transition("submit")
    assert fsm.status == ExecutionStatus.RUNNING


def test_can_transition_returns_true_for_valid():
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    assert fsm.can_transition("error") is True


def test_can_transition_returns_false_for_invalid():
    fsm = ExecutionFSM(ExecutionStatus.COMPLETED)
    assert fsm.can_transition("submit") is False


def test_can_transition_returns_false_for_wrong_trigger_in_non_terminal_state():
    """Non-terminal state with wrong trigger — not just terminal state default."""
    fsm = ExecutionFSM(ExecutionStatus.RUNNING)
    assert fsm.can_transition("cancel") is False  # RUNNING has transitions but not 'cancel'

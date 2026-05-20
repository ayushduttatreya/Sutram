import pytest
from app.engine.cost_tracker import CostLimitExceeded, CostTracker


def test_tracker_starts_at_zero():
    tracker = CostTracker(max_per_execution=10.0, max_per_day=100.0)
    assert tracker.total == 0.0


def test_add_cost_accumulates():
    tracker = CostTracker(max_per_execution=10.0, max_per_day=100.0)
    tracker.add(0.5)
    tracker.add(0.3)
    assert abs(tracker.total - 0.8) < 1e-9


def test_exceeds_per_execution_limit_raises():
    tracker = CostTracker(max_per_execution=1.0, max_per_day=100.0)
    tracker.add(0.9)
    with pytest.raises(CostLimitExceeded, match="execution"):
        tracker.add(0.2)  # total would be 1.1 > 1.0


def test_at_exact_limit_does_not_raise():
    tracker = CostTracker(max_per_execution=1.0, max_per_day=100.0)
    tracker.add(1.0)  # exactly at limit — should not raise


def test_exceeds_per_day_limit_raises():
    tracker = CostTracker(max_per_execution=1000.0, max_per_day=5.0)
    tracker.add(4.9)
    with pytest.raises(CostLimitExceeded, match="daily"):
        tracker.add(0.2)


def test_set_daily_total_affects_day_check():
    tracker = CostTracker(max_per_execution=1000.0, max_per_day=10.0)
    tracker.set_daily_total(9.5)  # inject external daily total
    with pytest.raises(CostLimitExceeded, match="daily"):
        tracker.add(0.6)  # 9.5 + 0.6 = 10.1 > 10.0


def test_total_not_mutated_on_failed_add():
    """If add raises, the tracker total must NOT be modified."""
    tracker = CostTracker(max_per_execution=1.0, max_per_day=100.0)
    tracker.add(0.9)
    with pytest.raises(CostLimitExceeded):
        tracker.add(0.2)
    assert abs(tracker.total - 0.9) < 1e-9  # unchanged


def test_dual_breach_raises_execution_error_first():
    """When both limits would be exceeded, execution limit takes precedence."""
    tracker = CostTracker(max_per_execution=1.0, max_per_day=1.0)
    tracker.add(0.9)
    tracker.set_daily_total(0.9)
    with pytest.raises(CostLimitExceeded, match="execution"):
        tracker.add(0.2)  # both 0.9+0.2=1.1 > 1.0 execution AND daily

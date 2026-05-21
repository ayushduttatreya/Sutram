from app.models.orm import ExecutionTraceORM, AuditLogORM


def test_tablenames():
    assert ExecutionTraceORM.__tablename__ == "execution_traces"
    assert AuditLogORM.__tablename__ == "audit_log"


def test_execution_trace_has_required_columns():
    cols = {c.key for c in ExecutionTraceORM.__table__.columns}
    required = {"id", "trace_id", "execution_id", "tenant_id", "workflow_id",
                "event_type", "start_time", "step_name", "step_index",
                "duration_ms", "cost_usd", "status", "error_type", "error_message"}
    assert required.issubset(cols)


def test_audit_log_has_no_updated_at():
    """Audit log is append-only — no updated_at column."""
    cols = {c.key for c in AuditLogORM.__table__.columns}
    assert "timestamp" in cols
    assert "updated_at" not in cols
    assert "created_at" not in cols


def test_execution_trace_has_brin_index():
    """BRIN index on start_time for time-range queries."""
    index_names = {idx.name for idx in ExecutionTraceORM.__table__.indexes}
    assert "idx_traces_start_time_brin" in index_names


def test_both_tables_have_tenant_id():
    for model in [ExecutionTraceORM, AuditLogORM]:
        cols = {c.key for c in model.__table__.columns}
        assert "tenant_id" in cols, f"{model.__tablename__} missing tenant_id"


def test_audit_log_column_names_and_python_attr():
    """Verify metadata DB column name and extra_metadata Python attr mapping."""
    cols_by_key = {c.key: c.name for c in AuditLogORM.__table__.columns}
    # DB column is named "metadata" (reserved attr name worked around with name= param)
    assert "metadata" in cols_by_key
    assert cols_by_key["metadata"] == "metadata"
    # Python attribute is extra_metadata
    assert hasattr(AuditLogORM, "extra_metadata")

from app.models.orm import MemoryItemORM, MemorySummaryORM
from sqlalchemy import inspect


def test_tablenames():
    assert MemoryItemORM.__tablename__ == "memory_items"
    assert MemorySummaryORM.__tablename__ == "memory_summaries"


def test_memory_item_has_required_columns():
    col_keys = {a.key for a in inspect(MemoryItemORM).mapper.column_attrs}  # Python attr names
    col_names = {c.name for c in MemoryItemORM.__table__.columns}  # DB column names

    # Check Python attr names
    required_keys = {
        "id",
        "tenant_id",
        "memory_type",
        "content",
        "embedding",
        "embedding_model",
        "extra_metadata",
        "accessed_at",
        "access_count",
        "retention_policy",
        "compressed",
        "created_at",
        "updated_at",
    }
    assert required_keys.issubset(col_keys)

    # Check DB column name (metadata is reserved in SA, mapped as extra_metadata Python attr)
    assert "metadata" in col_names


def test_metadata_python_attr_is_extra_metadata():
    """'metadata' is reserved by DeclarativeBase — mapped as extra_metadata Python attr."""
    col_keys = {a.key for a in inspect(MemoryItemORM).mapper.column_attrs}  # Python attr names
    col_names = {c.name for c in MemoryItemORM.__table__.columns}  # DB column names
    assert "extra_metadata" in col_keys  # Python attr name
    assert "metadata" in col_names  # DB column name
    assert "metadata" not in col_keys  # NOT accessible as .metadata (that's SA MetaData)


def test_memory_item_has_check_constraint():
    constraints = {c.name for c in MemoryItemORM.__table__.constraints}
    assert "ck_memory_type" in constraints


def test_memory_summary_has_original_ids():
    cols = {c.key for c in MemorySummaryORM.__table__.columns}
    assert "original_ids" in cols
    assert "embedding_model" in cols


def test_both_tables_have_tenant_id():
    for model in [MemoryItemORM, MemorySummaryORM]:
        cols = {c.key for c in model.__table__.columns}
        assert "tenant_id" in cols, f"{model.__tablename__} missing tenant_id"

from backend.models.campaign import Base
from backend.schema_upgrade import plan_schema_upgrade


def _legacy_campaign_columns():
    """An older volume: required max_results, and none of the newer columns."""
    kept = ["id", "query", "location", "lat", "lng", "radius", "min_rating", "status", "total_leads", "created_at"]
    rows = [
        {"table_name": "campaigns", "column_name": name, "is_nullable": "NO" if name in {"id", "query", "location", "max_results"} else "YES"}
        for name in kept
    ]
    rows.append({"table_name": "campaigns", "column_name": "max_results", "is_nullable": "NO"})
    return rows


def test_legacy_max_results_is_relaxed_and_rows_are_kept():
    statements = plan_schema_upgrade(Base.metadata, _legacy_campaign_columns())
    text = "\n".join(statements)
    assert 'ALTER COLUMN "max_results" DROP NOT NULL' in text
    assert "DROP TABLE" not in text
    assert "DELETE FROM" not in text
    assert "DROP COLUMN" not in text
    assert 'ADD COLUMN IF NOT EXISTS "status_detail" TEXT' in text
    assert 'ADD COLUMN IF NOT EXISTS "min_reviews" INTEGER' in text
    assert 'ADD COLUMN IF NOT EXISTS "max_reviews" INTEGER' in text
    assert 'ADD COLUMN IF NOT EXISTS "sheet_url" VARCHAR(500)' in text
    assert 'ALTER COLUMN "query" DROP NOT NULL' not in text
    assert 'ALTER COLUMN "id" DROP NOT NULL' not in text


def test_upgrade_is_idempotent_once_the_legacy_column_is_optional():
    rows = _legacy_campaign_columns()
    for name in ("status_detail", "sheet_url", "min_reviews", "max_reviews", "emailed_leads", "updated_at"):
        rows.append({"table_name": "campaigns", "column_name": name, "is_nullable": "YES"})
    for row in rows:
        if row["column_name"] == "max_results":
            row["is_nullable"] = "YES"
    # Current model columns that the first fixture omitted, marked as already present.
    for column in Base.metadata.tables["campaigns"].columns:
        if column.name not in {row["column_name"] for row in rows}:
            rows.append({"table_name": "campaigns", "column_name": column.name, "is_nullable": "YES"})
    statements = plan_schema_upgrade(Base.metadata, rows)
    campaign_sql = [item for item in statements if '"campaigns"' in item]
    assert campaign_sql == []


def test_missing_lead_and_audit_columns_are_added():
    rows = []
    for table_name, names in {
        "leads": ["id", "campaign_id", "place_id", "name"],
        "audit_logs": ["id", "method", "path"],
    }.items():
        for name in names:
            rows.append({"table_name": table_name, "column_name": name, "is_nullable": "NO"})
    rows.append({"table_name": "leads", "column_name": "legacy_flag", "is_nullable": "NO"})
    statements = plan_schema_upgrade(Base.metadata, rows)
    text = "\n".join(statements)
    assert 'ALTER TABLE "leads" ADD COLUMN IF NOT EXISTS "maps_url" TEXT' in text
    assert 'ALTER TABLE "leads" ALTER COLUMN "legacy_flag" DROP NOT NULL' in text
    assert 'ALTER TABLE "audit_logs" ADD COLUMN IF NOT EXISTS "detail" TEXT' in text
    assert 'ALTER COLUMN "place_id" DROP NOT NULL' not in text

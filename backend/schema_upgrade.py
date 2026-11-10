"""Startup upgrades for databases created by older versions of LeadForge.

create_all() adds missing tables. It does not change an existing table.
An old volume can still have a NOT NULL column the current models do not set
(for example campaigns.max_results). Inserts then fail. This planner adds
columns the models need and relaxes extra NOT NULL columns. It does not delete
rows or drop columns, so existing values stay.
"""

import re

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_ident(name: str) -> str:
    if not _IDENT.fullmatch(name or ""):
        raise ValueError(f"Refusing to touch an unexpected column name: {name!r}")
    return '"' + name + '"'


def sql_type(column) -> str:
    kind = column.type
    if isinstance(kind, Text):
        return "TEXT"
    if isinstance(kind, String):
        return f"VARCHAR({kind.length or 255})"
    if isinstance(kind, Integer):
        return "INTEGER"
    if isinstance(kind, Float):
        return "DOUBLE PRECISION"
    if isinstance(kind, Boolean):
        return "BOOLEAN"
    if isinstance(kind, DateTime):
        if kind.timezone:
            return "TIMESTAMP WITH TIME ZONE"
        return "TIMESTAMP"
    return "TEXT"


def plan_schema_upgrade(metadata, db_columns: list[dict]) -> list[str]:
    """Return idempotent DDL for the tables that already exist.

    db_columns items need table_name, column_name, and is_nullable ('YES' or 'NO').
    """
    present = {}
    for row in db_columns:
        table = row["table_name"]
        present.setdefault(table, {})[row["column_name"]] = row.get("is_nullable", "YES")

    statements = []
    for table_name, table in metadata.tables.items():
        if table_name not in present:
            continue
        existing = present[table_name]
        model_names = set()
        for column in table.columns:
            model_names.add(column.name)
            if column.name in existing:
                continue
            statements.append(
                f"ALTER TABLE {quote_ident(table_name)} "
                f"ADD COLUMN IF NOT EXISTS {quote_ident(column.name)} {sql_type(column)}"
            )
        for column_name, nullable in existing.items():
            if column_name in model_names or nullable == "YES":
                continue
            if column_name == "id":
                continue
            statements.append(
                f"ALTER TABLE {quote_ident(table_name)} "
                f"ALTER COLUMN {quote_ident(column_name)} DROP NOT NULL"
            )
    return statements

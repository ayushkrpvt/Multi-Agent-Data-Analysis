"""
Schema tool: reads the live SQLite schema and enriches it with
schema/schema_metadata.json (descriptions, relationships, business rules)
to build the context given to the LLM agents.
"""

import json
import sqlite3
from functools import lru_cache
from pprint import pprint

from tools.config import DB_PATH, SCHEMA_DIR


def get_connection():
    return sqlite3.connect(DB_PATH)


@lru_cache(maxsize=1)
def get_metadata() -> dict:
    path = SCHEMA_DIR / "schema_metadata.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"tables": {}, "relationships": [], "business_rules": []}


def get_tables():
    """List of all table names in the database."""

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()

    return [r[0] for r in rows]


def get_table_columns(table_name):
    """List of (column_name, column_type) for one table (junk columns hidden)."""

    conn = get_connection()
    try:
        rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    finally:
        conn.close()

    return [
        (r[1], r[2])
        for r in rows
        if not r[1].lower().startswith("unnamed")
    ]


@lru_cache(maxsize=1)
def get_schema():
    """{table: [column, ...]} for the whole database."""

    return {
        table: [c for c, _ in get_table_columns(table)]
        for table in get_tables()
    }


def normalize_tables(tables):
    """Keep only real table names (case-insensitive match)."""

    lookup = {t.lower(): t for t in get_schema()}

    result = []
    for t in tables or []:
        key = str(t).strip().lower()
        if key in lookup and lookup[key] not in result:
            result.append(lookup[key])

    return result


def _table_block(table):

    meta = get_metadata()["tables"].get(table, {})
    col_meta = meta.get("columns", {})

    lines = [f"Table: {table}"]
    if meta.get("description"):
        lines.append(f"  -- {meta['description']}")

    for col, ctype in get_table_columns(table):
        desc = col_meta.get(col, "")
        lines.append(f"  - {col} ({ctype}){': ' + desc if desc else ''}")

    return "\n".join(lines)


def get_schema_text():
    """Full schema as LLM-friendly text."""
    return "\n\n".join(_table_block(t) for t in get_schema())


def get_table_overview():
    """One line per table: name + description (used by intent/planning)."""

    meta = get_metadata()["tables"]
    return "\n".join(
        f"- {t}: {meta.get(t, {}).get('description', '')}"
        for t in get_schema()
    )


def get_required_schema(required_tables):
    """Schema text only for the given tables."""

    tables = normalize_tables(required_tables) or list(get_schema())
    return "\n\n".join(_table_block(t) for t in tables)


def get_relationships():

    meta = get_metadata()

    rel = "\n".join(f"- {r}" for r in meta.get("relationships", []))
    rules = "\n".join(f"- {r}" for r in meta.get("business_rules", []))
    coverage = meta.get("data_coverage", {})

    return (
        f"RELATIONSHIPS (join keys)\n{rel}\n\n"
        f"BUSINESS RULES\n{rules}\n\n"
        f"DATA COVERAGE\n"
        f"- Orders from {coverage.get('first_order_date')} "
        f"to {coverage.get('last_order_date')}\n"
        f"- {coverage.get('note', '')}"
    )


def get_sql_context(required_tables):
    """
    Complete context passed to the SQL agent:
    relevant tables (+ any join tables needed) + relationships + rules.
    """

    tables = normalize_tables(required_tables)

    # Revenue always needs order_details; dates always need orders.
    if tables and "order_details" in tables and "orders" not in tables:
        tables.append("orders")

    return (
        "DATABASE SCHEMA\n\n"
        f"{get_required_schema(tables)}\n\n"
        "--------------------------------------------------\n\n"
        f"{get_relationships()}"
    )


def print_schema():
    pprint(get_schema())


if __name__ == "__main__":

    print("\nTABLES\n")
    print(get_tables())

    print("\nSQL CONTEXT\n")
    print(get_sql_context(["products", "categories", "order_details"]))

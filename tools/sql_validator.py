"""
SQL validator used by the SQL Generation Agent before any query is executed.

Validation flow:
    1. Non-empty, single statement
    2. Forbidden keywords (whole-word match, string literals ignored)
    3. Forbidden (non-SQLite) functions
    4. SQLGlot parse -> must be a read-only SELECT / WITH query
    5. All referenced tables must exist in the database
    6. SQLite EXPLAIN QUERY PLAN (catches unknown columns, bad syntax)
"""

import re
import sqlite3

import sqlglot
from sqlglot import exp

from tools.config import DB_PATH

FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "CREATE", "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX",
]

FORBIDDEN_FUNCTIONS = [
    "JSON_AGG", "JSON_OBJECT", "JSON_OBJECT_AGG", "JSON_BUILD_OBJECT",
    "ARRAY_AGG", "DATE_TRUNC", "EXTRACT", "TO_CHAR", "STRING_AGG",
    "DATEPART", "DATEDIFF", "YEAR", "MONTH",
]

HINTS = {
    "YEAR": "Use strftime('%Y', orders.OrderDate) instead of YEAR().",
    "MONTH": "Use strftime('%m', orders.OrderDate) or strftime('%Y-%m', ...) instead of MONTH().",
    "DATE_TRUNC": "Use strftime('%Y-%m', orders.OrderDate) instead of DATE_TRUNC().",
    "EXTRACT": "Use strftime() instead of EXTRACT().",
    "STRING_AGG": "Use GROUP_CONCAT() instead of STRING_AGG().",
    "DATEDIFF": "Use julianday(a) - julianday(b) instead of DATEDIFF().",
}


def clean_sql(text: str) -> str:
    """Strip markdown fences / leading 'sql' labels / trailing semicolons."""

    sql = text.strip()
    fence = re.search(r"```(?:sql|sqlite)?\s*(.*?)```", sql, re.S | re.I)
    if fence:
        sql = fence.group(1)

    sql = re.sub(r"^\s*(sql|sqlite)\s*\n", "", sql, flags=re.I)

    # Start at the first SELECT / WITH if the model added prose before it
    m = re.search(r"\b(WITH|SELECT)\b", sql, re.I)
    if m:
        sql = sql[m.start():]

    return sql.strip().rstrip(";").strip()


def _strip_literals(sql: str) -> str:
    """Remove '...' string literals so keywords inside values don't trigger."""
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def extract_tables(sql_query: str):
    """Real table names referenced (CTE names excluded)."""

    tree = sqlglot.parse_one(sql_query, dialect="sqlite")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}

    return {
        t.name.lower()
        for t in tree.find_all(exp.Table)
        if t.name and t.name.lower() not in cte_names
    }


def format_sql(sql_query: str):
    try:
        return sqlglot.transpile(sql_query, read="sqlite", pretty=True)[0]
    except Exception:
        return sql_query


def _db_tables():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return {
            r[0].lower()
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()


def validate_sql(sql_query: str, required_tables: list = None):
    """
    Returns (True, None) or (False, error_message).

    required_tables is accepted for backward compatibility but no longer
    forces every planned table into the query (that caused needless joins).
    """

    if not sql_query or not sql_query.strip():
        return False, "Empty SQL query."

    body = _strip_literals(sql_query)
    upper = body.upper()

    if ";" in body.strip().rstrip(";"):
        return False, "Only ONE SQL statement is allowed."

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", upper):
            return False, f"Forbidden SQL operation detected: {kw}. Only SELECT queries are allowed."

    for fn in FORBIDDEN_FUNCTIONS:
        if re.search(rf"\b{fn}\s*\(", upper):
            hint = HINTS.get(fn, "It is not supported by SQLite.")
            return False, f"Function {fn}() is not valid in SQLite. {hint}"

    try:
        tree = sqlglot.parse_one(sql_query, dialect="sqlite")
    except Exception as e:
        return False, f"SQL syntax error: {e}"

    if not isinstance(tree, exp.Query):
        return False, "Query must be a SELECT (or WITH ... SELECT) statement."

    try:
        used = extract_tables(sql_query)
    except Exception as e:
        return False, f"Could not analyse tables: {e}"

    unknown = used - _db_tables()
    if unknown:
        return False, f"Unknown table(s): {sorted(unknown)}. Use only tables from the schema."

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        conn.execute(f"EXPLAIN QUERY PLAN {sql_query}")
    except Exception as e:
        return False, f"SQLite error: {e}"
    finally:
        conn.close()

    return True, None

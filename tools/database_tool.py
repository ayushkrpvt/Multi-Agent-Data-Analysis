"""
Database tool: read-only query execution against the SQLite database.
"""

import sqlite3

import pandas as pd

from tools.config import DB_PATH, MAX_RESULT_ROWS


def get_connection(read_only: bool = True):
    """SQLite connection. Read-only by default (extra safety for LLM SQL)."""

    if read_only:
        return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    return sqlite3.connect(DB_PATH)


def execute_query(sql_query: str, max_rows: int = MAX_RESULT_ROWS) -> pd.DataFrame:
    """Execute SQL and return a DataFrame (capped at max_rows)."""

    conn = get_connection()

    try:
        df = pd.read_sql_query(sql_query, conn)
    finally:
        conn.close()

    if len(df) > max_rows:
        df = df.head(max_rows)

    return df

"""
Text-to-SQL generation with native tool calling (used by the SQL Generation Agent).

Tools available to the LLM:
    get_column_values(table, column, search)  -> exact values for WHERE filters
    get_table_schema(table_names)             -> schema of extra tables
    submit_sql_query(sql, explanation)        -> final answer
"""

import json
import sqlite3
from typing import List, Tuple

from pydantic import BaseModel, Field

from models.common import Str, StrList
from tools.config import DB_PATH, load_prompt
from tools.llm import invoke_text
from tools.schema_tool import get_required_schema, get_schema, get_sql_context
from tools.sql_validator import clean_sql
from tools.tool_calling import final_tool, run_tool_loop, work_tool


# ----------------------------------------
# Tool argument schemas
# ----------------------------------------

class ColumnValuesArgs(BaseModel):
    table: str = Field(description="Table name, e.g. categories")
    column: str = Field(description="Column name, e.g. CategoryName")
    search: str = Field(default="", description="Optional case-insensitive text to search for, e.g. 'bev'")


class TableSchemaArgs(BaseModel):
    table_names: List[str] = Field(description="Tables whose columns you need")


class SubmitSQL(BaseModel):
    sql: Str = Field(description="One SQLite SELECT query")
    explanation: Str = Field(default="", description="One sentence: what the query returns")
    tables_used: StrList = Field(default_factory=list)


# ----------------------------------------
# Tool implementations (read-only, identifiers checked against the schema)
# ----------------------------------------

def _resolve(table: str, column: str = None):
    schema = get_schema()
    t = next((x for x in schema if x.lower() == str(table).strip().lower()), None)
    if not t:
        raise ValueError(f"Unknown table '{table}'. Tables: {', '.join(schema)}")
    if column is None:
        return t, None
    c = next((x for x in schema[t] if x.lower() == str(column).strip().lower()), None)
    if not c:
        raise ValueError(f"Unknown column '{column}' in {t}. Columns: {', '.join(schema[t])}")
    return t, c


def get_column_values(table: str, column: str, search: str = "") -> str:
    t, c = _resolve(table, column)
    sql = f'SELECT DISTINCT "{c}" FROM "{t}" WHERE "{c}" IS NOT NULL'
    params = []
    if search:
        sql += f' AND LOWER("{c}") LIKE ?'
        params.append(f"%{search.lower()}%")
    sql += f' ORDER BY "{c}" LIMIT 40'
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        values = [r[0] for r in conn.execute(sql, params)]
    finally:
        conn.close()
    return json.dumps({"table": t, "column": c, "values": values})


def get_table_schema(table_names: List[str]) -> str:
    tables = [_resolve(t)[0] for t in table_names]
    return get_required_schema(tables)


WORK_TOOLS = [
    work_tool(get_column_values, "get_column_values",
              "Distinct values of a text column (use before filtering on names).", ColumnValuesArgs),
    work_tool(get_table_schema, "get_table_schema",
              "Columns, types and descriptions of the given tables.", TableSchemaArgs),
]


# ----------------------------------------
# Prompt + generation
# ----------------------------------------

def build_sql_prompts(question, intent, plan, data_query, previous_sql="", error=""):

    schema_context = get_sql_context(plan.get("required_tables") or intent.get("required_tables", []))
    system = f"{load_prompt('sql_prompt')}\n\n{schema_context}"

    feedback = ""
    if error:
        feedback = (
            "\nPREVIOUS ATTEMPT FAILED - FIX IT\n"
            f"Previous SQL:\n{previous_sql}\n\n"
            f"Error / feedback:\n{error}\n"
        )

    user = f"""USER QUESTION:
{question}

INTENT:
{json.dumps(intent, indent=2)}

DATA REQUEST (the dataset this query must return):
id: {data_query.get('id')}
purpose: {data_query.get('purpose', '')}
description: {data_query.get('description')}
{feedback}
Write the query and call submit_sql_query."""

    return system, user


def generate_sql(question, intent, plan, data_query, previous_sql="", error="") -> Tuple[str, str, list]:
    """Returns (sql, explanation, tool_call_log)."""

    system, user = build_sql_prompts(question, intent, plan, data_query, previous_sql, error)

    try:
        result = run_tool_loop(
            system, user,
            final_tools={"submit_sql_query": final_tool(
                "submit_sql_query", "Submit the final SQLite SELECT query.", SubmitSQL)},
            work_tools=WORK_TOOLS,
            max_steps=4, agent="SQL Agent",
        )
        return clean_sql(result.args.sql), result.args.explanation, result.log

    except Exception as e:
        print(f"[SQL Agent] tool calling failed ({e}); falling back to plain text SQL")
        return clean_sql(invoke_text(f"{system}\n\n{user}\nReturn ONLY the SQL.")), "", []

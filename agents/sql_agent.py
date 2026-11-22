"""
Agent 3 - SQL Generation Agent

sql_generate uses native tool calling (tools/sql_generator.py): the LLM may look up
exact column values / extra table schemas, then calls submit_sql_query.

Implemented as three LangGraph nodes forming a self-correcting loop:

    sql_generate  ->  sql_validate  --(invalid, retries left)-->  sql_generate
                           |
                        (valid)
                           v
                      sql_execute   --(error / 0 rows, retries left)--> sql_generate
                           |
                (success: next data query or -> Analysis Agent)

Every attempt is logged in state["sql_attempts"] for explainability.
"""

from agents.common import traced
from tools.config import MAX_SQL_RETRIES
from tools.database_tool import execute_query
from tools.sql_generator import generate_sql
from tools.sql_validator import validate_sql


def _current_query(state):
    return state["data_queries"][state.get("query_index", 0)]


@traced("SQL Agent", "generate SQL")
def sql_generate(state):

    dq = _current_query(state)
    attempt = state.get("sql_attempt", 0) + 1

    sql, explanation, tool_log = generate_sql(
        question=state["user_query"],
        intent=state["intent"],
        plan=state["plan"],
        data_query=dq,
        previous_sql=state.get("current_sql", "") if state.get("sql_error") else "",
        error=state.get("sql_error") or "",
    )

    lookups = [c["tool"] for c in tool_log if c["tool"] != "submit_sql_query"]
    return {
        "current_sql": sql,
        "sql_attempt": attempt,
        "tool_calls": [{"agent": "SQL Agent", "query_id": dq["id"], **c} for c in tool_log],
        "_detail": f"query '{dq['id']}' attempt {attempt}" + (f", tool lookups: {lookups}" if lookups else ""),
    }


@traced("SQL Agent", "validate SQL")
def sql_validate(state):

    dq = _current_query(state)
    ok, error = validate_sql(state.get("current_sql", ""))

    update = {"sql_error": None if ok else error, "_detail": "passed" if ok else error}

    if not ok:
        update["sql_attempts"] = [{
            "query_id": dq["id"], "attempt": state.get("sql_attempt", 1),
            "sql": state.get("current_sql", ""), "status": "validation_failed", "error": error,
        }]

    return update


@traced("SQL Agent", "execute SQL")
def sql_execute(state):

    dq = _current_query(state)
    sql = state["current_sql"]
    attempt = state.get("sql_attempt", 1)

    try:
        df = execute_query(sql)
    except Exception as e:
        err = f"Execution error: {e}"
        return {
            "sql_error": err,
            "sql_attempts": [{"query_id": dq["id"], "attempt": attempt, "sql": sql,
                              "status": "execution_failed", "error": err}],
            "_detail": err,
        }

    if df.empty:
        err = ("The query ran but returned 0 rows. Check filter values (exact names such as "
               "'Beverages', 'Germany'), date filters (strftime('%Y', o.OrderDate) = '1997'; data "
               "covers 1996-07 to 1998-05) and join keys.")
        return {
            "sql_error": err,
            "sql_attempts": [{"query_id": dq["id"], "attempt": attempt, "sql": sql,
                              "status": "empty_result", "error": err}],
            "_detail": "0 rows",
        }

    results = dict(state.get("query_results") or {})
    results[dq["id"]] = {
        "query_id": dq["id"],
        "purpose": dq.get("purpose", ""),
        "description": dq.get("description", ""),
        "sql": sql,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "records": df.to_dict(orient="records"),
    }

    return {
        "query_results": results,
        "query_index": state.get("query_index", 0) + 1,
        "sql_attempt": 0,
        "sql_error": None,
        "sql_attempts": [{"query_id": dq["id"], "attempt": attempt, "sql": sql, "status": "passed"}],
        "_detail": f"'{dq['id']}' -> {len(df)} rows, columns {list(df.columns)}",
    }


@traced("SQL Agent", "give up on query")
def sql_give_up(state):
    """Retries exhausted. Primary query failure stops the pipeline; supporting ones are skipped."""

    dq = _current_query(state)
    failed = list(state.get("failed_queries") or []) + [dq["id"]]
    update = {
        "failed_queries": failed,
        "query_index": state.get("query_index", 0) + 1,
        "sql_attempt": 0,
        "sql_error": None,
        "_detail": f"'{dq['id']}' failed after {MAX_SQL_RETRIES} attempts",
    }
    if dq["id"] == "primary" or not state.get("query_results"):
        update["error"] = (
            f"Could not generate a valid SQL query for '{dq['id']}' after {MAX_SQL_RETRIES} attempts. "
            f"Last error: {state.get('sql_error')}"
        )
    return update


# ----------------------------------------
# Routing functions (used as LangGraph conditional edges)
# ----------------------------------------

def route_after_validate(state):
    if not state.get("sql_error"):
        return "execute"
    return "retry" if state.get("sql_attempt", 0) < MAX_SQL_RETRIES else "give_up"


def route_after_execute(state):
    if state.get("sql_error"):
        return "retry" if state.get("sql_attempt", 0) < MAX_SQL_RETRIES else "give_up"
    return "next_query" if state.get("query_index", 0) < len(state["data_queries"]) else "analyze"


def route_after_give_up(state):
    if state.get("error"):
        return "fail"
    return "next_query" if state.get("query_index", 0) < len(state["data_queries"]) else "analyze"

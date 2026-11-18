"""
Agent 2 - Planning Agent
Breaks the request into analytical tasks and decides which datasets
(data queries) the SQL agent must retrieve.
"""

import json

from agents.common import traced
from models.planning_model import DataQuery, PlanOutput
from tools.config import MAX_DATA_QUERIES, load_prompt
from tools.llm import invoke_json
from tools.schema_tool import normalize_tables


def build_prompt(intent: dict) -> str:
    template = load_prompt("planning_prompt").replace("{max_queries}", str(MAX_DATA_QUERIES))
    return (
        f"{template}\n\nINTENT INFORMATION:\n{json.dumps(intent, indent=2)}\n\n"
        "Create the execution plan. Return ONLY JSON."
    )


def _fallback_query(intent: dict) -> DataQuery:
    cols = ", ".join(intent.get("dimensions", []) + [intent.get("metric", "Sales")])
    filters = "; ".join(intent.get("filters", [])) or "no filters"
    return DataQuery(
        id="primary",
        purpose="Answer the question directly",
        description=f"{intent.get('metric', 'Sales')} by {', '.join(intent.get('dimensions', [])) or 'total'}; "
                    f"filters: {filters}; period: {intent.get('time_period', 'All')}. columns: {cols}",
    )


@traced("Planning Agent", "create execution plan")
def planning_agent(state):

    intent = state["intent"]

    plan = invoke_json(build_prompt(intent), PlanOutput)

    # ---- validate / repair the plan ----
    plan.required_tables = normalize_tables(plan.required_tables + intent.get("required_tables", []))

    queries = [q for q in plan.data_queries if q.description.strip()]
    if not queries:
        queries = [_fallback_query(intent)]
    queries[0].id = "primary"

    seen, unique = set(), []
    for q in queries:
        qid = q.id.strip().replace(" ", "_").lower() or f"query_{len(unique) + 1}"
        if qid in seen:
            qid = f"{qid}_{len(unique) + 1}"
        seen.add(qid)
        q.id = qid
        unique.append(q)

    plan.data_queries = unique[:MAX_DATA_QUERIES]

    return {
        "plan": plan.model_dump(),
        "data_queries": [q.model_dump() for q in plan.data_queries],
        "query_index": 0,
        "sql_attempt": 0,
        "sql_error": None,
        "query_results": {},
        "failed_queries": [],
        "_detail": f"{len(plan.analysis_steps)} steps, {len(plan.data_queries)} data queries: "
                   f"{[q.id for q in plan.data_queries]}",
    }

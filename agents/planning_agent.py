"""
Agent 2 - Planning Agent

Breaks the request into analytical tasks and decides which datasets
(data queries) the SQL agent must retrieve. Output is submitted through the
native tool call `submit_plan` (validated by PlanOutput).

Re-planning: when the Analysis Agent calls request_more_data, the workflow
comes back here. The planner then receives the reason + the datasets already
retrieved and plans ONLY the additional queries needed.
"""

import json

from agents.common import traced
from models.planning_model import DataQuery, PlanOutput
from tools.config import MAX_DATA_QUERIES, load_prompt
from tools.llm import invoke_json
from tools.schema_tool import normalize_tables
from tools.tool_calling import final_tool, run_tool_loop


def _existing_summary(state):
    return [
        {"id": qid, "columns": r["columns"], "rows": r["row_count"], "description": r.get("description", "")}
        for qid, r in (state.get("query_results") or {}).items()
    ]


def build_prompts(state):
    system = load_prompt("planning_prompt").replace("{max_queries}", str(MAX_DATA_QUERIES))
    user = f"INTENT INFORMATION:\n{json.dumps(state['intent'], indent=2)}\n\nUSER QUESTION: {state['user_query']}\n"

    request = state.get("analysis_request")
    if request:
        user += (
            "\nRE-PLANNING REQUEST FROM THE ANALYSIS AGENT\n"
            f"Reason: {request.get('reason')}\n"
            f"Needed data: {json.dumps(request.get('needed_data', []))}\n"
            f"Datasets ALREADY retrieved (do not request them again):\n"
            f"{json.dumps(_existing_summary(state), indent=2)}\n\n"
            "Plan ONLY the additional data queries needed (1-2). Use new ids (not 'primary'). "
            "Keep the other plan fields describing the full analysis.\n"
        )

    return system, user + "\nCall submit_plan."


def _fallback_query(intent: dict) -> DataQuery:
    cols = ", ".join(intent.get("dimensions", []) + [intent.get("metric", "Sales")])
    filters = "; ".join(intent.get("filters", [])) or "no filters"
    return DataQuery(
        id="primary",
        purpose="Answer the question directly",
        description=f"{intent.get('metric', 'Sales')} by {', '.join(intent.get('dimensions', [])) or 'total'}; "
                    f"filters: {filters}; period: {intent.get('time_period', 'All')}. columns: {cols}",
    )


def _clean_ids(queries, taken):
    out = []
    for q in queries:
        qid = q.id.strip().replace(" ", "_").lower() or f"query_{len(taken) + 1}"
        base, n = qid, 2
        while qid in taken:
            qid, n = f"{base}_{n}", n + 1
        taken.add(qid)
        q.id = qid
        out.append(q)
    return out


@traced("Planning Agent", "create execution plan")
def planning_agent(state):

    intent = state["intent"]
    replanning = bool(state.get("analysis_request"))
    system, user = build_prompts(state)

    tool_log = []
    try:
        result = run_tool_loop(
            system, user,
            final_tools={"submit_plan": final_tool(
                "submit_plan", "Submit the execution plan and the data queries for the SQL agent.", PlanOutput)},
            max_steps=3, agent="Planning Agent",
        )
        plan, tool_log = result.args, result.log
    except Exception as e:
        print(f"[Planning Agent] tool calling failed ({e}); falling back to JSON mode")
        plan = invoke_json(f"{system}\n\n{user}\nReturn ONLY the submit_plan arguments as JSON.", PlanOutput)

    # ---- validate / repair the plan ----
    plan.required_tables = normalize_tables(plan.required_tables + intent.get("required_tables", []))
    queries = [q for q in plan.data_queries if q.description.strip()]
    tool_calls = [{"agent": "Planning Agent", **c} for c in tool_log]

    if not replanning:
        if not queries:
            queries = [_fallback_query(intent)]
        queries[0].id = "primary"
        queries = _clean_ids(queries, set())[:MAX_DATA_QUERIES]
        plan.data_queries = queries
        return {
            "plan": plan.model_dump(),
            "data_queries": [q.model_dump() for q in queries],
            "query_index": 0,
            "sql_attempt": 0,
            "sql_error": None,
            "query_results": {},
            "failed_queries": [],
            "replan_count": 0,
            "tool_calls": tool_calls,
            "_detail": f"{len(plan.analysis_steps)} steps, {len(queries)} data queries: {[q.id for q in queries]}",
        }

    # ---- re-planning: append only NEW queries ----
    existing = list(state.get("data_queries") or [])
    taken = {q["id"] for q in existing} | set(state.get("query_results") or {})
    new = _clean_ids(queries, taken | {"primary"})[:2]
    if not new:
        need = (state["analysis_request"].get("needed_data") or ["additional breakdown"])[0]
        new = _clean_ids([DataQuery(id="extra", purpose="Requested by Analysis Agent", description=need)], taken)

    merged_plan = dict(state.get("plan") or {})
    merged_plan["analysis_steps"] = list(dict.fromkeys(merged_plan.get("analysis_steps", []) + plan.analysis_steps))
    merged_plan["required_tables"] = normalize_tables(merged_plan.get("required_tables", []) + plan.required_tables)
    merged_plan["data_queries"] = existing + [q.model_dump() for q in new]
    merged_plan.setdefault("replans", []).append({
        "reason": state["analysis_request"].get("reason"),
        "new_queries": [q.id for q in new],
    })

    return {
        "plan": merged_plan,
        "data_queries": merged_plan["data_queries"],
        "query_index": len(existing),
        "sql_attempt": 0,
        "sql_error": None,
        "analysis_request": None,
        "tool_calls": tool_calls,
        "_detail": f"RE-PLAN #{state.get('replan_count', 0)}: added {[q.id for q in new]}",
    }

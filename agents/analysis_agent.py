"""
Agent 4 - Analysis Agent

analysis_agent  : loads query results, profiles every dataset (time column,
                  metric, dimensions) and decides the analysis branch.
route_analysis  : conditional edge -> one of the four specialised nodes:
                  trend_analysis | comparison_analysis | root_cause_analysis | anomaly_detection

Each specialised node computes statistics in Python (tools/analysis_tool.py)
and asks the LLM to interpret them (structured AnalysisOutput).
"""

import json

from agents.common import traced
from models.analysis_model import AnalysisOutput
from tools import analysis_tool as at
from tools.config import load_prompt
from tools.llm import invoke_json


def load_datasets(state):
    """query_id -> DataFrame (primary first)."""
    return {qid: at.to_frame(r["records"]) for qid, r in (state.get("query_results") or {}).items()}


@traced("Analysis Agent", "profile data & choose analysis")
def analysis_agent(state):

    metric_hint = state["intent"].get("metric", "")
    datasets = load_datasets(state)
    profiles = {qid: at.profile(df, metric_hint) for qid, df in datasets.items()}

    requested = state["intent"].get("analysis_type", "comparison")
    primary = profiles.get("primary") or next(iter(profiles.values()))

    # Validate that the requested analysis is possible with the data returned
    route = requested
    if requested == "trend" and not primary["time_col"]:
        route = "comparison"
    if requested == "root_cause" and not any(p["time_col"] or p["dimensions"] for p in profiles.values()):
        route = "comparison"

    detail = f"requested={requested}, route={route}; " + "; ".join(
        f"{qid}: time={p['time_col']}, metric={p['metric']}, dims={p['dimensions']}"
        for qid, p in profiles.items()
    )

    return {"profiles": profiles, "analysis_route": route, "_detail": detail}


def route_analysis(state):
    return state.get("analysis_route", "comparison")


# ----------------------------------------
# LLM interpretation shared by all branches
# ----------------------------------------

def _compact(obj, limit=7000):
    text = json.dumps(obj, indent=1, default=str)
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


def _coverage_note(datasets, profiles):
    """Explicit statement of which periods in the returned data are partial."""
    cov = at.get_metadata().get("data_coverage", {})
    if not any(p.get("time_col") for p in profiles.values()):
        return "Totals cover the full dataset period (1996-07-04 to 1998-05-06); no time breakdown in this analysis."
    partial = set()
    for qid, df in datasets.items():
        t = profiles.get(qid, {}).get("time_col")
        if t:
            partial |= set(at.partial_periods(list(df[t].astype(str).unique())))
    note = (f"Dataset contains orders from {cov.get('first_order_date')} to {cov.get('last_order_date')} only. "
            f"{cov.get('note', '')}")
    if partial:
        note += (f" Periods present in this data that are PARTIAL (incomplete, not a real decline): "
                 f"{sorted(partial)}.")
    return note


def _interpret(state, analysis_type, facts):

    datasets = load_datasets(state)
    facts = {"data_coverage": _coverage_note(datasets, state.get("profiles", {})), **facts}
    previews = {
        qid: df.head(15).to_dict(orient="records") for qid, df in datasets.items()
    }

    prompt = (
        load_prompt("analysis_prompt").replace("{analysis_type}", analysis_type)
        + f"\n\nUSER QUESTION:\n{state['user_query']}"
        + f"\n\nINTENT:\n{json.dumps(state['intent'], indent=1)}"
        + f"\n\nPLAN STEPS:\n{json.dumps(state['plan'].get('analysis_steps', []), indent=1)}"
        + f"\n\nCOMPUTED FACTS:\n{_compact(facts)}"
        + f"\n\nDATA PREVIEW (first rows of each dataset):\n{_compact(previews, 3000)}"
        + "\n\nReturn ONLY JSON."
    )

    result = invoke_json(prompt, AnalysisOutput).model_dump()
    state_facts = facts  # includes data_coverage
    return result, state_facts


def _supporting_stats(datasets, profiles):
    return {
        qid: at.describe_dataset(df, profiles[qid])["metric_stats"]
        for qid, df in list(datasets.items())[1:]
    }


def _primary(state):
    datasets = load_datasets(state)
    pid = "primary" if "primary" in datasets else next(iter(datasets))
    return datasets, pid


@traced("Analysis Agent", "trend analysis")
def trend_analysis(state):
    datasets, pid = _primary(state)
    profiles = state["profiles"]
    facts = at.trend_analysis(datasets[pid], profiles[pid])
    facts["supporting_datasets"] = _supporting_stats(datasets, profiles)
    analysis, facts = _interpret(state, "trend", facts)
    return {"analysis_facts": facts, "analysis": analysis,
            "_detail": f"direction={facts.get('trend_direction')}, change={facts.get('overall_change_pct')}%"}


@traced("Analysis Agent", "comparison analysis")
def comparison_analysis(state):
    datasets, pid = _primary(state)
    profiles = state["profiles"]
    facts = at.comparison_analysis(datasets[pid], profiles[pid])
    facts["supporting_datasets"] = {
        qid: at.comparison_analysis(df, profiles[qid]) for qid, df in list(datasets.items())[1:]
    }
    analysis, facts = _interpret(state, "comparison", facts)
    top = (facts.get("ranking") or [{}])[0]
    return {"analysis_facts": facts, "analysis": analysis, "_detail": f"top={top}"}


@traced("Analysis Agent", "root cause analysis")
def root_cause_analysis(state):
    datasets = load_datasets(state)
    facts = at.root_cause_analysis(datasets, state["profiles"])
    analysis, facts = _interpret(state, "root_cause", facts)
    return {"analysis_facts": facts, "analysis": analysis,
            "_detail": f"drivers analysed: {list(facts.get('drivers', {}))}"}


@traced("Analysis Agent", "anomaly detection")
def anomaly_detection(state):
    datasets, pid = _primary(state)
    facts = at.anomaly_analysis(datasets[pid], state["profiles"][pid])
    analysis, facts = _interpret(state, "anomaly", facts)
    return {"analysis_facts": facts, "analysis": analysis,
            "_detail": f"{len(facts.get('anomalies', []))} anomalies found"}

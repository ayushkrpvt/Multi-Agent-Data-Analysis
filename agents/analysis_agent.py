"""
Agent 4 - Analysis Agent (single LangGraph node, native tool calling)

Receives the outputs of the Intent, Planning and SQL agents and lets the LLM
decide the analysis type by calling analysis tools:

    trend_analysis(dataset_id)                      -> growth, peaks, partial periods
    comparison_analysis(dataset_id)                 -> shares, spread, concentration
    rank_analysis(dataset_id, top_n, ascending)     -> leaderboard, gaps, leader margin
    root_cause_analysis()                           -> like-for-like change decomposition by driver
    anomaly_detection(dataset_id, z_threshold)      -> z-score / IQR outliers

Final tools:
    submit_analysis(analysis_type, summary, findings, ...)   -> go to Reporting Agent
    request_more_data(reason, needed_data)                   -> back to Planning + SQL agents

All statistics are computed in Python (tools/analysis_tool.py); the LLM interprets them.
"""

import json
import re

from pydantic import BaseModel, Field

from agents.common import traced
from models.analysis_model import ANALYSIS_TYPES, AnalysisOutput, MoreDataRequest
from tools import analysis_tool as at
from tools.config import MAX_REPLANS, load_prompt
from tools.llm import invoke_json
from tools.tool_calling import final_tool, run_tool_loop, work_tool


def load_datasets(state):
    """query_id -> DataFrame (primary first)."""
    return {qid: at.to_frame(r["records"]) for qid, r in (state.get("query_results") or {}).items()}


def _compact(obj, limit=7000):
    text = json.dumps(obj, indent=1, default=str)
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


def coverage_note(datasets, profiles):
    """Explicit statement of which periods in the returned data are partial."""
    cov = at.get_metadata().get("data_coverage", {})
    if not any(p.get("time_col") for p in profiles.values()):
        return "Totals cover the full dataset period (1996-07-04 to 1998-05-06); no time breakdown in this data."
    partial = set()
    for qid, df in datasets.items():
        t = profiles.get(qid, {}).get("time_col")
        if t:
            partial |= set(at.partial_periods(list(df[t].astype(str).unique())))
    note = (f"Dataset contains orders from {cov.get('first_order_date')} to {cov.get('last_order_date')} only. "
            f"{cov.get('note', '')}")
    if partial:
        note += f" Periods present in this data that are PARTIAL (incomplete, not a real decline): {sorted(partial)}."
    return note


# ----------------------------------------
# Analysis tools (bound to the current datasets)
# ----------------------------------------

class DatasetArgs(BaseModel):
    dataset_id: str = Field(default="primary", description="Dataset id, e.g. primary")


class RankArgs(DatasetArgs):
    top_n: int = Field(default=10, description="How many positions to rank")
    ascending: bool = Field(default=False, description="True = bottom/worst first")


class AnomalyArgs(DatasetArgs):
    z_threshold: float = Field(default=2.0, description="z-score threshold for an anomaly")


class NoArgs(BaseModel):
    pass


class AnalysisToolkit:
    """Holds the datasets; each method is exposed to the LLM as a tool."""

    def __init__(self, datasets, profiles):
        self.datasets, self.profiles = datasets, profiles
        self.results = {}   # analysis_type -> facts

    def _get(self, dataset_id):
        if dataset_id not in self.datasets:
            dataset_id = "primary" if "primary" in self.datasets else next(iter(self.datasets))
        return dataset_id, self.datasets[dataset_id], self.profiles[dataset_id]

    def _store(self, kind, facts):
        if "error" not in facts:
            self.results[kind] = facts
        return facts

    def trend(self, dataset_id="primary"):
        qid, df, prof = self._get(dataset_id)
        if not prof["time_col"]:
            return {"error": f"Dataset '{qid}' has no time column - trend analysis is not possible. "
                             "Use another analysis or request_more_data for a time breakdown."}
        return self._store("trend", {"dataset": qid, **at.trend_analysis(df, prof)})

    def comparison(self, dataset_id="primary"):
        qid, df, prof = self._get(dataset_id)
        facts = at.comparison_analysis(df, prof)
        return self._store("comparison", {"dataset": qid, **facts})

    def rank(self, dataset_id="primary", top_n=10, ascending=False):
        qid, df, prof = self._get(dataset_id)
        return self._store("rank", {"dataset": qid, **at.rank_analysis(df, prof, top_n, ascending)})

    def root_cause(self):
        facts = at.root_cause_analysis(self.datasets, self.profiles)
        if not facts["drivers"] and not facts.get("driver_shares"):
            return {"error": "No dataset has both a time column and a driver dimension, so the change cannot "
                             "be decomposed. Call request_more_data for e.g. monthly KPI by product / country."}
        return self._store("root_cause", facts)

    def anomaly(self, dataset_id="primary", z_threshold=2.0):
        qid, df, prof = self._get(dataset_id)
        return self._store("anomaly", {"dataset": qid, **at.anomaly_analysis(df, prof, z_threshold)})

    def run(self, kind):
        """Deterministic call used when the LLM chose a type without calling its tool."""
        return {"trend": self.trend, "comparison": self.comparison, "rank": self.rank,
                "root_cause": self.root_cause, "anomaly": self.anomaly}[kind]()

    def tools(self):
        return [
            work_tool(self.trend, "trend_analysis",
                      "Trend over time: change %, peak/low, period-over-period moves, slope, partial periods.",
                      DatasetArgs),
            work_tool(self.comparison, "comparison_analysis",
                      "Compare members of a dimension: totals, shares, top vs bottom ratio, concentration.",
                      DatasetArgs),
            work_tool(self.rank, "rank_analysis",
                      "Leaderboard: rank positions, gap to next, leader margin, cumulative share, bottom members.",
                      RankArgs),
            work_tool(self.root_cause, "root_cause_analysis",
                      "Explain WHY a KPI changed: like-for-like period comparison and contribution of each driver "
                      "(uses all datasets).", NoArgs),
            work_tool(self.anomaly, "anomaly_detection",
                      "Detect unusual spikes / drops with z-score and IQR (partial periods excluded from baseline).",
                      AnomalyArgs),
        ]


# ----------------------------------------
# Prompt
# ----------------------------------------

def build_user_prompt(state, datasets, profiles, replans_left):
    summary = []
    for qid, df in datasets.items():
        res = state["query_results"][qid]
        summary.append({
            "dataset_id": qid,
            "purpose": res.get("purpose", ""),
            "rows": len(df),
            "columns": list(df.columns),
            "detected": {k: profiles[qid][k] for k in ("time_col", "metric", "dimensions")},
            "first_rows": df.head(8).to_dict(orient="records"),
        })

    failed = state.get("failed_queries") or []
    return (
        f"USER QUESTION:\n{state['user_query']}\n\n"
        f"INTENT (Intent Agent):\n{json.dumps(state['intent'], indent=1)}\n\n"
        f"PLAN (Planning Agent):\n{json.dumps({k: state['plan'].get(k) for k in ('objective', 'analysis_steps')}, indent=1)}\n\n"
        f"DATASETS (SQL Agent):\n{_compact(summary, 6000)}\n\n"
        + (f"Data queries that FAILED: {failed}\n\n" if failed else "")
        + f"DATA COVERAGE: {coverage_note(datasets, profiles)}\n\n"
        + f"DATA SUFFICIENCY CHECK (computed in Python):\n{json.dumps(sufficiency_check(profiles), indent=1)}\n\n"
        + (f"You may call request_more_data (re-plans left: {replans_left})."
           if replans_left > 0 else
           "No more data can be requested: analyse with the datasets you have.")
        + "\n\nCall the analysis tool(s), then submit_analysis."
    )


def sufficiency_check(profiles):
    """Which analysis types the retrieved data can support (computed in Python, given to the LLM)."""
    has_time = any(p["time_col"] for p in profiles.values())
    has_dim = any(p["dimensions"] for p in profiles.values())
    driver_ds = [q for q, p in profiles.items() if p["time_col"] and p["dimensions"]]
    return {
        "trend": "possible" if has_time else "NOT possible: no dataset has a time column",
        "comparison": "possible" if has_dim else "NOT possible: no dimension column",
        "rank": "possible" if has_dim else "NOT possible: no dimension column",
        "anomaly": "possible" if (has_time or has_dim) else "NOT possible",
        "root_cause": (f"possible (time + driver dimension in: {driver_ds})" if driver_ds else
                       "NOT possible: no dataset has BOTH a time column and a driver dimension "
                       "(need e.g. Month + ProductName + Sales)"),
    }


def _guess_type(question, profiles):
    """Keyword heuristic used only if tool calling fails completely."""
    q = question.lower()
    primary = profiles.get("primary") or next(iter(profiles.values()))
    if re.search(r"\bwhy\b|reason|cause|driver", q):
        return "root_cause"
    if re.search(r"unusual|anomal|outlier|spike|drop", q):
        return "anomaly"
    if re.search(r"\btop\b|\bbottom\b|best|worst|highest|lowest|rank", q):
        return "rank"
    if primary["time_col"] and re.search(r"trend|over time|month|quarter|year|growth|changed", q):
        return "trend"
    return "comparison"


# ----------------------------------------
# The node
# ----------------------------------------

@traced("Analysis Agent", "choose analysis via tool calling")
def analysis_agent(state):

    datasets = load_datasets(state)
    if not datasets:
        return {"error": "No data was retrieved, so nothing can be analysed."}

    profiles = {qid: at.profile(df, state["intent"].get("metric", "")) for qid, df in datasets.items()}
    toolkit = AnalysisToolkit(datasets, profiles)
    replans_left = MAX_REPLANS - state.get("replan_count", 0)

    finals = {"submit_analysis": final_tool(
        "submit_analysis", "Submit the analysis type and your interpretation of the tool results.", AnalysisOutput)}
    if replans_left > 0:
        finals["request_more_data"] = final_tool(
            "request_more_data", "The data is not sufficient: ask the Planning and SQL agents for more datasets.",
            MoreDataRequest)

    coverage = coverage_note(datasets, profiles)
    tool_log = []

    try:
        result = run_tool_loop(
            load_prompt("analysis_prompt"),
            build_user_prompt(state, datasets, profiles, replans_left),
            final_tools=finals, work_tools=toolkit.tools(), max_steps=5, agent="Analysis Agent",
        )
        tool_log = result.log
        tool_calls = [{"agent": "Analysis Agent", **c} for c in tool_log]

        # ---- Not enough information -> back to Planning + SQL ----
        if result.final_tool == "request_more_data":
            req = result.args.model_dump()
            return {
                "profiles": profiles,
                "analysis_request": req,
                "replan_count": state.get("replan_count", 0) + 1,
                "tool_calls": tool_calls,
                "_detail": f"needs more data -> re-plan: {req['reason'][:150]}",
            }

        analysis = result.args

    except Exception as e:
        # Fallback for models with weak tool calling
        print(f"[Analysis Agent] tool calling failed ({e}); using heuristic type + JSON mode")
        kind = _guess_type(state["user_query"], profiles)
        facts = toolkit.run(kind)
        analysis = invoke_json(
            load_prompt("analysis_prompt")
            + f"\n\n{build_user_prompt(state, datasets, profiles, 0)}"
            + f"\n\nTOOL RESULT ({kind}):\n{_compact(facts)}"
            + "\n\nReturn ONLY the submit_analysis arguments as JSON (analysis_type must be "
            + f"'{kind}').", AnalysisOutput)
        tool_calls = [{"agent": "Analysis Agent", "tool": f"{kind} (fallback)", "args": "", "result": ""}]

    kind = analysis.analysis_type

    # Make sure the chosen analysis has computed facts (the LLM may skip the tool call)
    if kind not in toolkit.results:
        facts = toolkit.run(kind)
        if "error" in facts:
            kind = next((k for k in ("comparison", "rank", "trend") if "error" not in toolkit.run(k)), kind)
            analysis.analysis_type = kind

    facts = {"data_coverage": coverage, **toolkit.results.get(kind, {})}
    others = {k: v for k, v in toolkit.results.items() if k != kind}
    if others:
        facts["other_analyses"] = others

    used = [c["tool"] for c in tool_log if c["tool"] not in ("submit_analysis",)]
    return {
        "profiles": profiles,
        "analysis_route": kind,
        "analysis_facts": facts,
        "analysis": analysis.model_dump(),
        "analysis_request": None,
        "tool_calls": tool_calls,
        "_detail": f"analysis_type={kind}; tools used: {used}",
    }


def route_after_analysis(state):
    if state.get("error"):
        return "fail"
    if state.get("analysis_request"):
        return "replan"
    return "report"

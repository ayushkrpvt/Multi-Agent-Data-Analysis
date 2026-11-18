"""
Agent 5 - Reporting Agent
Creates visualizations, writes the executive report (summary, key findings,
root cause analysis, recommendations) and saves it to outputs/reports/.
"""

import json
import os
from datetime import datetime

import pandas as pd

from agents.analysis_agent import load_datasets
from agents.common import traced
from models.report_model import ReportOutput
from tools.config import REPORTS_DIR, llm_description, load_prompt
from tools.llm import invoke_json
from tools.visualization_tool import create_charts


def build_prompt(state, charts):
    facts = json.dumps(state.get("analysis_facts", {}), indent=1, default=str)
    if len(facts) > 6000:
        facts = facts[:6000] + "\n... (truncated)"
    return (
        load_prompt("reporting_prompt")
        + f"\n\nUSER QUESTION:\n{state['user_query']}"
        + f"\n\nANALYSIS TYPE: {state.get('analysis_route')}"
        + f"\n\nANALYSIS AGENT OUTPUT:\n{json.dumps(state.get('analysis', {}), indent=1)}"
        + f"\n\nCOMPUTED FACTS:\n{facts}"
        + f"\n\nCHARTS CREATED:\n{json.dumps([c['title'] for c in charts])}"
        + "\n\nReturn ONLY JSON."
    )


def _md_table(records, limit=10):
    if not records:
        return "_No rows._"
    df = pd.DataFrame(records).head(limit)
    try:
        return df.to_markdown(index=False, floatfmt=",.2f")
    except Exception:
        return df.to_string(index=False)


def render_markdown(state, report: dict, charts: list) -> str:

    intent = state.get("intent", {})
    plan = state.get("plan", {})
    analysis = state.get("analysis", {})
    lines = [
        f"# {report['title']}",
        "",
        f"**Question:** {state['user_query']}  ",
        f"**Analysis type:** {state.get('analysis_route')}  ",
        f"**Generated:** {datetime.now():%Y-%m-%d %H:%M} · **LLM:** {llm_description()} · **Dataset:** Northwind",
        "",
        "## Business Summary",
        "",
        report["business_summary"],
        "",
        "## Key Findings",
        "",
        *[f"- {f}" for f in report.get("key_findings", [])],
        "",
    ]

    if charts:
        lines += ["## Visualizations", ""]
        for c in charts:
            rel = os.path.relpath(c["path"], REPORTS_DIR)
            lines += [f"### {c['title']}", "", f"![{c['title']}]({rel})", "", f"_{c['description']}_", ""]

    lines += ["## Root Cause Analysis", "", *[f"- {r}" for r in report.get("root_cause_analysis", [])], ""]

    lines += ["## Recommendations", "", "| Priority | Action | Rationale |", "|---|---|---|"]
    for r in report.get("recommendations", []):
        lines.append(f"| {r['priority']} | {r['action']} | {r['rationale']} |")
    lines.append("")

    if analysis.get("caveats"):
        lines += ["## Data Caveats", "", *[f"- {c}" for c in analysis["caveats"]], ""]

    if report.get("next_questions"):
        lines += ["## Suggested Next Questions", "", *[f"- {q}" for q in report["next_questions"]], ""]

    # ---------- Appendix: how the agents got here ----------
    lines += [
        "---",
        "## Appendix: How This Answer Was Produced",
        "",
        "### 1. Intent (Intent Agent)",
        "```json", json.dumps(intent, indent=2), "```",
        "",
        "### 2. Execution Plan (Planning Agent)",
        f"**Objective:** {plan.get('objective', '')}",
        "",
        *[f"{i + 1}. {s}" for i, s in enumerate(plan.get("analysis_steps", []))],
        "",
        "### 3. Data Retrieval (SQL Agent)",
        "",
    ]
    attempts = state.get("sql_attempts", [])
    for qid, res in (state.get("query_results") or {}).items():
        n = sum(1 for a in attempts if a["query_id"] == qid)
        lines += [
            f"**{qid}** - {res.get('purpose', '')} ({res['row_count']} rows, {n} attempt(s))",
            "", "```sql", res["sql"], "```", "",
            _md_table(res["records"]), "",
        ]
    for qid in state.get("failed_queries", []):
        lines += [f"**{qid}** - failed after all retries (skipped)", ""]

    lines += ["### 4. Agent Trace", "", "| # | Agent | Step | Status | Time (s) |", "|---|---|---|---|---|"]
    for i, t in enumerate(state.get("trace", []), 1):
        lines.append(f"| {i} | {t['agent']} | {t['step']} | {t['status']} | {t['seconds']} |")
    lines.append("")

    return "\n".join(lines)


@traced("Reporting Agent", "charts + executive report")
def reporting_agent(state):

    run_id = state["run_id"]
    datasets = load_datasets(state)

    charts = create_charts(
        analysis_type=state.get("analysis_route", "comparison"),
        datasets=datasets,
        profiles=state.get("profiles", {}),
        facts=state.get("analysis_facts", {}),
        run_id=run_id,
        question=state["user_query"],
    )

    report = invoke_json(build_prompt(state, charts), ReportOutput).model_dump()

    # Markdown is rendered after this node adds its own trace entry, so include it now
    md = render_markdown(state, report, charts)
    path = REPORTS_DIR / f"{run_id}.md"
    path.write_text(md, encoding="utf-8")

    return {
        "charts": charts,
        "report": report,
        "report_markdown": md,
        "report_path": str(path),
        "_detail": f"{len(charts)} charts, {len(report.get('recommendations', []))} recommendations -> {path.name}",
    }

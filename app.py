"""
Streamlit UI for the Multi-Agent Business Data Analytics Platform.

Run:  streamlit run app.py
"""

import json

import pandas as pd
import streamlit as st

from graph.workflow import run_analysis
from tools.config import LLM_PROVIDER, llm_description

SAMPLE_QUESTIONS = [
    "Show monthly sales trends for 1997",
    "Compare sales by product category",
    "Who are the top 10 customers by revenue?",
    "Why did beverage sales decline in 1998?",
    "Are there any unusual spikes or drops in monthly sales?",
    "Which countries generate the most revenue?",
    "How has the number of orders changed per quarter?",
    "Which employees generated the highest sales in 1997?",
    "What's the weather in Paris?  (guardrail demo)",
]

NODE_LABELS = {
    "intent_agent": ("🧭", "Intent Agent", "Understanding the question"),
    "planning_agent": ("🗺️", "Planning Agent", "Creating execution plan"),
    "sql_generate": ("🧑‍💻", "SQL Agent", "Generating SQL"),
    "sql_validate": ("🛡️", "SQL Agent", "Validating SQL"),
    "sql_execute": ("🗄️", "SQL Agent", "Executing query"),
    "sql_give_up": ("⚠️", "SQL Agent", "Retries exhausted"),
    "analysis_agent": ("🔬", "Analysis Agent", "Choosing & running analysis (tool calling)"),
    "reporting_agent": ("📝", "Reporting Agent", "Charts & executive report"),
}

st.set_page_config(page_title="Multi-Agent Business Analytics", page_icon="📊", layout="wide")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("⚙️ Configuration")
    st.markdown(f"**LLM:** {llm_description()}")
    st.markdown("**Dataset:** Northwind (orders Jul 1996 – May 1998)")
    st.markdown("**Orchestration:** LangGraph, 5 agents")
    if LLM_PROVIDER == "ollama":
        st.caption("Make sure Ollama is running: `ollama serve`")
    st.divider()
    st.subheader("💡 Sample questions")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, width="stretch"):
            st.session_state["question"] = q.split("  (")[0]

# ---------------- Main ----------------
st.title("📊 Multi-Agent Business Data Analytics")
st.caption("Ask a business question in plain English. Five AI agents will understand it, plan the "
           "analysis, query the database, analyse the results and write an executive report.")

question = st.text_input(
    "Business question",
    value=st.session_state.get("question", ""),
    placeholder="e.g. Why did beverage sales decline in 1998?",
)

run = st.button("🚀 Analyze", type="primary", disabled=not question.strip())

if run:
    st.session_state.pop("result", None)
    with st.status("Agents are working...", expanded=True) as status:

        def on_step(node, update):
            icon, agent, label = NODE_LABELS.get(node, ("•", node, ""))
            entry = (update.get("trace") or [{}])[-1]
            if entry.get("status") == "blocked":
                mark = "🛑"
            elif update.get("analysis_request"):
                mark = "🔁 needs more data → re-planning"
            elif update.get("sql_error"):
                mark = "🔁"
            else:
                mark = "✅" if entry.get("status") != "error" else "❌"
            tools_used = [c["tool"] for c in update.get("tool_calls") or []]
            if tools_used:
                label += f" · tools: {', '.join(tools_used)}"
            detail = str(entry.get("detail", ""))[:160]
            st.write(f"{icon} **{agent}** — {label} {mark}  \n<small>{detail}</small>",
                     unsafe_allow_html=True)

        try:
            result = run_analysis(question.strip(), on_step=on_step)
            st.session_state["result"] = result
            if (result.get("guardrail") or {}).get("blocked"):
                status.update(label="Question is outside the scope of this assistant", state="complete",
                              expanded=False)
            elif result.get("error"):
                status.update(label="Pipeline stopped with an error", state="error")
            else:
                status.update(label="Analysis complete", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Pipeline failed", state="error")
            st.exception(e)

result = st.session_state.get("result")

if result and (result.get("guardrail") or {}).get("blocked"):
    g = result["guardrail"]
    st.info(f"🤖 {g.get('message')}")
    st.caption(f"Guardrail: {g.get('category')} ({g.get('layer')}) — {g.get('reason')}")
    result = None

if result:

    if result.get("error"):
        st.error(result["error"])

    report = result.get("report")

    tabs = st.tabs(["📝 Executive Report", "📈 Charts", "🗄️ Data & SQL", "🤖 Agent Trace"])

    # ---------- Report ----------
    with tabs[0]:
        if report:
            st.header(report["title"])
            st.markdown(f"**Analysis type (chosen by Analysis Agent):** `{result.get('analysis_route')}`")
            replans = (result.get("plan") or {}).get("replans") or []
            if replans:
                st.caption(f"🔁 The Analysis Agent requested more data {len(replans)} time(s): "
                           + "; ".join(r.get("reason", "") for r in replans))
            st.subheader("Business Summary")
            st.write(report["business_summary"])

            st.subheader("Key Findings")
            for f in report.get("key_findings", []):
                st.markdown(f"- {f}")

            for c in (result.get("charts") or [])[:1]:
                st.image(c["path"], caption=c["title"], width="stretch")

            st.subheader("Root Cause Analysis")
            for r in report.get("root_cause_analysis", []):
                st.markdown(f"- {r}")

            st.subheader("Recommendations")
            st.dataframe(pd.DataFrame(report.get("recommendations", [])),
                         width="stretch", hide_index=True)

            caveats = (result.get("analysis") or {}).get("caveats") or []
            if caveats:
                st.subheader("Data Caveats")
                for c in caveats:
                    st.warning(c)

            if report.get("next_questions"):
                st.subheader("Suggested Next Questions")
                for q in report["next_questions"]:
                    st.markdown(f"- {q}")

            st.download_button("⬇️ Download report (Markdown)", result.get("report_markdown", ""),
                               file_name=f"{result['run_id']}.md", mime="text/markdown")
            st.caption(f"Saved to {result.get('report_path')}")
        else:
            st.info("No report was produced.")

    # ---------- Charts ----------
    with tabs[1]:
        charts = result.get("charts") or []
        if not charts:
            st.info("No charts.")
        for c in charts:
            st.subheader(c["title"])
            st.image(c["path"], width="stretch")
            st.caption(c["description"])

    # ---------- Data & SQL ----------
    with tabs[2]:
        for qid, res in (result.get("query_results") or {}).items():
            st.subheader(f"{qid} — {res.get('purpose', '')}")
            st.caption(res.get("description", ""))
            st.code(res["sql"], language="sql")
            st.dataframe(pd.DataFrame(res["records"]), width="stretch", hide_index=True)
        attempts = result.get("sql_attempts") or []
        if attempts:
            st.subheader("All SQL attempts (validation & self-correction)")
            st.dataframe(pd.DataFrame(attempts), width="stretch", hide_index=True)

    # ---------- Agent Trace ----------
    with tabs[3]:
        st.subheader("Agent execution trace")
        st.dataframe(pd.DataFrame(result.get("trace") or []), width="stretch", hide_index=True)
        st.subheader("Native tool calls")
        st.dataframe(pd.DataFrame(result.get("tool_calls") or []), width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Intent (Agent 1)**")
            st.json(result.get("intent") or {})
        with c2:
            st.markdown("**Execution Plan (Agent 2)**")
            st.json(result.get("plan") or {})
        st.markdown("**Analysis interpretation (Agent 4)**")
        st.json(result.get("analysis") or {})
        with st.expander("Computed facts (Python statistics given to the LLM)"):
            st.code(json.dumps(result.get("analysis_facts") or {}, indent=2, default=str), language="json")

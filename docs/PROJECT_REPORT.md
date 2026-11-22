# Final Project Report
## Autonomous Multi-Agent Business Data Analytics Platform

---

### 1. Executive Summary

This project delivers an **agentic AI analytics platform**. Business users ask questions in natural language and receive an executive-level report: business summary, key findings, visualizations, root cause analysis and actionable recommendations.

The system is built as five specialised agents orchestrated with **LangGraph**. They use **native tool calling**:
- The Intent Agent applies **guardrails** to off-topic or unsafe questions.
- The SQL Agent looks up exact values before writing SQL.
- The Analysis Agent **chooses the analysis type itself** (trend, comparison, rank, root cause, anomaly) by deciding which analysis tools to call. If the data isn't enough, it sends the workflow back to the Planning and SQL agents.

Agents exchange structured, validated outputs, correct their own errors, and log every step and tool call, so each answer is explainable.

It runs entirely **locally with Ollama** (default `llama3.2`), or with Google Gemini through a free API key. It uses the **Northwind** dataset in SQLite.

**Key results:**
- **Benchmark:** 8 questions, every one producing a complete report. The Analysis Agent chose the expected analysis type in each case, including the new *rank* type for "top/highest" questions.
- **Guardrails:** off-topic and unsafe questions (e.g. weather, "delete all orders", marketing spend) were refused with a friendly message, and no SQL was generated.
- **Accuracy:** the reported figures were checked against direct SQL queries and matched exactly.
- **False premise refuted:** for *"Why did beverage sales decline in 1998?"* the system showed a like-for-like (Jan–Apr) **+157% growth**. The apparent decline comes only from the dataset ending on 6 May 1998.

---

### 2. Business Problem

Business users regularly need answers about sales performance, customer behaviour, revenue trends and operations. Traditional BI tools require manual report building, SQL knowledge and analytical expertise, which creates delays and a bottleneck on data teams.

**Goal:** automate the full analyst workflow: understand the question → plan → retrieve data → analyse → visualize → recommend. The output must be reliable and explainable, not just plausible text.

---

### 3. Solution Architecture

```
Question → Intent Agent (guardrails) ──off-topic──► friendly message
                │
                ▼
          Planning Agent ◄──────────── request_more_data ───────────┐
                │                                                   │
                ▼                                                   │
          SQL Agent (generate ⇄ validate ⇄ execute, tool lookups)   │
                │                                                   │
                ▼                                                   │
          Analysis Agent (single node; tools: trend | comparison |  │
                          rank | root_cause | anomaly) ─────────────┘
                │ submit_analysis
                ▼
          Reporting Agent → Executive Report
```

`docs/ARCHITECTURE.md` has the full LangGraph graph, the tool-calling loop, the state schema and the details of each agent.

| Layer | Technology |
|---|---|
| Orchestration | LangGraph `StateGraph` with conditional edges (guardrail exit, SQL retry loop, re-plan loop) |
| Agent actions | Native tool calling (`bind_tools`) with a shared loop and Pydantic-validated final tools |
| LLM | Ollama (`llama3.2`, local) or Gemini (cloud), switchable through `.env` |
| SQL validation | SQLGlot + SQLite `EXPLAIN QUERY PLAN` |
| Data | SQLite (Northwind), pandas, NumPy |
| Visualization | Matplotlib (validated colour-blind-safe palette) |
| UI | Streamlit (live agent progress and tool calls) and CLI |

---

### 4. Agent Design

| Agent | Responsibility | Tools (native tool calling) | Validation |
|---|---|---|---|
| **1. Intent** | Extract metric, KPIs, dimensions, filters, time period, tables; **guardrails** | `submit_intent` / `reject_out_of_scope` | Rule-based pre-checks, Pydantic, unknown tables removed |
| **2. Planning** | Decompose into analysis steps and 1–3 data queries; re-plan on request | `submit_plan` | Plan repaired, ids de-duplicated, query count capped, fallback query |
| **3. SQL** | Schema-aware Text-to-SQL, validation, execution, retry | `get_column_values`, `get_table_schema`, `submit_sql_query` | 6-layer validator, empty-result detection, up to 3 self-corrections |
| **4. Analysis** | **Choose the analysis type**, compute statistics, interpret; request more data if insufficient | `trend_analysis`, `comparison_analysis`, `rank_analysis`, `root_cause_analysis`, `anomaly_detection`, `submit_analysis`, `request_more_data` | Data-sufficiency check, numbers computed in Python, max re-plans |
| **5. Reporting** | Charts, executive summary, findings, root cause, recommendations | structured report | Pydantic, recommendations must cite data |

#### Key design decisions

1. **The analysis type is an agent decision, not a label.** The Intent Agent only extracts requirements. The Analysis Agent sees the actual data and a Python sufficiency check, then *chooses* by calling analysis tools. It may combine tools (e.g. trend + anomaly).
2. **Closed feedback loops.** SQL failures loop back to SQL generation. Insufficient data loops back to Planning → SQL → Analysis (`request_more_data`), capped by `MAX_REPLANS`.
3. **Guardrails without an extra node.** Two layers inside the Intent Agent: deterministic rules (data modification, prompt injection, greetings, empty input), then an LLM decision through tool choice (`reject_out_of_scope`) with categorised, friendly replies.
4. **The LLM never does the maths.** Statistics (growth, shares, ranks, contribution to change, z-scores, IQR) are computed by the analysis tools in Python. The LLM only interprets tool results.
5. **One provider-agnostic tool loop.** `tools/tool_calling.py` runs the same tool-calling protocol on Gemini and Ollama. It validates arguments, lets the model self-correct, forces a final answer, and falls back to JSON for weak models.
6. **Explainability by default.** Every node is traced and every tool call is logged. The report appendix shows the intent, plan, SQL, re-plans, tool calls and timings.

---

### 5. Validation & Reliability Mechanisms

| Risk | Mitigation |
|---|---|
| Off-topic / unsafe / injection questions | Two-layer guardrails in the Intent Agent; friendly refusal, no SQL generated |
| Destructive SQL | Read-only SQLite connection + keyword/statement validator |
| Hallucinated tables/columns | Schema-scoped prompt, `get_table_schema` tool, table existence check, `EXPLAIN QUERY PLAN` |
| Wrong filter values → empty result | `get_column_values` tool + zero-row results trigger a retry |
| Non-SQLite dialect (`YEAR()`, `DATE_TRUNC`) | Function blacklist with corrective hints fed back to the LLM |
| Wrong analysis for the data | Python data-sufficiency check; analysis tools return errors when infeasible; `request_more_data` loop |
| Malformed tool arguments | Pydantic validation; the error is returned to the LLM to self-correct |
| Arithmetic hallucination | All numbers computed in Python by the analysis tools |
| Misleading partial-period trends | Automatic detection, like-for-like comparison, caveats in the report |
| Temporary API failures | Retry with exponential backoff, request timeout, friendly error messages |

---

### 6. Results

The benchmark ran on 10 questions (full outputs in `docs/samples/`). The analysis type was chosen by the Analysis Agent:

| # | Question | Type chosen | Analysis tools called | Outcome |
|---|---|---|---|---|
| 1 | Show monthly sales trends for 1997 | trend | trend, anomaly | ✅ +16.2% Jan→Dec; peak Dec ($77.5K); low Jun ($39.1K) |
| 2 | Compare sales by product category | comparison | comparison | ✅ Beverages 21.2%, Dairy 18.6%; Grains/Cereals lowest (7.4%) |
| 3 | Top 10 customers by revenue | rank | rank | ✅ QUICK-Stop #1 ($117.5K), Save-a-lot #2, Ernst Handel #3 |
| 4 | Why did beverage sales decline in 1998? | root cause | root_cause, trend, comparison | ✅ Premise refuted: +157% like-for-like; drivers Côte de Blaye, Germany, USA, Brazil |
| 5 | Unusual spikes or drops in monthly sales? | anomaly | anomaly | ✅ Apr 1998 spike (z = 2.64); May 1998 correctly identified as partial |
| 6 | Which countries generate the most revenue? | rank | rank | ✅ USA 19.5%, Germany 18.1% |
| 7 | Top employees by sales in 1997 | rank | rank | ✅ Margaret Peacock $139.5K (21.2%), leads #2 by $27.7K |
| 8 | Orders per quarter | trend | trend, anomaly | ✅ 70 → 182 orders (+160%); 1998-Q2 flagged as partial |
| 9 | What's the weather in Paris? | – | – | 🛑 LLM guardrail (off_topic), friendly reply |
| 10 | Delete all orders from 1996 | – | – | 🛑 Rule-based guardrail (unsafe_request), no LLM call |

**Re-plan loop:** in a test where the first plan lacked a time breakdown for *"Why did sales to Germany change in 1998?"*, the Analysis Agent detected this through the sufficiency check and called `request_more_data`. The Planning Agent added a monthly-by-product query and the SQL Agent fetched it. The Analysis Agent then completed a root-cause analysis (+163% like-for-like, driven by Côte de Blaye).

**Accuracy check:** key figures (top employee, top customer, top countries, quarterly order counts, category totals) were re-computed with independent SQL and matched exactly.

**Typical latency:** 30–50 s per question with Gemini (about 6–8 LLM calls). It is slower on CPU-only Ollama.

---

### 7. Sample Insight (Root Cause)

> **Question:** Why did beverage sales decline in 1998?
>
> **Finding:** The premise is contradicted by the data. Jan–Apr 1998 beverage sales were **$117,627 vs $45,720** in Jan–Apr 1997 (**+157%**). Côte de Blaye alone contributed **52%** of the increase. Germany (+$28.6K), the USA (+$24.1K) and Brazil (+$20.6K) drove growth, while Denmark (−97%) and Canada (−84%) declined.
>
> **Why it looked like a decline:** the dataset ends on 1998-05-06, so the 1998 annual total covers only ~4 months.
>
> **Recommendations:** scale supply and marketing for Côte de Blaye; investigate the Denmark and Canada contraction; reinvest in the German, US and Brazilian markets.

---

### 8. Limitations

- **Dataset:** Northwind is small and historical (Jul 1996 – May 1998). `Discount` is 0 in this copy, and some accented product names were lost in the source CSVs.
- **Small local models:** `llama3.2` (3B) has weaker tool calling and SQL on complex questions. The retry loops and JSON fallbacks mitigate this, and larger local models (7–8B, e.g. `qwen2.5:7b`) noticeably improve quality. The Ollama model must support tools.
- **Single-database scope:** one SQLite database. There is no semantic layer for metric definitions beyond `schema_metadata.json`.
- **Static charts:** PNG charts are used so they embed in reports. The UI doesn't offer interactive drill-down.

### 9. Future Work

- Conversational follow-ups with memory (LangGraph checkpointer).
- A semantic metric layer (certified KPI definitions) and support for larger warehouses (PostgreSQL, Snowflake).
- A human-in-the-loop approval step before running expensive queries.
- Forecasting (Prophet / ARIMA) as a fifth analysis branch.
- An evaluation harness with gold SQL answers for automatic accuracy tracking.
- PDF export and scheduled reports.

### 10. Conclusion

The platform shows real multi-agent collaboration. Specialised agents act through native tool calling, hand structured and validated results to one another, refuse out-of-scope questions, recover from their own errors, decide the analysis strategy from the actual data (requesting more data when needed), and produce explainable, data-grounded executive reports. Deterministic analytics plus LLM interpretation makes the system reliable even on a small local model.

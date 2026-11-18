# Final Project Report
## Autonomous Multi-Agent Business Data Analytics Platform

---

### 1. Executive Summary

This project delivers an **agentic AI analytics platform**. Business users ask questions in natural language and receive an executive-level report: business summary, key findings, visualizations, root cause analysis and actionable recommendations.

The system is built as five specialised agents orchestrated with **LangGraph**. They exchange **structured, validated outputs**, correct their own SQL errors, route between four analysis strategies, and log every step so each answer is explainable.

It runs entirely **locally with Ollama** (default `llama3.2`), or with Google Gemini through a free API key. It uses the **Northwind** dataset in SQLite.

**Key result:** across 8 benchmark questions covering all four analysis types, every run produced a complete report. The reported figures were checked against direct SQL queries and matched exactly. In one case the system correctly **refuted a false premise**. For *"Why did beverage sales decline in 1998?"* it showed that a like-for-like comparison (Jan–Apr) gives **+157% growth**. The apparent decline comes only from the dataset ending on 6 May 1998.

---

### 2. Business Problem

Business users regularly need answers about sales performance, customer behaviour, revenue trends and operations. Traditional BI tools require manual report building, SQL knowledge and analytical expertise, which creates delays and a bottleneck on data teams.

**Goal:** automate the full analyst workflow: understand the question → plan → retrieve data → analyse → visualize → recommend. The output must be reliable and explainable, not just plausible text.

---

### 3. Solution Architecture

```
Question → Intent Agent → Planning Agent → SQL Agent (generate ⇄ validate ⇄ execute)
         → Analysis Agent ─┬─ Trend
                           ├─ Comparison
                           ├─ Root Cause
                           └─ Anomaly      → Reporting Agent → Executive Report
```

`docs/ARCHITECTURE.md` has the full LangGraph graph, the state schema and the details of each agent.

| Layer | Technology |
|---|---|
| Orchestration | LangGraph `StateGraph` with conditional edges |
| LLM | Ollama (`llama3.2`, local) or Gemini (cloud), switchable through `.env` |
| Structured outputs | Pydantic v2 models with lenient validators |
| SQL validation | SQLGlot + SQLite `EXPLAIN QUERY PLAN` |
| Data | SQLite (Northwind), pandas, NumPy |
| Visualization | Matplotlib (validated colour-blind-safe palette) |
| UI | Streamlit (live agent progress) and CLI |

---

### 4. Agent Design

| Agent | Responsibility | Structured output | Validation |
|---|---|---|---|
| **1. Intent** | Extract metric, KPIs, dimensions, filters, time period, analysis type, tables | `IntentOutput` | Pydantic, analysis type normalised, unknown tables removed |
| **2. Planning** | Decompose into analysis steps and 1–3 data queries (primary + drivers) | `PlanOutput` | Plan repaired, ids de-duplicated, query count capped, fallback query |
| **3. SQL** | Schema-aware Text-to-SQL, validation, execution, retry | `QueryResult` + attempt log | 6-layer validator, empty-result detection, up to 3 self-corrections |
| **4. Analysis** | Profile data, route to trend / comparison / root cause / anomaly, interpret | `AnalysisOutput` | Branch feasibility check, numbers computed in Python |
| **5. Reporting** | Charts, executive summary, findings, root cause, recommendations | `ReportOutput` + Markdown | Pydantic, recommendations must cite data |

#### Key design decisions

1. **The LLM never does the maths.** Statistics (growth, shares, contribution to change, z-scores, IQR) are computed deterministically in `tools/analysis_tool.py`. The LLM only interprets these facts. This removes arithmetic hallucinations and keeps results correct on small local models.
2. **Self-correcting SQL loop as graph edges.** Validation and execution failures go back to the generator along with the exact error message and targeted hints. A query that returns zero rows also counts as a failure, which catches wrong filter values such as `'Beverage'` instead of `'Beverages'`.
3. **Data-aware analysis.** The system knows the dataset's coverage. It flags partial periods, excludes them from anomaly baselines, and switches to like-for-like comparisons for year-over-year questions.
4. **Provider-agnostic LLM layer.** One file (`tools/llm.py`) handles Ollama and Gemini, JSON mode, re-asking on invalid JSON, retries on temporary errors and timeouts.
5. **Explainability by default.** Every node is wrapped with a `@traced` decorator. The report appendix contains the intent, plan, SQL, data preview and agent trace.

---

### 5. Validation & Reliability Mechanisms

| Risk | Mitigation |
|---|---|
| Destructive SQL | Read-only SQLite connection + keyword/statement validator |
| Hallucinated tables/columns | Schema-scoped prompt, table existence check, `EXPLAIN QUERY PLAN` |
| Non-SQLite dialect (`YEAR()`, `DATE_TRUNC`) | Function blacklist with corrective hints fed back to the LLM |
| Wrong filter values → empty result | Zero-row results trigger a retry with guidance |
| Malformed JSON from small models | JSON mode + tolerant parsing + Pydantic + re-ask with the error |
| Arithmetic hallucination | All numbers computed in Python |
| Misleading partial-period trends | Automatic detection, like-for-like comparison, caveats in the report |
| Temporary API failures | Retry with exponential backoff, request timeout, friendly error messages |

---

### 6. Results

The benchmark ran on 8 questions (full outputs in `docs/samples/`):

| # | Question | Analysis | Data queries | Outcome |
|---|---|---|---|---|
| 1 | Show monthly sales trends for 1997 | trend | 1 | ✅ +16.2% Jan→Dec; peak Dec ($77.5K); low Jun ($39.1K) |
| 2 | Compare sales by product category | comparison | 1 | ✅ Beverages 21.2%, Dairy 18.6%; Grains/Cereals lowest (7.4%) |
| 3 | Top 10 customers by revenue | comparison | 1 | ✅ QUICK-Stop, Save-a-lot, Ernst Handel ≈ 56% of top-10 revenue |
| 4 | Why did beverage sales decline in 1998? | root cause | 2 | ✅ Premise refuted: +157% like-for-like; drivers Côte de Blaye, Germany, USA, Brazil |
| 5 | Unusual spikes or drops in monthly sales? | anomaly | 1 | ✅ Apr 1998 spike (z = 2.64); May 1998 correctly identified as partial |
| 6 | Which countries generate the most revenue? | comparison | 1 | ✅ USA 19.5%, Germany 18.1%; 9 of 21 countries make up 80% |
| 7 | Top employees by sales in 1997 | comparison | 1 | ✅ Margaret Peacock $139.5K (21.2%) |
| 8 | Orders per quarter | trend | 1 | ✅ 70 → 182 orders (+160%); 1998-Q2 flagged as partial |

**Accuracy check:** key figures (top employee, top customer, top countries, quarterly order counts, category totals) were re-computed with independent SQL and matched exactly.

**Self-correction observed in testing:** the SQL Agent recovered from non-SQLite functions (`YEAR()`), from empty results caused by wrong filter values, and from unknown columns.

**Typical latency:** 20–50 s per question with Gemini (about 6 LLM calls). It is slower on CPU-only Ollama.

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
- **Small local models:** `llama3.2` (3B) can produce weaker SQL on complex multi-join questions. The retry loop mitigates this, and larger local models (7–8B) noticeably improve quality.
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

The platform shows real multi-agent collaboration. Specialised agents hand structured, validated results to one another, recover from their own errors, choose an analysis strategy suited to the data, and produce explainable, data-grounded executive reports. Deterministic analytics plus LLM interpretation makes the system reliable even on a small local model.

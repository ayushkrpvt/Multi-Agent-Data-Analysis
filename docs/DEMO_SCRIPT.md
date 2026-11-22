# Demonstration Video Script (about 6–8 minutes)

**Before recording**
- `ollama serve` is running, and `ollama pull llama3.2` is done (or a Gemini key is in `.env`).
- `streamlit run app.py` is open in the browser at full screen.
- Run each demo question once beforehand, so the model is warmed up and you know roughly how long it takes.
- Have `docs/ARCHITECTURE.md` (the Mermaid diagram) open in another tab.

---

### 1. Introduction (≈45 s)
> "This is an autonomous multi-agent business analytics platform. A business user asks a question in plain English, and five AI agents, orchestrated with LangGraph, understand it, plan the analysis, write and validate SQL, analyse the data, and produce an executive report with charts, root causes and recommendations. It runs fully locally with Ollama on the Northwind database."

### 2. Architecture (≈1 min)
Show the diagram in `docs/ARCHITECTURE.md` or the README.
> "Each agent acts through native tool calling and hands a validated, structured output to the next.
> The intent agent has guardrails, so off-topic or unsafe questions get a friendly reply.
> The SQL agent can look up exact values with tools and corrects itself when validation fails.
> The analysis agent is a single node that decides the analysis type itself (trend, comparison, rank, root cause or anomaly) by choosing which analysis tool to call. If the data isn't enough, it sends the flow back to planning and SQL.
> The statistics are computed in Python, and the LLM only interprets them, so the numbers are reliable."

### 2b. Guardrails (≈30 s)
Click **"What's the weather in Paris?"** in the sidebar → **Analyze**.
> "The intent agent recognises this isn't about our business data and replies politely with example questions. No SQL is generated."
Optionally type **"Delete all orders from 1996"** to show it is blocked instantly by the rule-based layer.

### 3. Demo 1: Comparison (≈1 min)
Click **"Compare sales by product category"** → **Analyze**.
- While it runs, point at the live agent steps in the status box.
- **Executive Report** tab: summary, key findings, bar chart, recommendations.
> "Beverages lead with 21% of sales. The system computed shares and concentration and turned them into recommendations."

### 4. Demo 2: Root cause, the highlight (≈2 min)
Type **"Why did beverage sales decline in 1998?"** → **Analyze**.
- Point out that the Planning Agent created **2 data queries**: by product and by country.
- In the progress box, point at the Analysis Agent line: **"tools: root_cause_analysis, trend_analysis"**. The agent chose the root-cause analysis itself.
- **Executive Report**: *"the premise is contradicted by the data"*, +157% like-for-like.
> "The question assumes a decline. The agents noticed the data ends on 6 May 1998, compared the same months in both years, and found beverage sales actually grew 157%, driven by Côte de Blaye and by customers in Germany, the USA and Brazil. A simple SQL chatbot would have invented reasons for a decline that never happened."
- **Charts** tab: contribution charts (blue = increase, red = decrease).

### 5. Demo 3: Anomaly (≈1 min)
Click **"Are there any unusual spikes or drops in monthly sales?"**
> "April 1998 is flagged as a spike with z-score 2.6. May 1998 looks low, but it's marked as a partial period and excluded, not reported as a false alarm."

### 6. Explainability (≈1 min)
- **Data & SQL** tab: generated SQL, result table, **all SQL attempts** (show a retry if one happened).
- **Agent Trace** tab: every agent step with timings, the **native tool calls** table (which agent called which tool, with arguments), the intent JSON, the plan JSON, and the computed facts.
> "Every answer is fully traceable: what each agent decided, the SQL it ran, and the numbers behind each claim."
- Optional: open the saved Markdown report from `outputs/reports/`.

### 7. Close (≈30 s)
> "To summarise: five collaborating agents using native tool calling, guardrails, self-correcting SQL, an analysis agent that picks among five analysis strategies and asks for more data when needed, data-aware caveats, and executive reports, all running locally. Thank you."

---

**Tip:** if a live run is slow on a local CPU, record the runs separately and speed up the waiting parts while editing.

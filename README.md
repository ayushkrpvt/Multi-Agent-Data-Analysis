# Multi-Agent Business Data Analytics Platform

Ask business questions in plain English, for example *"Why did beverage sales decline in 1998?"*. Five collaborating AI agents, orchestrated with **LangGraph**, then:

1. understand the question,
2. plan the analysis,
3. write, validate and run SQL (and correct it themselves when it fails),
4. analyse the results (trend, comparison, root cause or anomaly detection),
5. deliver an executive report with charts, key findings, root cause analysis and recommendations.

The platform runs **fully locally with Ollama** (default `llama3.2`). It can also use **Google Gemini** through a free API key. Switching between them is a one-line change in `.env`.

---

## Architecture

```mermaid
flowchart TD
    U([Business question]) --> I

    subgraph A1[Agent 1 · Intent Understanding]
        I[intent_agent<br/>KPIs · dimensions · filters · time period · analysis type]
    end

    I --> P

    subgraph A2[Agent 2 · Planning]
        P[planning_agent<br/>analytical steps · data queries · tables]
    end

    P --> G

    subgraph A3[Agent 3 · SQL Generation]
        G[sql_generate<br/>schema-aware Text-to-SQL] --> V{sql_validate<br/>read-only · SQLite syntax<br/>tables · EXPLAIN}
        V -- invalid, retry with error --> G
        V -- valid --> E[(sql_execute<br/>Northwind SQLite)]
        E -- error / 0 rows, retry --> G
        E -- next data query --> G
        V -- retries exhausted --> X[sql_give_up]
        E -- retries exhausted --> X
    end

    E -- all data retrieved --> AN
    X -- supporting query skipped --> AN

    subgraph A4[Agent 4 · Analysis]
        AN{analysis_agent<br/>profile data · choose branch}
        AN -- trend --> T[trend_analysis]
        AN -- comparison --> C[comparison_analysis]
        AN -- root_cause --> R[root_cause_analysis]
        AN -- anomaly --> AD[anomaly_detection]
    end

    T --> RP
    C --> RP
    R --> RP
    AD --> RP

    subgraph A5[Agent 5 · Reporting]
        RP[reporting_agent<br/>charts · summary · findings · root cause · recommendations]
    end

    RP --> OUT([Executive report<br/>outputs/reports/*.md + charts])
```

`docs/ARCHITECTURE.md` has the full design: shared state, routing rules, validation layers and the graph that LangGraph auto-generates.

### Why the design is "agentic", not a SQL chatbot

| Capability | How it is implemented |
|---|---|
| **Structured hand-offs** | Every agent returns a Pydantic-validated object (`models/`) stored in a shared LangGraph state (`graph/state.py`). |
| **Planning & decomposition** | The Planning Agent splits a question into analysis steps and 1–3 **data queries**. A root-cause question gets a primary query plus "driver" queries, e.g. by product and by country. |
| **Validation of intermediate results** | Intent: unknown tables are removed. Plan: repaired and de-duplicated. SQL: 6-layer validator plus empty-result check. Analysis: falls back to another branch if the data can't support the requested one. |
| **Self-correction loop** | SQL errors and empty results are fed back to the SQL Agent, which retries (up to `MAX_SQL_RETRIES`). |
| **Conditional routing** | LangGraph conditional edges send the flow to one of four analysis branches. |
| **Explainability** | Every step is logged in an **agent trace**, and every SQL attempt is logged. The report appendix shows the intent, plan, SQL and data. |
| **Reliable numbers** | The LLM never does arithmetic. Growth, shares, contribution-to-change, z-scores and partial-period detection are computed in Python (`tools/analysis_tool.py`), and the LLM interprets those facts. |

---

## Project structure

```
├── app.py                     # Streamlit UI
├── main.py                    # Command-line runner
├── requirements.txt
├── .env.example               # Configuration template (copy to .env)
│
├── agents/
│   ├── intent_agent.py        # Agent 1
│   ├── planning_agent.py      # Agent 2
│   ├── sql_agent.py           # Agent 3 (generate / validate / execute / retry)
│   ├── analysis_agent.py      # Agent 4 (router + 4 analysis branches)
│   ├── reporting_agent.py     # Agent 5
│   └── common.py              # trace decorator, friendly errors
│
├── graph/
│   ├── state.py               # Shared state (TypedDict)
│   └── workflow.py            # LangGraph StateGraph + run_analysis()
│
├── tools/
│   ├── config.py              # All settings (reads .env)
│   ├── llm.py                 # LLM provider switch (Ollama / Gemini) + JSON helper
│   ├── database_tool.py       # Read-only query execution
│   ├── schema_tool.py         # Schema + metadata context for the LLM
│   ├── sql_generator.py       # Text-to-SQL prompt building
│   ├── sql_validator.py       # SQL safety & correctness checks
│   ├── analysis_tool.py       # Trend / comparison / root cause / anomaly statistics
│   └── visualization_tool.py  # Matplotlib charts
│
├── models/                    # Pydantic output models for each agent
├── prompts/                   # Prompt templates for each agent
├── schema/
│   ├── database_schema.sql    # DDL of the Northwind database
│   └── schema_metadata.json   # Table/column descriptions, relationships, business rules
├── database/
│   ├── northwind.db           # SQLite database
│   ├── northwind/*.csv        # Source CSVs
│   └── load_data.py           # Rebuilds northwind.db from the CSVs
├── outputs/
│   ├── charts/                # Generated charts (PNG)
│   └── reports/               # Generated reports (Markdown)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROJECT_REPORT.md
│   ├── DEMO_SCRIPT.md
│   └── samples/               # Sample questions with full outputs
├── scripts/generate_samples.py
└── tests/
```

---

## Setup

### 1. Prerequisites
- Python 3.10+ (tested on 3.12)
- **Either** [Ollama](https://ollama.com/download) (local, recommended) **or** a free Gemini API key

### 2. Install

```bash
git clone https://github.com/ayushkrpvt/Multi-Agent-Data-Analysis.git
cd Multi-Agent-Data-Analysis

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure the LLM

```bash
cp .env.example .env              # Windows: copy .env.example .env
```

**Option A: Ollama (local, default)**

```bash
ollama pull llama3.2              # one-time download (~2 GB)
ollama serve                      # skip if the Ollama app is already running
```

`.env`:
```ini
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```

> **Tip:** `llama3.2` (3B) works, but larger local models give noticeably better SQL and reports. If your machine can handle it, try `qwen2.5:7b`, `llama3.1:8b` or `qwen2.5-coder:7b` (`ollama pull <name>` and set `OLLAMA_MODEL`).

**Option B: Gemini (cloud, free key)**

Get a key at <https://aistudio.google.com/apikey>, then set in `.env`:
```ini
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.5-flash-lite
GOOGLE_API_KEY=your-key-here
```
> Free-tier daily limits are counted **per model** and are small (around 20 requests/day for some models). Each question uses about 6 requests. If you hit a quota error, change `GEMINI_MODEL`.

### 4. Check the connection

```bash
python -m tests.test_llm_connection
```

### 5. Run

**Web UI**
```bash
streamlit run app.py
```
Open <http://localhost:8501>, type a question or click a sample question, then press **Analyze**. You will see each agent working live. The results appear in tabs: Executive Report · Charts · Data & SQL · Agent Trace.

**Command line**
```bash
python main.py "Compare sales by product category"
```

Reports are saved to `outputs/reports/` and charts to `outputs/charts/`.

### 6. Tests

```bash
python -m pytest tests/test_tools.py -q     # offline: DB, validator, analytics, charts (no LLM needed)
```

---

## Sample questions

| Question | Analysis type |
|---|---|
| Show monthly sales trends for 1997 | trend |
| How has the number of orders changed per quarter? | trend |
| Compare sales by product category | comparison |
| Who are the top 10 customers by revenue? | comparison |
| Which countries generate the most revenue? | comparison |
| Which employees generated the highest sales in 1997? | comparison |
| Why did beverage sales decline in 1998? | root cause |
| Are there any unusual spikes or drops in monthly sales? | anomaly |

The full generated reports, with charts, SQL and agent traces, are in **[`docs/samples/`](docs/samples/README.md)**. To regenerate them:

```bash
python -m scripts.generate_samples
```

> **Example of explainable insight:** For *"Why did beverage sales decline in 1998?"* the system finds that the premise is **false**. The dataset ends on 1998-05-06, so 1998 looks smaller, but a like-for-like comparison of January–April shows beverage sales **grew 157%**. The growth was driven by Côte de Blaye and by customers in Germany, the USA and Brazil.

---

## Configuration reference (`.env`)

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` or `gemini` |
| `OLLAMA_MODEL` | `llama3.2` | Any model pulled in Ollama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model name |
| `GOOGLE_API_KEY` | — | Required only for Gemini |
| `DB_PATH` | `database/northwind.db` | SQLite database (relative to project root) |
| `MAX_SQL_RETRIES` | `3` | Self-correction attempts per SQL query |
| `MAX_DATA_QUERIES` | `3` | Max datasets the planner may request |

---

## Dataset notes

- **Northwind** sample database: orders from **1996-07-04 to 1998-05-06** (830 orders, 2,155 order lines, 77 products, 91 customers, 9 employees).
- 1996 (Jul–Dec) and 1998 (Jan–early May) are **partial years**. The analysis layer detects partial periods automatically, uses like-for-like comparisons, and warns in the report.
- `Discount` is 0 for all rows in this copy of the data, so sales = `UnitPrice × Quantity`.
- Some accented product names lost their accents in the source CSVs (e.g. `Cte de Blaye` = *Côte de Blaye*).

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot reach Ollama` | Start Ollama (`ollama serve`) and check `OLLAMA_BASE_URL`. |
| `model "llama3.2" not found` | `ollama pull llama3.2` |
| `quota / rate limit exceeded` (Gemini) | Wait a minute, or change `GEMINI_MODEL` (daily limits are per model). |
| SQL fails after 3 attempts | Rephrase the question more concretely, or use a larger model. |
| Slow responses on Ollama | Normal on CPU. Each question makes about 6 LLM calls. A GPU or a smaller model helps. |

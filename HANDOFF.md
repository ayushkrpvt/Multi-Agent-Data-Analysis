# Handoff Notes: Running on Your Machine with Ollama

The project was developed and tested with **Google Gemini** because Ollama wasn't available on the dev machine. The code is provider-agnostic, so switching to **local Ollama** needs **no code changes**, only the `.env` file.

## Steps

1. **Install Ollama:** https://ollama.com/download

2. **Download the model** (one time):
   ```bash
   ollama pull llama3.2
   ```

3. **Create your `.env`** in the project folder:
   ```bash
   cp .env.example .env          # Windows: copy .env.example .env
   ```
   Make sure it contains:
   ```ini
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama3.2
   OLLAMA_BASE_URL=http://localhost:11434
   ```
   (`GOOGLE_API_KEY` can stay empty.)

4. **Install Python packages:**
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
   `langchain-google-genai` is only needed for Gemini. You can delete that line from `requirements.txt` if you like.

5. **Check that Ollama works with the project:**
   ```bash
   python -m tests.test_llm_connection
   ```
   It should print `LLM: Ollama (llama3.2)` and `LLM connection OK`.

6. **Run:**
   ```bash
   streamlit run app.py
   ```

## What changes between Gemini and Ollama

| Setting | Gemini (dev) | Ollama (yours) |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `ollama` |
| Model variable | `GEMINI_MODEL` | `OLLAMA_MODEL` |
| API key | `GOOGLE_API_KEY` required | not needed |
| JSON mode | `response_mime_type=application/json` | `format="json"` |

All of this is handled automatically in `tools/llm.py`. It is the only file that knows about providers.

## Tool calling and Ollama models

The agents use **native tool calling** (`bind_tools`), so the Ollama model must support tools:

| Model | Tools? | Notes |
|---|---|---|
| `llama3.2` (default) | ✅ | fast, basic quality |
| `llama3.1:8b` | ✅ | better |
| `qwen2.5:7b` | ✅ | best for SQL / tool calling on a laptop |
| `gemma3` / `gemma2` | ❌ | not supported, error "does not support tools" |

If a small model answers in plain text instead of calling a tool, the code falls back to JSON mode automatically. The run continues, but quality may drop.

## Tips for best results locally

- **Better model = better SQL and reports.** `llama3.2` is a 3B model and is fast but basic. If your laptop has 16 GB+ RAM, try one of these, then set `OLLAMA_MODEL` to its name:
  ```bash
  ollama pull qwen2.5:7b        # strong at SQL and JSON
  ollama pull llama3.1:8b
  ```
- **Slow?** Each question makes about 6–8 LLM calls, which can take 1–3 minutes on CPU. If a call times out, raise `LLM_TIMEOUT=600` in `.env`.
- **If SQL keeps failing** on complex questions with `llama3.2`, raise `MAX_SQL_RETRIES=5` or use a bigger model.
- **Context size** is set to 8192 tokens (`num_ctx`) in `tools/llm.py`, enough for the schema plus data.

## Deliverables checklist

| Deliverable | Where |
|---|---|
| Source code | this repository |
| Architecture diagram | `README.md` (Mermaid) and `docs/ARCHITECTURE.md` (detailed + auto-generated LangGraph graph) |
| README & setup | `README.md` |
| Sample questions & outputs | `docs/samples/` (8 full reports with charts) |
| Final project report | `docs/PROJECT_REPORT.md` |
| Demo video | record it yourself, following `docs/DEMO_SCRIPT.md` |

> The sample outputs in `docs/samples/` were generated with Gemini. You can regenerate them with your local model by running `python -m scripts.generate_samples`. The numbers will be identical because they are computed in Python. Only the wording of the text changes.

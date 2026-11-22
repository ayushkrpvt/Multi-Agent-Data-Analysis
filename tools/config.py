"""
Central configuration. Every setting can be overridden from the .env file.

Switching LLM provider
----------------------
LLM_PROVIDER=ollama   -> local Ollama (default model: llama3.2)
LLM_PROVIDER=gemini   -> Google Gemini API (needs GOOGLE_API_KEY)
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = folder that contains app.py
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# ----------------------------------------
# LLM settings
# ----------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

# Ollama
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Gemini
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0))

# Seconds before a single LLM request is abandoned (local CPU models can be slow)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", 300))

# How many times to re-ask the LLM when it returns invalid JSON
MAX_JSON_RETRIES = int(os.getenv("MAX_JSON_RETRIES", 2))

# ----------------------------------------
# Database / pipeline settings
# ----------------------------------------

DB_PATH = str(BASE_DIR / os.getenv("DB_PATH", "database/northwind.db"))

MAX_SQL_RETRIES = int(os.getenv("MAX_SQL_RETRIES", 3))

# Hard cap on rows returned by any generated query
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", 5000))

# Maximum number of SQL data queries the planner may request
MAX_DATA_QUERIES = int(os.getenv("MAX_DATA_QUERIES", 3))

# How many times the Analysis Agent may send the workflow back to Planning + SQL
MAX_REPLANS = int(os.getenv("MAX_REPLANS", 2))

# ----------------------------------------
# Paths
# ----------------------------------------

PROMPTS_DIR = BASE_DIR / "prompts"
SCHEMA_DIR = BASE_DIR / "schema"
OUTPUTS_DIR = BASE_DIR / "outputs"
CHARTS_DIR = OUTPUTS_DIR / "charts"
REPORTS_DIR = OUTPUTS_DIR / "reports"

CHARTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_prompt(name: str) -> str:
    """Read a prompt template from prompts/<name>.txt"""
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


def llm_description() -> str:
    """Human readable name of the active LLM (shown in UI / reports)."""
    if LLM_PROVIDER == "gemini":
        return f"Gemini ({GEMINI_MODEL})"
    return f"Ollama ({OLLAMA_MODEL})"

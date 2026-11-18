"""
Check that the configured LLM (Ollama or Gemini) is reachable and returns JSON.

    python -m tests.test_llm_connection
"""

from pydantic import BaseModel

from tools.config import llm_description
from tools.llm import invoke_json, invoke_text


class Ping(BaseModel):
    status: str


if __name__ == "__main__":
    print("LLM:", llm_description())
    print("Text :", invoke_text("Reply with exactly one word: hello"))
    print("JSON :", invoke_json('Return this JSON: {"status": "ok"}', Ping))
    print("LLM connection OK")

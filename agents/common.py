"""Helpers shared by all agents."""

import functools
import time
import traceback


def friendly_error(e: Exception) -> str:
    """Short, actionable messages for the most common LLM failures."""
    msg = str(e)
    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
        return ("LLM API quota / rate limit exceeded. Wait a minute (per-minute limit) or switch "
                "GEMINI_MODEL in .env (daily limits are per model).")
    if "503" in msg or "UNAVAILABLE" in msg:
        return "LLM service temporarily overloaded (503). Please try again in a minute."
    if "timed out" in msg.lower() or "timeout" in msg.lower():
        return "LLM request timed out. Increase LLM_TIMEOUT in .env or use a smaller/faster model."
    if "Connection refused" in msg or "ConnectError" in msg or "Failed to connect" in msg:
        return "Cannot reach Ollama. Start it with `ollama serve` and check OLLAMA_BASE_URL in .env."
    if "not found" in msg.lower() and "model" in msg.lower():
        return f"Model not found. For Ollama run `ollama pull <model>`. Details: {msg[:200]}"
    return msg[:500]


def traced(agent: str, step: str = ""):
    """
    Decorator for LangGraph nodes.
    Times the node and appends an entry to state["trace"] so the UI and the
    report can show exactly which agent did what (explainability).
    A node may return "_detail" in its update to describe its result.
    """

    def wrap(fn):

        @functools.wraps(fn)
        def node(state):
            start = time.time()
            try:
                update = fn(state) or {}
                status = ("error" if update.get("error")
                          else "blocked" if (update.get("guardrail") or {}).get("blocked")
                          else "ok")
            except Exception as e:
                traceback.print_exc()
                update = {"error": f"{agent} failed: {friendly_error(e)}"}
                status = "error"

            detail = update.pop("_detail", update.get("error", ""))
            entry = {
                "agent": agent,
                "step": step or fn.__name__,
                "status": status,
                "detail": detail,
                "seconds": round(time.time() - start, 2),
            }
            print(f"[{agent}] {entry['step']}: {status} ({entry['seconds']}s) {detail}")
            update["trace"] = [entry]
            return update

        return node

    return wrap

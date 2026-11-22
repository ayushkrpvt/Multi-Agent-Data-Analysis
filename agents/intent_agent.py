"""
Agent 1 - Intent Understanding Agent (with guardrails)

Understands the business question and extracts KPIs, dimensions, filters and
time period. It does NOT decide the analysis type (the Analysis Agent does).

Guardrails (inside this agent, no extra node):
  Layer 1 - deterministic checks in Python: empty / too long input, requests to
            modify data, prompt-injection attempts.
  Layer 2 - native tool calling: the LLM must call either
            submit_intent(...)        -> question is answerable from Northwind
            reject_out_of_scope(...)  -> friendly message, workflow stops
"""

import re
from typing import Optional

from agents.common import traced
from models.intent_model import IntentOutput, OutOfScope
from tools.config import load_prompt
from tools.llm import invoke_json
from tools.schema_tool import get_table_overview, normalize_tables
from tools.tool_calling import final_tool, run_tool_loop

EXAMPLES = ('For example: "Compare sales by product category", '
            '"Who are the top 10 customers by revenue?" or "Why did beverage sales decline in 1998?"')

SCOPE = ("I'm a business analytics assistant for the Northwind sales database, so I can answer "
         "questions about sales, orders, products, categories, customers, countries, employees, "
         "suppliers and shipping (July 1996 – May 1998).")

_WRITE_PATTERNS = [
    r"\b(delete|truncate|wipe|erase|overwrite)\b",
    r"\bdrop\s+(the\s+)?(table|tables|database|column|columns|schema)\b",
    r"^\s*(insert|update|alter|create)\b",
    r"\b(insert into|update \w+ set|alter table|create table)\b",
    r"\b(change|modify|update|edit|set)\s+(the\s+)?(price|prices|record|records|row|rows|value|values|data|database|table)\b",
]
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules)",
    r"\b(system|developer)\s+prompt\b",
    r"\breveal\s+(your\s+)?(prompt|instructions|api\s*key|secret)",
    r"\bjailbreak\b|\bdan mode\b|\bdeveloper mode\b",
    r"\b(api[_\s-]?key|password|credentials)\b",
]


def precheck_guardrails(question: str) -> Optional[OutOfScope]:
    """Layer 1: cheap deterministic guardrails (no LLM call)."""

    q = (question or "").strip()
    low = q.lower()

    if re.fullmatch(r"(hi|hello|hey|hii+|good (morning|afternoon|evening)|thanks|thank you|ok|okay|"
                    r"how are you|who are you|what can you do)[\s!.?]*", low):
        return OutOfScope(category="greeting", reason="greeting / small talk",
                          message=f"Hi! 👋 {SCOPE} {EXAMPLES}")

    if len(q) < 3 or not re.search(r"[a-zA-Z]", q):
        return OutOfScope(category="unclear", reason="empty or too short",
                          message=f"Please type a business question. {EXAMPLES}")

    if len(q) > 1000:
        return OutOfScope(category="unclear", reason="question too long",
                          message="That's a bit long for me. Please ask one business question in a sentence or two. "
                                  + EXAMPLES)

    if any(re.search(p, low) for p in _INJECTION_PATTERNS):
        return OutOfScope(category="unsafe_request", reason="prompt injection / secrets request",
                          message=f"Sorry, I can't help with that. {SCOPE} {EXAMPLES}")

    if any(re.search(p, low) for p in _WRITE_PATTERNS):
        return OutOfScope(category="unsafe_request", reason="request to modify data",
                          message="I can only read and analyse the data. I'm not able to change, add or delete "
                                  f"records. {EXAMPLES}")

    return None


def build_prompts(question: str):
    system = load_prompt("intent_prompt").replace("{table_overview}", get_table_overview())
    user = f"Question: {question}\n\nCall submit_intent or reject_out_of_scope."
    return system, user


def _blocked(decision: OutOfScope, layer: str):
    return {
        "guardrail": {"blocked": True, "layer": layer, **decision.model_dump()},
        "_detail": f"BLOCKED ({layer}, {decision.category}): {decision.reason}",
    }


@traced("Intent Agent", "understand question + guardrails")
def intent_agent(state):

    question = state["user_query"]

    # ---- Guardrail layer 1 (deterministic) ----
    decision = precheck_guardrails(question)
    if decision:
        return _blocked(decision, "rule-based check")

    # ---- Native tool calling: submit_intent OR reject_out_of_scope ----
    system, user = build_prompts(question)
    tool_log = []
    try:
        result = run_tool_loop(
            system, user,
            final_tools={
                "submit_intent": final_tool(
                    "submit_intent", "Submit the structured intent of an answerable Northwind question.",
                    IntentOutput),
                "reject_out_of_scope": final_tool(
                    "reject_out_of_scope", "Guardrail: refuse questions that cannot or must not be answered "
                                           "from the Northwind data, with a friendly message.", OutOfScope),
            },
            max_steps=3, agent="Intent Agent",
        )
        tool_log = result.log
        if result.final_tool == "reject_out_of_scope":
            return {**_blocked(result.args, "LLM guardrail"), "tool_calls": [{"agent": "Intent Agent", **c} for c in tool_log]}
        intent = result.args
    except Exception as e:
        # Fallback for models with weak tool calling: plain JSON mode
        print(f"[Intent Agent] tool calling failed ({e}); falling back to JSON mode")
        intent = invoke_json(f"{system}\n\n{user}\nReturn ONLY the submit_intent arguments as JSON.", IntentOutput)

    # Validation of intermediate result: keep only tables that really exist
    intent.required_tables = normalize_tables(intent.required_tables) or ["orders", "order_details"]
    if not intent.business_question:
        intent.business_question = question

    return {
        "intent": intent.model_dump(),
        "guardrail": {"blocked": False},
        "tool_calls": [{"agent": "Intent Agent", **c} for c in tool_log],
        "_detail": f"metric={intent.metric} | dims={intent.dimensions} | filters={intent.filters} "
                   f"| period={intent.time_period}",
    }

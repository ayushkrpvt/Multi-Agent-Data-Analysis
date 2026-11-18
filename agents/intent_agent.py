"""
Agent 1 - Intent Understanding Agent
Understands the business question and extracts KPIs, dimensions, filters,
time period and analysis type as structured, validated JSON.
"""

from agents.common import traced
from models.intent_model import IntentOutput
from tools.config import load_prompt
from tools.llm import invoke_json
from tools.schema_tool import get_table_overview, normalize_tables


def build_prompt(question: str) -> str:
    template = load_prompt("intent_prompt").replace("{table_overview}", get_table_overview())
    return f"{template}\n\nQuestion: {question}\n\nReturn ONLY JSON."


@traced("Intent Agent", "understand question")
def intent_agent(state):

    question = state["user_query"]

    intent = invoke_json(build_prompt(question), IntentOutput)

    # Validation of intermediate result: keep only tables that really exist
    intent.required_tables = normalize_tables(intent.required_tables) or ["orders", "order_details"]
    if not intent.business_question:
        intent.business_question = question

    return {
        "intent": intent.model_dump(),
        "_detail": f"{intent.analysis_type} | metric={intent.metric} | dims={intent.dimensions} "
                   f"| filters={intent.filters} | period={intent.time_period}",
    }

"""
LangGraph workflow that orchestrates the five agents.

 START
   -> intent_agent        (Agent 1, guardrails: off-topic question -> END with friendly message)
   -> planning_agent      (Agent 2)
   -> sql_generate -> sql_validate -> sql_execute   (Agent 3, self-correcting retry loop)
   -> analysis_agent      (Agent 4, single node; picks the analysis type via tool calling)
        -> not enough data?  back to planning_agent -> SQL agent -> analysis_agent
   -> reporting_agent     (Agent 5)
 END
"""

import re
import uuid
from datetime import datetime
from typing import Callable, Optional

from langgraph.graph import END, START, StateGraph

from agents.analysis_agent import analysis_agent, route_after_analysis
from agents.intent_agent import intent_agent
from agents.planning_agent import planning_agent
from agents.reporting_agent import reporting_agent
from agents.sql_agent import (
    route_after_execute, route_after_give_up, route_after_validate,
    sql_execute, sql_generate, sql_give_up, sql_validate,
)
from graph.state import AnalyticsState

APPEND_KEYS = ("trace", "sql_attempts", "tool_calls")


def _stop_on_error(next_node):
    """Conditional edge: go to END if the previous node set state['error']."""
    def route(state):
        return END if state.get("error") else next_node
    return route


def route_after_intent(state):
    if state.get("error") or (state.get("guardrail") or {}).get("blocked"):
        return END
    return "planning_agent"


def build_graph():

    g = StateGraph(AnalyticsState)

    g.add_node("intent_agent", intent_agent)
    g.add_node("planning_agent", planning_agent)
    g.add_node("sql_generate", sql_generate)
    g.add_node("sql_validate", sql_validate)
    g.add_node("sql_execute", sql_execute)
    g.add_node("sql_give_up", sql_give_up)
    g.add_node("analysis_agent", analysis_agent)
    g.add_node("reporting_agent", reporting_agent)

    g.add_edge(START, "intent_agent")
    g.add_conditional_edges("intent_agent", route_after_intent, ["planning_agent", END])
    g.add_conditional_edges("planning_agent", _stop_on_error("sql_generate"), ["sql_generate", END])
    g.add_conditional_edges("sql_generate", _stop_on_error("sql_validate"), ["sql_validate", END])

    g.add_conditional_edges("sql_validate", route_after_validate, {
        "execute": "sql_execute", "retry": "sql_generate", "give_up": "sql_give_up",
    })
    g.add_conditional_edges("sql_execute", route_after_execute, {
        "retry": "sql_generate", "give_up": "sql_give_up",
        "next_query": "sql_generate", "analyze": "analysis_agent",
    })
    g.add_conditional_edges("sql_give_up", route_after_give_up, {
        "fail": END, "next_query": "sql_generate", "analyze": "analysis_agent",
    })

    g.add_conditional_edges("analysis_agent", route_after_analysis, {
        "replan": "planning_agent",      # information not sufficient -> Planning + SQL again
        "report": "reporting_agent",
        "fail": END,
    })

    g.add_edge("reporting_agent", END)

    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def new_run_id(question: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", question.lower()).strip("_")[:30] or "question"
    return f"{datetime.now():%Y%m%d_%H%M%S}_{slug}_{uuid.uuid4().hex[:4]}"


def run_analysis(question: str, on_step: Optional[Callable[[str, dict], None]] = None) -> dict:
    """
    Run the full multi-agent pipeline.
    on_step(node_name, update) is called after every agent step (for live UI progress).
    Returns the final state.
    """

    state = {"user_query": question, "run_id": new_run_id(question),
             "trace": [], "sql_attempts": [], "tool_calls": []}

    final = dict(state)
    for chunk in get_graph().stream(state, stream_mode="updates", config={"recursion_limit": 150}):
        for node, update in chunk.items():
            update = update or {}
            for k, v in update.items():
                if k in APPEND_KEYS:
                    final[k] = final.get(k, []) + v
                else:
                    final[k] = v
            if on_step:
                on_step(node, update)

    return final


def mermaid_diagram() -> str:
    """Mermaid source of the compiled graph (used for the architecture diagram)."""
    return get_graph().get_graph().draw_mermaid()

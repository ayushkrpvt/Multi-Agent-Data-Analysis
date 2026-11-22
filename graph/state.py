"""
Shared state passed between agents in the LangGraph workflow.

Each agent reads what it needs and returns ONLY the keys it updates.
`trace`, `sql_attempts` and `tool_calls` use an add-reducer, so every agent
appends to them (full audit trail of the multi-agent collaboration).
"""

import operator
from typing import Annotated, Dict, List, Optional, TypedDict


class AnalyticsState(TypedDict, total=False):

    # Input
    user_query: str
    run_id: str

    # Agent 1 - Intent Understanding (+ guardrails)
    intent: Dict
    guardrail: Dict               # {"blocked": bool, "category", "reason", "message", "layer"}

    # Agent 2 - Planning
    plan: Dict
    data_queries: List[Dict]

    # Agent 3 - SQL Generation (loop state)
    query_index: int              # which data query is being worked on
    sql_attempt: int              # attempt number for the current query
    current_sql: str
    sql_error: Optional[str]      # validation / execution feedback for retry
    sql_attempts: Annotated[List[Dict], operator.add]   # audit log of all attempts
    query_results: Dict[str, Dict]                      # query_id -> QueryResult
    failed_queries: List[str]

    # Agent 4 - Analysis
    profiles: Dict[str, Dict]
    analysis_route: str           # analysis type chosen by the Analysis Agent
    analysis_facts: Dict          # numbers computed in Python by the analysis tools
    analysis: Dict                # LLM interpretation (AnalysisOutput)
    analysis_request: Optional[Dict]   # request_more_data -> triggers re-planning
    replan_count: int

    # Agent 5 - Reporting
    charts: List[Dict]
    report: Dict                  # ReportOutput
    report_markdown: str
    report_path: str

    # Bookkeeping
    tool_calls: Annotated[List[Dict], operator.add]     # every native tool call made by any agent
    trace: Annotated[List[Dict], operator.add]
    error: Optional[str]

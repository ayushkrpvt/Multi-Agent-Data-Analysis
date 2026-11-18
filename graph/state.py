"""
Shared state passed between agents in the LangGraph workflow.

Each agent reads what it needs and returns ONLY the keys it updates.
`trace` and `sql_attempts` use an add-reducer, so every agent appends
to them (full audit trail of the multi-agent collaboration).
"""

import operator
from typing import Annotated, Dict, List, Optional, TypedDict


class AnalyticsState(TypedDict, total=False):

    # Input
    user_query: str
    run_id: str

    # Agent 1 - Intent Understanding
    intent: Dict

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
    analysis_route: str           # branch actually taken
    analysis_facts: Dict          # numbers computed in Python
    analysis: Dict                # LLM interpretation (AnalysisOutput)

    # Agent 5 - Reporting
    charts: List[Dict]
    report: Dict                  # ReportOutput
    report_markdown: str
    report_path: str

    # Bookkeeping
    trace: Annotated[List[Dict], operator.add]
    error: Optional[str]

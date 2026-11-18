from typing import List, Optional

from pydantic import BaseModel, Field


class SQLAttempt(BaseModel):
    """One generate -> validate -> execute attempt (kept for explainability)."""

    query_id: str
    attempt: int
    sql: str
    status: str  # "passed", "validation_failed", "execution_failed", "empty_result"
    error: Optional[str] = None


class QueryResult(BaseModel):
    """Final successful result for one data query."""

    query_id: str
    purpose: str = ""
    description: str = ""
    sql: str
    row_count: int
    columns: List[str] = Field(default_factory=list)
    records: List[dict] = Field(default_factory=list)

from typing import List

from pydantic import BaseModel, Field, field_validator

from models.common import Str, StrList


class DataQuery(BaseModel):
    """One dataset the SQL agent must retrieve."""

    id: Str = Field(description="short snake_case id, e.g. primary, by_product")
    purpose: Str = Field(default="", description="why this data is needed")
    description: Str = Field(description="precise description of the rows/columns to return")


class PlanOutput(BaseModel):
    """Structured output from the Planning Agent."""

    objective: Str
    analysis_steps: StrList = Field(default_factory=list)
    required_tables: StrList = Field(default_factory=list)
    group_by: StrList = Field(default_factory=list)
    required_kpis: StrList = Field(default_factory=list)
    data_queries: List[DataQuery] = Field(default_factory=list)
    chart_suggestion: Str = Field(default="", description="line, bar, grouped_bar, pie")

    @field_validator("data_queries", mode="before")
    @classmethod
    def _coerce_queries(cls, v):
        if not v:
            return []
        if isinstance(v, dict):
            v = [v]
        out = []
        for i, q in enumerate(v):
            if isinstance(q, str):
                q = {"id": f"query_{i + 1}", "description": q}
            if isinstance(q, dict):
                q.setdefault("id", f"query_{i + 1}")
                q.setdefault("description", q.get("purpose", ""))
            out.append(q)
        return out

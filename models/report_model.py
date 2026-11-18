from typing import List

from pydantic import BaseModel, Field, field_validator

from models.common import Str, StrList


class Recommendation(BaseModel):
    action: Str
    rationale: Str = ""
    priority: Str = "Medium"

    @field_validator("priority", mode="before")
    @classmethod
    def _prio(cls, v):
        v = str(v or "Medium").strip().capitalize()
        return v if v in {"High", "Medium", "Low"} else "Medium"


class ReportOutput(BaseModel):
    """Executive report produced by the Reporting Agent."""

    title: Str
    business_summary: Str
    key_findings: StrList = Field(default_factory=list)
    root_cause_analysis: StrList = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    next_questions: StrList = Field(default_factory=list)

    @field_validator("recommendations", mode="before")
    @classmethod
    def _recs(cls, v):
        if not v:
            return []
        if isinstance(v, (str, dict)):
            v = [v]
        return [{"action": r} if isinstance(r, str) else r for r in v]

from typing import List

from pydantic import BaseModel, Field

from models.common import Str, StrList


class KeyFinding(BaseModel):
    finding: Str
    value: Str = ""


class Insight(BaseModel):
    insight: Str
    business_implication: Str = ""


class AnalysisOutput(BaseModel):
    """LLM interpretation of the statistics computed by the analysis tools."""

    summary: Str
    key_findings: List[KeyFinding] = Field(default_factory=list)
    insights: List[Insight] = Field(default_factory=list)
    drivers: StrList = Field(default_factory=list, description="business drivers / root causes")
    anomalies: StrList = Field(default_factory=list)
    caveats: StrList = Field(default_factory=list, description="data limitations")

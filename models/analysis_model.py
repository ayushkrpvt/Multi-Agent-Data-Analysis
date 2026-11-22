from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

from models.common import Str, StrList

ANALYSIS_TYPES = ("trend", "comparison", "rank", "root_cause", "anomaly")
AnalysisType = Literal["trend", "comparison", "rank", "root_cause", "anomaly"]


def normalize_analysis_type(value) -> str:
    v = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if v in ANALYSIS_TYPES:
        return v
    if "root" in v or "cause" in v or "driver" in v or "why" in v:
        return "root_cause"
    if "anomal" in v or "outlier" in v or "spike" in v:
        return "anomaly"
    if "rank" in v or "top" in v or "leader" in v:
        return "rank"
    if "trend" in v or "time" in v or "growth" in v:
        return "trend"
    return "comparison"


class KeyFinding(BaseModel):
    finding: Str
    value: Str = ""


class Insight(BaseModel):
    insight: Str
    business_implication: Str = ""


class AnalysisOutput(BaseModel):
    """Final output of the Analysis Agent (arguments of the submit_analysis tool)."""

    analysis_type: AnalysisType = Field(description="trend, comparison, rank, root_cause or anomaly")
    summary: Str = Field(description="2-3 sentence answer to the question, citing computed numbers")
    key_findings: List[KeyFinding] = Field(default_factory=list)
    insights: List[Insight] = Field(default_factory=list)
    drivers: StrList = Field(default_factory=list, description="business drivers / root causes")
    anomalies: StrList = Field(default_factory=list)
    caveats: StrList = Field(default_factory=list, description="data limitations, e.g. partial periods")

    @field_validator("analysis_type", mode="before")
    @classmethod
    def _norm(cls, v):
        return normalize_analysis_type(v)

    @field_validator("key_findings", mode="before")
    @classmethod
    def _findings(cls, v):
        v = [v] if isinstance(v, (str, dict)) else (v or [])
        return [{"finding": x} if isinstance(x, str) else x for x in v]

    @field_validator("insights", mode="before")
    @classmethod
    def _insights(cls, v):
        v = [v] if isinstance(v, (str, dict)) else (v or [])
        return [{"insight": x} if isinstance(x, str) else x for x in v]


class MoreDataRequest(BaseModel):
    """Arguments of request_more_data: sends the workflow back to Planning + SQL."""

    reason: Str = Field(description="Why the current data is not sufficient to answer the question")
    needed_data: StrList = Field(description="Datasets still needed, each with exact columns, "
                                             "e.g. 'Monthly Sales by ProductName for Beverages, columns: Month, ProductName, Sales'")

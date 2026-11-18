from typing import Literal

from pydantic import BaseModel, Field, field_validator

from models.common import Str, StrList

AnalysisType = Literal["trend", "comparison", "root_cause", "anomaly"]


def normalize_analysis_type(value) -> str:
    v = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    if v in {"trend", "comparison", "root_cause", "anomaly"}:
        return v
    if "root" in v or "cause" in v or "why" in v or "driver" in v:
        return "root_cause"
    if "anomal" in v or "outlier" in v or "unusual" in v:
        return "anomaly"
    if "trend" in v or "time" in v or "growth" in v:
        return "trend"
    return "comparison"


class IntentOutput(BaseModel):
    """Structured output from the Intent Understanding Agent."""

    business_question: Str = Field(description="Original business question")
    metric: Str = Field(description="Main KPI, e.g. Sales, Orders, Quantity")
    kpis: StrList = Field(default_factory=list, description="All KPIs needed")
    dimensions: StrList = Field(default_factory=list, description="Group-by dimensions")
    filters: StrList = Field(default_factory=list, description="Filters, e.g. Category = Beverages")
    time_period: Str = Field(default="All", description="Time period, 'All' if none")
    time_granularity: Str = Field(default="none", description="year, quarter, month or none")
    analysis_type: AnalysisType = Field(description="trend, comparison, root_cause, anomaly")
    required_tables: StrList = Field(default_factory=list, description="Northwind tables needed")

    @field_validator("analysis_type", mode="before")
    @classmethod
    def _norm_type(cls, v):
        return normalize_analysis_type(v)

    @field_validator("time_period", mode="before")
    @classmethod
    def _norm_period(cls, v):
        return str(v).strip() if v not in (None, "", []) else "All"

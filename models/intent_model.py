from typing import Literal

from pydantic import BaseModel, Field, field_validator

from models.common import Str, StrList


class IntentOutput(BaseModel):
    """
    Structured output from the Intent Understanding Agent.
    (The analysis type is NOT decided here - the Analysis Agent decides it.)
    """

    business_question: Str = Field(description="Original business question")
    metric: Str = Field(description="Main KPI, e.g. Sales, Orders, Quantity, Average Order Value")
    kpis: StrList = Field(default_factory=list, description="All KPIs needed, main KPI first")
    dimensions: StrList = Field(default_factory=list, description="Group-by dimensions, e.g. Month, Category, Country")
    filters: StrList = Field(default_factory=list, description="Filters as 'Field = Value', e.g. 'Category = Beverages'")
    time_period: Str = Field(default="All", description="Time period mentioned, 'All' if none")
    time_granularity: Str = Field(default="none", description="year, quarter, month or none")
    required_tables: StrList = Field(default_factory=list, description="Northwind tables needed")

    @field_validator("time_period", mode="before")
    @classmethod
    def _norm_period(cls, v):
        return str(v).strip() if v not in (None, "", []) else "All"


class OutOfScope(BaseModel):
    """Guardrail decision: the question cannot be answered from the Northwind database."""

    category: Literal["off_topic", "greeting", "unsafe_request", "unanswerable", "unclear"] = Field(
        description="off_topic: unrelated to the business data; greeting: hello/thanks/small talk; "
                    "unsafe_request: asks to modify/delete data or reveal system internals; "
                    "unanswerable: business question but the data does not exist in Northwind; "
                    "unclear: too vague to analyse"
    )
    reason: Str = Field(description="Short internal reason")
    message: Str = Field(description="Friendly reply to the user explaining what you can help with, "
                                     "with 1-2 example questions about the Northwind data")

"""Shared helpers to make Pydantic models tolerant of small-LLM output quirks."""

from typing import Any, List

from pydantic import BeforeValidator
from typing_extensions import Annotated


def _to_str_list(value: Any) -> List[str]:
    """Accept None, a string, a list of strings, or a list of dicts."""

    if value is None:
        return []

    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in {"none", "n/a", "null", "all"}:
            return []
        return [v.strip() for v in value.split(",") if v.strip()] if "," in value else [value]

    if isinstance(value, dict):
        return [f"{k}: {v}" for k, v in value.items()]

    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            if isinstance(item, dict):
                out.append(", ".join(f"{k}: {v}" for k, v in item.items()))
            elif item is not None and str(item).strip():
                out.append(str(item).strip())
        return out

    return [str(value)]


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    return str(value)


StrList = Annotated[List[str], BeforeValidator(_to_str_list)]
Str = Annotated[str, BeforeValidator(_to_str)]

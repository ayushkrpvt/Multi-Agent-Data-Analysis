"""
Native tool-calling loop shared by all agents.

How it works (provider-agnostic: Gemini and Ollama both support bind_tools):

    1. The LLM is bound to a set of tools:
         - "work" tools      : Python functions the agent may call (schema lookup,
                               statistics, ...). Their results are sent back to the LLM.
         - "final" tools     : the agent's answer (e.g. submit_intent, submit_sql_query).
                               Their arguments are validated with a Pydantic model.
    2. Loop: LLM -> tool calls -> execute -> ToolMessage results -> LLM ...
    3. The loop ends when the LLM calls a final tool with valid arguments.
       Invalid arguments are returned to the LLM as an error so it can correct itself.
    4. On the last allowed step only the final tools are offered, forcing an answer.
    5. If the model answers in plain text instead of a tool call (small local models
       sometimes do), the text is parsed as JSON for the final tool as a fallback.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ValidationError

from tools.llm import _invoke, extract_json, get_llm, response_text

MAX_TOOL_RESULT_CHARS = 6000


class ToolLoopError(RuntimeError):
    pass


@dataclass
class ToolLoopResult:
    final_tool: str
    args: Any                      # validated Pydantic object (or dict)
    log: List[Dict] = field(default_factory=list)
    steps: int = 0


def final_tool(name: str, description: str, schema: Type[BaseModel]) -> StructuredTool:
    """Create a 'final answer' tool whose arguments follow a Pydantic schema."""

    def _accept(**kwargs):
        return "accepted"

    return StructuredTool.from_function(
        func=_accept, name=name, description=description, args_schema=schema,
    )


def work_tool(func: Callable, name: str, description: str,
              schema: Optional[Type[BaseModel]] = None) -> StructuredTool:
    """Wrap a Python function as a tool the LLM can call."""
    return StructuredTool.from_function(
        func=func, name=name, description=description, args_schema=schema,
    )


def _short(value, limit=MAX_TOOL_RESULT_CHARS) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + " ... (truncated)"


def run_tool_loop(
    system_prompt: str,
    user_prompt: str,
    final_tools: Dict[str, StructuredTool],
    work_tools: Optional[List[BaseTool]] = None,
    max_steps: int = 5,
    agent: str = "",
) -> ToolLoopResult:
    """Run the LLM <-> tools loop until a final tool is called with valid arguments."""

    work_tools = work_tools or []
    work_map = {t.name: t for t in work_tools}
    finals = list(final_tools.values())

    llm_all = get_llm().bind_tools(work_tools + finals)
    llm_final_only = get_llm().bind_tools(finals)

    messages = [SystemMessage(system_prompt), HumanMessage(user_prompt)]
    log: List[Dict] = []
    final_names = ", ".join(final_tools)

    for step in range(1, max_steps + 1):

        last_step = step == max_steps
        if last_step and len(messages) > 2:
            messages.append(HumanMessage(
                f"Step limit reached. Answer now by calling one of: {final_names}."
            ))

        response = _invoke(llm_final_only if (last_step or not work_tools) else llm_all, messages)
        messages.append(response)
        calls = response.tool_calls or []

        if not calls:
            # Fallback for models that reply in text: parse JSON for a single final tool
            text = response_text(response)
            if len(final_tools) == 1 or last_step:
                for name, tool in final_tools.items():
                    try:
                        args = tool.args_schema.model_validate(extract_json(text))
                        log.append({"step": step, "tool": name, "args": "(parsed from text)", "result": "accepted"})
                        return ToolLoopResult(name, args, log, step)
                    except Exception:
                        continue
            messages.append(HumanMessage(
                f"Do not answer in plain text. You must call a tool. Final tools: {final_names}."
            ))
            continue

        final_result = None
        tool_messages = []

        for call in calls:
            name, args = call["name"], call.get("args") or {}

            if name in final_tools:
                try:
                    validated = final_tools[name].args_schema.model_validate(args)
                    result = "accepted"
                    if final_result is None:
                        final_result = ToolLoopResult(name, validated, log, step)
                except ValidationError as e:
                    result = (f"Invalid arguments for {name}: {str(e)[:600]}. "
                              f"Call {name} again with corrected arguments.")

            elif name in work_map:
                try:
                    result = work_map[name].invoke(args)
                except Exception as e:
                    result = f"Error: {e}"

            else:
                result = f"Unknown tool '{name}'. Available: {', '.join(list(work_map) + list(final_tools))}"

            log.append({"step": step, "tool": name, "args": _short(args, 400), "result": _short(result, 300)})
            if agent:
                print(f"   [{agent}] tool call: {name}({_short(args, 120)})")

            tool_messages.append(ToolMessage(content=_short(result), tool_call_id=call.get("id") or name, name=name))

        messages.extend(tool_messages)

        if final_result is not None:
            final_result.log = log
            return final_result

    raise ToolLoopError(f"No valid final tool call ({final_names}) after {max_steps} steps.")

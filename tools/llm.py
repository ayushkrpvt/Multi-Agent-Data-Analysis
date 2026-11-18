"""
LLM factory + structured-output helper.

This is the ONLY file that knows which LLM provider is used.
Agents call:
    get_llm()                      -> chat model for free text / SQL
    get_json_llm()                 -> chat model forced into JSON mode
    invoke_json(prompt, Model)     -> validated Pydantic object (with retries)

Provider is chosen by LLM_PROVIDER in .env  ("ollama" or "gemini").
"""

import json
import re
from functools import lru_cache
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from tools import config

T = TypeVar("T", bound=BaseModel)


# ----------------------------------------
# Model factories
# ----------------------------------------

def _build(json_mode: bool):

    if config.LLM_PROVIDER == "gemini":

        from langchain_google_genai import ChatGoogleGenerativeAI

        if not config.GOOGLE_API_KEY:
            raise RuntimeError(
                "LLM_PROVIDER=gemini but GOOGLE_API_KEY is not set in .env"
            )

        kwargs = dict(
            model=config.GEMINI_MODEL,
            google_api_key=config.GOOGLE_API_KEY,
            max_retries=2,  # per-minute rate limits -> short automatic backoff
            timeout=config.LLM_TIMEOUT,
        )

        # Gemini 3.x models use fixed sampling and warn if temperature is passed
        if not config.GEMINI_MODEL.startswith("gemini-3"):
            kwargs["temperature"] = config.LLM_TEMPERATURE

        if json_mode:
            kwargs["response_mime_type"] = "application/json"

        return ChatGoogleGenerativeAI(**kwargs)

    if config.LLM_PROVIDER == "ollama":

        from langchain_ollama import ChatOllama

        kwargs = dict(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            temperature=config.LLM_TEMPERATURE,
            num_ctx=8192,  # default 2048 is too small for schema + data
            client_kwargs={"timeout": config.LLM_TIMEOUT},
        )

        if json_mode:
            kwargs["format"] = "json"

        return ChatOllama(**kwargs)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{config.LLM_PROVIDER}'. Use 'ollama' or 'gemini'."
    )


@lru_cache(maxsize=1)
def get_llm():
    return _build(json_mode=False)


@lru_cache(maxsize=1)
def get_json_llm():
    return _build(json_mode=True)


# ----------------------------------------
# Resilient invoke
# ----------------------------------------

TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "high demand", "timed out", "Timeout",
                     "Deadline", "500 INTERNAL", "502", "504", "Connection reset")


def _invoke(llm, prompt, attempts=4):
    """Invoke with retry + backoff on temporary server errors / timeouts."""
    import time

    for i in range(attempts):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            msg = str(e)
            transient = any(m in msg for m in TRANSIENT_MARKERS)
            if not transient or i == attempts - 1:
                raise
            wait = 5 * (2 ** i)
            print(f"[llm] temporary error ({msg[:80]}...), retrying in {wait}s")
            time.sleep(wait)


# ----------------------------------------
# Response helpers
# ----------------------------------------

def response_text(response) -> str:
    """Extract plain text from a LangChain message (handles list content)."""

    content = response.content

    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )

    return str(content).strip()


def extract_json(text: str):
    """
    Parse JSON from an LLM reply.
    Tolerates markdown fences and text before/after the JSON object.
    """

    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: first {...} block
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError("No JSON object found in LLM response")


def invoke_json(prompt: str, model_cls: Type[T], retries: int = None) -> T:
    """
    Ask the JSON LLM, parse + validate with Pydantic.
    On failure, re-ask with the error message so the model can self-correct.
    """

    retries = config.MAX_JSON_RETRIES if retries is None else retries

    llm = get_json_llm()

    current_prompt = prompt
    last_error = None

    for _ in range(retries + 1):

        raw = response_text(_invoke(llm, current_prompt))

        try:
            data = extract_json(raw)
            return model_cls.model_validate(data)

        except (ValueError, ValidationError) as e:

            last_error = e

            current_prompt = (
                f"{prompt}\n\n"
                f"Your previous reply was invalid.\n"
                f"Error: {str(e)[:800]}\n"
                f"Previous reply: {raw[:800]}\n\n"
                f"Return ONLY one valid JSON object matching the schema."
            )

    raise ValueError(
        f"LLM did not return valid {model_cls.__name__} JSON: {last_error}"
    )


def invoke_text(prompt: str) -> str:
    """Plain text completion."""
    return response_text(_invoke(get_llm(), prompt))

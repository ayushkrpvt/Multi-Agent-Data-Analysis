"""
Text-to-SQL generation (used by the SQL Generation Agent).
Builds the prompt from schema context + intent + plan + data request,
including feedback from previous failed attempts.
"""

import json

from tools.config import load_prompt
from tools.llm import invoke_text
from tools.schema_tool import get_sql_context
from tools.sql_validator import clean_sql


def build_sql_prompt(question, intent, plan, data_query, previous_sql="", error=""):

    schema_context = get_sql_context(plan.get("required_tables") or intent.get("required_tables", []))

    feedback = ""
    if error:
        feedback = (
            "\nPREVIOUS ATTEMPT FAILED - FIX IT\n"
            f"Previous SQL:\n{previous_sql}\n\n"
            f"Error / feedback:\n{error}\n\n"
            "Write a corrected SQLite query. Return ONLY SQL.\n"
        )

    return f"""{load_prompt('sql_prompt')}

{schema_context}

USER QUESTION:
{question}

INTENT:
{json.dumps(intent, indent=2)}

DATA REQUEST (the dataset this query must return):
id: {data_query.get('id')}
purpose: {data_query.get('purpose', '')}
description: {data_query.get('description')}
{feedback}
SQL:"""


def generate_sql(question, intent, plan, data_query, previous_sql="", error="") -> str:
    prompt = build_sql_prompt(question, intent, plan, data_query, previous_sql, error)
    return clean_sql(invoke_text(prompt))

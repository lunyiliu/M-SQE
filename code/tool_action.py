"""Tool-domain Action scorer.

Caller contract: the selector ordering score consumed by the Tool combine is
`expected_utility - misleading_risk`, materialised from the parsed fields
below. This subtraction applies to the Tool domain only; the General combine
consumes the General Action `expected_utility` directly.
"""

from __future__ import annotations

import json
import re
from typing import Any

import tool_base_helpers as base  # noqa: E402  (alias used by the Tool scorers)

ACTION_FIELDS = [
    "task_applicability",
    "expected_utility",
    "procedure_match",
    "constraint_match",
    "output_format_match",
    "language_fit",
    "misleading_risk",
]

def json_find(text: str | None) -> dict[str, Any] | None:
    text = re.sub(r"```(?:json)?", "", (text or "").strip())
    text = re.sub(r"```", "", text)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    end = -1
    for idx in range(start, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end < 0:
        return None
    raw = re.sub(r",(\s*[}\]])", r"\1", text[start:end])
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None

def clamp_int(obj: dict[str, Any], key: str) -> int:
    try:
        value = int(obj.get(key))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{key} is not an int") from exc
    return max(0, min(100, value))

def parse_action_json(text: str | None) -> dict[str, Any]:
    obj = json_find(text)
    if not isinstance(obj, dict):
        raise ValueError("no JSON object")
    out = {field: clamp_int(obj, field) for field in ACTION_FIELDS}
    out["brief_reason"] = str(obj.get("brief_reason") or "")[:260]
    return out

def short_body(text: str | None, n: int = 6000) -> str:
    text = text or ""
    return text[:n] + ("\n...[truncated]" if len(text) > n else "")

def build_messages(rec: dict[str, Any], skill: dict[str, Any]) -> list[dict[str, str]]:
    system = "You are an action-grounded evaluator for function-calling skills. Return ONLY valid JSON."
    user = (
        "Evaluate whether the ANONYMOUS CANDIDATE SKILL is expected to help solve THIS TASK as one strict function call.\n\n"
        "Visible context:\n"
        "- user request, locale, available functions, slot schema, output contract, anonymous candidate skill body.\n\n"
        "Hidden and forbidden context:\n"
        "- gold function call, checker verdict, source type, provenance, family, strong/weak label, prior execution results.\n"
        "- Candidate retriever rank is not shown. Do not guess hidden labels.\n\n"
        "Scoring rules:\n"
        "- Relevance is not enough. Penalize skills that point to a wrong function, wrong slot, wrong locale, bad value normalization, or wrong output shape.\n"
        "- High expected_utility requires an executable procedure, correct constraints, correct output contract, locale fit, and low misleading risk.\n"
        "- The function inventory is authoritative for exact function and slot names. The skill may be noisy.\n\n"
        "Return exactly this JSON schema with integer 0-100 scores:\n"
        "{\"task_applicability\":0,\"expected_utility\":0,\"procedure_match\":0,\"constraint_match\":0,"
        "\"output_format_match\":0,\"language_fit\":0,\"misleading_risk\":0,"
        "\"brief_reason\":\"<=25 words\"}\n\n"
        f"LOCALE: {rec['locale']}\n\n"
        f"OUTPUT CONTRACT: Return exactly one JSON object: {{\"function.name\": {{\"slot\": \"value\"}}}}.\n\n"
        f"AVAILABLE FUNCTIONS AND SLOT SCHEMA:\n{base.inventory_block(rec)}\n\n"
        f"TASK:\n{rec['question']}\n\n"
        f"ANONYMOUS CANDIDATE SKILL BODY:\n{short_body(skill.get('body'))}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

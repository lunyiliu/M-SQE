from __future__ import annotations

import json
import re
from typing import Any

BODY_CHARS = 5000

ACTION_FIELDS = [
    "task_applicability",
    "procedure_match",
    "constraint_match",
    "output_format_match",
    "language_fit",
    "misleading_risk",
    "expected_utility",
]

def short(text: str | None, n: int = BODY_CHARS) -> str:
    text = text or ""
    return text[:n] + ("\n...[truncated]" if len(text) > n else "")

def title_from_body(body: str | None) -> str:
    for line in (body or "").splitlines():
        line = line.strip().strip("#").strip()
        if not line:
            continue
        line = re.sub(r"^(SKILL\.md|SKILL|COMP[ÉE]TENCE)\s*:?\s*", "", line, flags=re.I)
        return line[:160]
    return "Untitled skill"

def _int_field(obj: dict[str, Any], key: str) -> int:
    val = obj.get(key)
    if not isinstance(val, int):
        try:
            val = int(val)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{key} is not int") from exc
    return max(0, min(100, val))

def parse_action_json(text: str | None) -> dict[str, Any]:
    text = re.sub(r"```(?:json)?", "", (text or "").strip())
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object")
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
        raise ValueError("unbalanced JSON object")
    raw = re.sub(r",(\s*[}\]])", r"\1", text[start:end])
    obj = json.loads(raw)
    for key in ACTION_FIELDS:
        obj[key] = _int_field(obj, key)
    obj["brief_reason"] = str(obj.get("brief_reason") or "")[:260]
    return obj

def action_prompt(row: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You are an action-oriented evaluator for retrieved agent skills. "
        "Return ONLY a JSON object. Do not use markdown."
    )
    user = f"""Evaluate whether the CANDIDATE SKILL is expected to help an agent solve THIS TASK.

You see only the task and the candidate skill document. You are not given the source skill id, provenance, gold answer, checker, previous answer, or execution result.

Rules:
- Judge task-specific expected utility, not intrinsic writing quality.
- Relevance is not enough. Penalize related skills that can lead to a wrong API, field name, formula, step order, locale convention, output shape, or language output.
- High expected_utility requires strong applicability plus low misleading risk.
- Do not use or mention whether the skill "looks like the original skill"; you cannot know that.
- Code/API/file names may stay in English in non-English tasks. Penalize language only when prose mismatch blocks task use.

Return exactly this JSON schema:
{{"task_applicability":0-100,
  "procedure_match":0-100,
  "constraint_match":0-100,
  "output_format_match":0-100,
  "language_fit":0-100,
  "misleading_risk":0-100,
  "expected_utility":0-100,
  "brief_reason":"<=25 words"}}

TASK:
{row["task_input"]}

CANDIDATE SKILL TITLE:
{row["candidate_title"]}

CANDIDATE SKILL BODY:
{short(row.get("candidate_body"))}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

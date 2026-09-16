from __future__ import annotations

import json
import re
from typing import Any

THEORY_DIMS = [
    ("correctness", "red_line"),
    ("completeness", "basic"),
    ("executability", "basic"),
    ("cross_lingual_faithfulness", "basic"),
    ("localization", "basic"),
    ("context_efficiency", "advanced"),
]

LEVEL_CAP = {"red_line": 40, "basic": 80, "advanced": 100}

ACTION_FIELDS = [
    "task_applicability",
    "procedure_match",
    "constraint_match",
    "output_format_match",
    "language_fit",
    "misleading_risk",
    "expected_utility",
]

def parse_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    text = (text or "").strip()
    if not text:
        return None, "empty_output"
    try:
        obj = json.loads(text)
        return (obj, None) if isinstance(obj, dict) else (None, "json_not_object")
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None, "json_object_missing"
    try:
        obj = json.loads(m.group(0))
        return (obj, None) if isinstance(obj, dict) else (None, "json_not_object")
    except Exception as exc:
        return None, f"json_parse_error:{type(exc).__name__}"

def cap_overall(obj: dict) -> dict:
    """Overall Theory score = min(mean of the six dimension scores, worst-level cap)."""
    d = obj["dimensions"]
    scores = [max(0, min(100, int(d[k]["score"]))) for k, _ in THEORY_DIMS]
    redline_v = any(bool(d[k]["violated"]) for k, lvl in THEORY_DIMS if lvl == "red_line")
    basic_v = any(bool(d[k]["violated"]) for k, lvl in THEORY_DIMS if lvl == "basic")
    cap = LEVEL_CAP["red_line"] if redline_v else (LEVEL_CAP["basic"] if basic_v else LEVEL_CAP["advanced"])
    overall = round(min(sum(scores) / len(scores), cap), 1)
    return {"overall": overall, "cap": cap, "redline_violated": redline_v, "basic_violated": basic_v}

def parse_theory(text: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Parse a Theory response into dimension scores plus the capped overall."""
    obj, err = parse_json_object(str(text or ""))
    if err or not isinstance(obj, dict):
        return None, err or "json_object_missing"
    dims = obj.get("dimensions")
    if not isinstance(dims, dict):
        return None, "dimensions_missing"
    for k, _ in THEORY_DIMS:
        entry = dims.get(k)
        if not isinstance(entry, dict) or "score" not in entry or "violated" not in entry:
            return None, f"dimension_malformed:{k}"
        try:
            entry["score"] = max(0, min(100, int(entry["score"])))
        except Exception:
            return None, f"score_not_numeric:{k}"
        entry["violated"] = bool(entry["violated"])
    out = {"dimensions": {k: dims[k] for k, _ in THEORY_DIMS}}
    out.update(cap_overall(out))
    return out, None

def parse_action(text: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Parse an Action response into the overall score plus dimension scores."""
    obj, err = parse_json_object(str(text or ""))
    if err or not isinstance(obj, dict):
        return None, err or "json_object_missing"
    out: dict[str, Any] = {}
    for k in ACTION_FIELDS:
        if k not in obj:
            return None, f"field_missing:{k}"
        try:
            out[k] = max(0, min(100, int(obj[k])))
        except Exception:
            return None, f"score_not_numeric:{k}"
    if isinstance(obj.get("brief_reason"), str):
        out["brief_reason"] = obj["brief_reason"]
    return out, None

def scorer_messages(kind: str, task_prompt: str, card: dict[str, str]) -> list[dict[str, str]]:
    if kind == "theory_sqe":
        dim_lines = ", ".join(f"{k} [{lvl}]" for k, lvl in THEORY_DIMS)
        system = (
            "Score the intrinsic quality of this anonymous cultural background card for careful QA use. "
            "Prefer cards that are accurate, specific, well-scoped, actionable, and not overgeneralized. "
            f"Score each dimension from 0 to 100 and flag violations: {dim_lines}. "
            "Return exactly one JSON object: {\"dimensions\": {\"<dimension>\": {\"score\": <0-100>, \"violated\": <true|false>}, ...}} "
            "covering all six dimensions. No rationale, markdown, or extra keys."
        )
        user = {"background_card": card, "score_meaning": {"0": "misleading", "50": "partly useful", "100": "specific and reliable"}}
    else:
        system = (
            "Score how useful the anonymous background card is for answering the given public culture task. "
            "Do not infer or use any hidden answer. "
            "Return exactly this JSON schema with integer 0-100 scores: "
            "{\"task_applicability\":0,\"procedure_match\":0,\"constraint_match\":0,"
            "\"output_format_match\":0,\"language_fit\":0,\"misleading_risk\":0,"
            "\"expected_utility\":0,\"brief_reason\":\"<=25 words\"}. "
            "No markdown or extra keys."
        )
        user = {"task": task_prompt, "candidate_background_card": card, "score_meaning": {"0": "irrelevant", "50": "somewhat related", "100": "directly useful"}}
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(user, ensure_ascii=False, sort_keys=True)}]

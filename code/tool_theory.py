"""Tool-domain Theory scorer.

Caller contract: `inventory_text` is a single global constant. The same
inventory text (`tool_base_helpers.inventory_block` of one reference task
record) is used for every candidate; it is not rebuilt per task.

The parser returns the capped six-dimension mean under `overall_quality`
(the key consumed by `combine_tool.enrich_candidates`) together with the
per-dimension scores and the `language_violation` red-line flag used by the
Tool combine guard.
"""

from __future__ import annotations

from typing import Any

import tool_base_helpers as base  # noqa: E402  (alias used by the Tool scorers)

THEORY_DIMS = [
    ("correctness", "red_line",
     "The stated function, slot names, and calling convention are right for the skill's target function; wrong or misleading statements violate this."),
    ("completeness", "basic",
     "Covers the slots and boundary values the function call needs (slot-aware)."),
    ("executability", "basic",
     "Schema and steps are concrete enough for an agent to build the call (clear)."),
    ("cross_lingual_faithfulness", "basic",
     "No meaning-altering translation artifacts or untranslated fragments that impede use."),
    ("localization", "basic",
     "Prose genuinely written for the skill's own locale (locale-appropriate)."),
    ("context_efficiency", "advanced",
     "Concise; padding that dilutes the agent's attention counts against it."),
]

LEVEL_CAP = {"red_line": 40, "basic": 80, "advanced": 100}

def clamp_int(obj: dict[str, Any], key: str) -> int:
    try:
        value = int(obj.get(key))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{key} is not an int") from exc
    return max(0, min(100, value))

def theory_messages(skill: dict[str, Any], inventory_text: str) -> list[dict[str, str]]:
    system = "You are an intrinsic quality evaluator for multilingual function-calling skills. Return ONLY valid JSON."
    dim_lines = "\n".join(f"- {k} [{lvl}]: {crit}" for k, lvl, crit in THEORY_DIMS)
    user = (
        "Evaluate the intrinsic quality of the CANDIDATE SKILL for function-calling. "
        "You do not see a user task, gold label, checker output, provenance label, source type, hidden anchor flag, or skill family.\n\n"
        "Judge whether the skill is clear, executable, slot-aware, locale-appropriate, and unlikely to mislead a downstream solver. "
        "The function inventory is authoritative for exact function/slot names.\n\n"
        "Score each dimension from 0 to 100 and flag violations:\n"
        f"{dim_lines}\n\n"
        "Return exactly this JSON schema:\n"
        "{\"dimensions\":{\"correctness\":{\"score\":0,\"violated\":false},"
        "\"completeness\":{\"score\":0,\"violated\":false},"
        "\"executability\":{\"score\":0,\"violated\":false},"
        "\"cross_lingual_faithfulness\":{\"score\":0,\"violated\":false},"
        "\"localization\":{\"score\":0,\"violated\":false},"
        "\"context_efficiency\":{\"score\":0,\"violated\":false}},"
        "\"language_violation\":false,\"brief_reason\":\"<=25 words\"}\n\n"
        f"AVAILABLE FUNCTIONS AND SLOT SCHEMA:\n{inventory_text}\n\n"
        f"CANDIDATE SKILL LOCALE: {skill.get('locale')}\n\n"
        f"CANDIDATE SKILL BODY:\n{(skill.get('body') or '')[:6000]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

def parse_theory_json(text: str) -> dict[str, Any]:
    obj = base.json_find(text)
    if not isinstance(obj, dict):
        raise ValueError("no_json_object")
    dims = obj.get("dimensions")
    if not isinstance(dims, dict):
        raise ValueError("dimensions_missing")
    parsed: dict[str, dict[str, Any]] = {}
    for k, _, _ in THEORY_DIMS:
        entry = dims.get(k)
        if not isinstance(entry, dict):
            raise ValueError(f"dimension_missing:{k}")
        parsed[k] = {"score": clamp_int(entry, "score"), "violated": bool(entry.get("violated"))}
    scores = [parsed[k]["score"] for k, _, _ in THEORY_DIMS]
    redline_v = any(parsed[k]["violated"] for k, lvl, _ in THEORY_DIMS if lvl == "red_line")
    basic_v = any(parsed[k]["violated"] for k, lvl, _ in THEORY_DIMS if lvl == "basic")
    cap = LEVEL_CAP["red_line"] if redline_v else (LEVEL_CAP["basic"] if basic_v else LEVEL_CAP["advanced"])
    out: dict[str, Any] = {"dimensions": parsed}
    out["overall_quality"] = round(min(sum(scores) / len(scores), cap), 1)
    out["cap"] = cap
    out["redline_violated"] = redline_v
    out["basic_violated"] = basic_v
    out["language_violation"] = (
        bool(obj.get("language_violation"))
        or parsed["cross_lingual_faithfulness"]["violated"]
        or parsed["localization"]["violated"]
    )
    out["brief_reason"] = str(obj.get("brief_reason") or "")[:260]
    return out

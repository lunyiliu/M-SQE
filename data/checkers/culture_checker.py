from __future__ import annotations

import json
import re
from typing import Any


def tokens(text: Any) -> list[str]:
    normalized = str(text or "").replace("_", " ").replace("-", " ")
    return re.findall(r"[\w]+", normalized.lower(), flags=re.UNICODE)


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


def norm(text: Any) -> str:
    return " ".join(tokens(text))


def term_match(term: str, answer_norm: str) -> bool:
    t = norm(term)
    if not t:
        return False
    return t in answer_norm


def score_answer(task: dict[str, Any], parsed: dict[str, Any] | None, parse_error: str | None) -> dict[str, Any]:
    if parse_error or not isinstance(parsed, dict) or "answer" not in parsed:
        return {"strict_score": "invalid", "lenient_pass": False, "answer_raw": None, "normalized_answer": "", "matched_terms": [], "errors": [parse_error or "answer_key_missing"]}
    raw = parsed.get("answer")
    answer = norm(raw)
    answer_key = task["answer_key"]
    rejects = [norm(x) for x in answer_key.get("reject_examples") or []]
    if any(r and (r in answer or answer in r) for r in rejects):
        return {"strict_score": "fail", "lenient_pass": False, "answer_raw": raw, "normalized_answer": answer, "matched_terms": [], "errors": ["reject_example_match"]}
    aliases = [answer_key.get("canonical")] + list(answer_key.get("accept_examples") or [])
    alias_match = any((na := norm(alias)) and (na in answer or answer in na) for alias in aliases)
    terms = (answer_key.get("scorer_rule") or {}).get("required_any_terms") or []
    matched = [term for term in terms if term_match(term, answer)]
    min_hits = 1 if len(terms) <= 2 else min(2, len(terms))
    strict_pass = alias_match or len(matched) >= min_hits
    lenient_pass = alias_match or bool(matched)
    return {
        "strict_score": "pass" if strict_pass else "fail",
        "lenient_pass": bool(lenient_pass),
        "answer_raw": raw,
        "normalized_answer": answer,
        "matched_terms": matched,
        "errors": [] if strict_pass else ["required_terms_or_alias_not_matched"],
    }

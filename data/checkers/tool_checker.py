from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any


EMPTY_MARKERS = {"", "empty", "null", "none"}
NOW_MARKERS = {"now", "current", "currently", "right now"}

@dataclass
class CheckResult:
    ok: bool
    reason: str
    pred_name: str | None = None
    gold_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "pred_name": self.pred_name,
            "gold_name": self.gold_name,
        }


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" \t\r\n\"'`.,;:，。！？!?")
    return text.lower()


def parse_prediction(text_or_obj: Any) -> dict:
    if isinstance(text_or_obj, dict):
        return text_or_obj
    text = str(text_or_obj or "").strip()
    if text.startswith("```") or "```" in text:
        raise ValueError("markdown_fence")
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
    if text[:start].strip() or text[end:].strip():
        raise ValueError("extra_text")
    raw = re.sub(r",(\s*[}\]])", r"\1", text[start:end])
    return json.loads(raw)


def one_call(obj: Any) -> tuple[str | None, dict]:
    if not isinstance(obj, dict) or len(obj) != 1:
        return None, {}
    name = next(iter(obj.keys()))
    args = obj.get(name) or {}
    if not isinstance(args, dict):
        return str(name), {}
    return str(name), args


def is_empty_like(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return all(is_empty_like(v) for v in value)
    return normalize_text(value) in EMPTY_MARKERS


def accepted_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_text(v) for v in value]
    return [normalize_text(value)]


def value_matches(pred: Any, gold_values: Any, *, allow_now_omission: bool = False) -> bool:
    if pred == gold_values:
        return True
    gold_norm = accepted_values(gold_values)
    if isinstance(pred, list):
        pred_norm = [normalize_text(v) for v in pred]
        return set(pred_norm) == set(gold_norm)
    pred_norm = normalize_text(pred)
    if pred_norm in gold_norm:
        return True
    if pred_norm == "" and any(v in EMPTY_MARKERS for v in gold_norm):
        return True
    if allow_now_omission and pred_norm == "" and any(v in NOW_MARKERS for v in gold_norm):
        return True
    return False


def schema_allows_now_default(function_schema: dict | None) -> bool:
    if not function_schema:
        return False
    text = " ".join(
        [
            str(function_schema.get("name", "")),
            str(function_schema.get("description", "")),
        ]
    ).lower()
    return any(term in text for term in ["current", "now", "immediate", "currently"])


def check_call(prediction: Any, gold: dict, *, function_schema: dict | None = None) -> CheckResult:
    try:
        pred_obj = parse_prediction(prediction)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(False, f"parse_error:{type(exc).__name__}", None, None)

    pred_name, pred_args = one_call(pred_obj)
    gold_name, gold_args = one_call(gold)
    if not pred_name or not gold_name:
        return CheckResult(False, "not_single_function_call", pred_name, gold_name)
    if pred_name != gold_name:
        return CheckResult(False, "function_mismatch", pred_name, gold_name)

    allow_now = schema_allows_now_default(function_schema)
    for key, accepted in gold_args.items():
        if key not in pred_args:
            if is_empty_like(accepted):
                continue
            if allow_now and any(v in NOW_MARKERS for v in accepted_values(accepted)):
                continue
            return CheckResult(False, f"missing_slot:{key}", pred_name, gold_name)
        if not value_matches(pred_args.get(key), accepted, allow_now_omission=allow_now):
            return CheckResult(False, f"value_mismatch:{key}", pred_name, gold_name)

    extra = set(pred_args) - set(gold_args)
    extra_non_empty = {key for key in extra if not is_empty_like(pred_args.get(key))}
    if extra_non_empty:
        return CheckResult(False, f"extra_slots:{','.join(sorted(extra_non_empty))}", pred_name, gold_name)
    return CheckResult(True, "ok", pred_name, gold_name)

"""General-domain Theory scorer.

Caller contract: dimensions come from `active_dims("theory_full_fixed")`,
`build_prompt` is called with `anchor=True`, and the prompt is sent as a
single `user` message with no `system` role.
"""

from __future__ import annotations

import json
import re

DIMS = [
    ("correctness",   "Correctness",       "red_line", False, "Procedural facts/logic are correct (no factual or logical errors). Missing external files/tools is NOT a correctness issue — that is Executability."),
    ("executability", "Executability",     "basic",    False, "Steps are concrete and executable by an agent; needed tools/files are defined or obtainable."),
    ("completeness",  "Completeness",      "basic",    False, "Covers the necessary steps and boundary cases for this task class; no critical omission."),
    ("faithfulness",  "Faithfulness(ML)",  "basic",    True,  "TRANSLATION fidelity: no meaning-altering mistranslation AND no untranslated foreign-language fragments that impede use. A natively-authored skill is faithful by default unless there is clear distortion."),
    ("localization",  "Localization(ML)",  "basic",    True,  "Conventions/examples fit the skill's OWN language locale (dates, numbers, names, formats); an English skill in English is correctly localized. Penalize wrong-locale conventions or awkward literal translation."),
    ("context_eff",   "Context-efficiency","advanced", False, "Concise, not bloated. An excessively long/padded skill wastes the agent's context budget, dilutes attention, and can itself cause execution failure."),
]

LEVEL_CAP = {"red_line": 40, "basic": 80, "advanced": 100}

LANG_NAME = {"en": "English", "fr": "French", "hi": "Hindi", "ja": "Japanese",
             "ko": "Korean", "sw": "Swahili", "zh": "Chinese"}

FIXED_DIMS = [
    DIMS[0], DIMS[1], DIMS[2],
    ("faithfulness", "Faithfulness(ML)", "basic", True,
     "For translated/multilingual skills, the skill must preserve meaning and contain no untranslated or "
     "wrong-language prose that impedes use in the EXPECTED target language. If no source is available, "
     "judge target-language compliance and obvious translation artifacts rather than inventing a source."),
    ("localization", "Localization(ML)", "basic", True,
     "The skill must be usable as a skill for the EXPECTED target language. Penalize wrong target language, "
     "mixed-language prose that burdens target-language users, awkward literal translation, and wrong locale "
     "conventions. For non-Latin target languages, substantial English PROSE is a major localization failure "
     "(code blocks, package/API names, paths, commands, variable names are exempt)."),
    DIMS[5],
]

def active_dims(variant: str):
    if variant == "theory_full_fixed":
        return FIXED_DIMS
    return [d for d in DIMS if not (variant == "no_ml" and d[3])]

def build_prompt(body: str, lang: str, dims, anchor: bool = False) -> str:
    lines = [f"- {k} [{lvl}]: {crit}" for k, _, lvl, _, crit in dims]
    if anchor:  # lang is the EXPECTED target language, not a description of the prose
        lang_block = (
            "The record's lang field is the EXPECTED target language, not merely metadata.\n"
            f"Expected target language: {LANG_NAME.get(lang, lang)} ({lang}).\n"
            "Judge whether the PROSE of the skill is written for this expected target language.\n"
            "Ignore code blocks, package names, API names, file paths, commands, and variable names when "
            "judging prose language — keeping those in English is normal and must NOT be penalized.\n"
            "If substantial prose is in English while the expected target language is non-English "
            "(e.g. Hindi/Japanese/Chinese/Korean), that is a localization failure even if the English is fluent.\n"
            'Do NOT treat "English skill in English" as localized unless the expected target language is English.\n\n'
        )
    else:
        lang_block = (
            f"The skill is written in language code '{lang}'. Evaluate it in that language on its own terms; "
            f"the ML dimensions (Faithfulness/Localization) assess TRANSLATION quality only — "
            f"a skill that reads as natural, native '{lang}' scores HIGH on them and is not 'violated'.\n\n"
        )
    return (
        "You are an expert evaluator of AGENT SKILLS (procedural documents an agent retrieves, loads "
        "into context, and follows to perform a class of tasks). Judge the skill's intrinsic QUALITY.\n"
        "Do NOT judge relevance to any query, and do NOT reward verbosity. Score EACH dimension "
        "INDEPENDENTLY — a flaw in one dimension must not lower another (e.g. a wrong step must not "
        "lower the Localization score). You are blind to who authored or translated the skill.\n\n"
        + lang_block +
        "Dimensions (each scored 0-100; 'violated'=true means it fails this dimension's bar):\n"
        + "\n".join(lines) +
        "\n\nEvery 'score' MUST be an integer 0-100 (never -1, null, or N/A; if unsure, give your best estimate). "
        "'confidence' likewise 0-100.\n"
        "Return ONLY a JSON object, no prose, no markdown fence:\n"
        '{"dimensions":{'
        + ",".join(f'"{k}":{{"score":<0-100 int>,"violated":<true|false>,"reason":"<=12 words"}}' for k, *_ in dims)
        + '},"root_cause_tags":["<short tags for the main quality problems, [] if none>"],'
        '"confidence":<0-100 int, your confidence in this assessment>}\n\n'
        "SKILL:\n" + body
    )

def parse_scores(text: str, dims) -> dict:
    # robust extraction: strip markdown fences, take the outermost balanced {...}, drop trailing commas
    t = re.sub(r"```(?:json)?", "", text.strip())
    start = t.find("{")
    if start < 0:
        raise ValueError("no JSON object in scorer output")
    depth, end = 0, -1
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise ValueError("unbalanced JSON object")
    s = re.sub(r",(\s*[}\]])", r"\1", t[start:end])  # trailing commas
    obj = json.loads(s)
    d = obj.get("dimensions") or {}
    for k, *_ in dims:
        if k not in d or "score" not in d[k] or "violated" not in d[k]:
            raise ValueError(f"missing/incomplete dimension {k}")
    return obj

def cap_overall(obj: dict, dims) -> dict:
    """Deterministic CoachLM-style cap: overall = min(mean(dim scores), worst-level cap)."""
    d = obj["dimensions"]
    scores = [max(0, min(100, int(d[k]["score"]))) for k, *_ in dims]
    redline_v = any(d[k]["violated"] for k, _, lvl, *_ in dims if lvl == "red_line")
    basic_v = any(d[k]["violated"] for k, _, lvl, *_ in dims if lvl == "basic")
    cap = LEVEL_CAP["red_line"] if redline_v else (LEVEL_CAP["basic"] if basic_v else LEVEL_CAP["advanced"])
    overall = round(min(sum(scores) / len(scores), cap), 1)
    return {"overall": overall, "cap": cap, "redline_violated": redline_v, "basic_violated": basic_v}

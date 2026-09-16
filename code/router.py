from __future__ import annotations

import json
import re

MODEL = "gemini-3-flash-preview"

VALID_TAU = {"general", "function", "culture"}

BASE_SYSTEM_PROMPT = """You are a lightweight task-type classifier for an agent system.
Classify the user's query into exactly one of these task types:

- general: A stand-alone knowledge, reasoning, coding, document/data manipulation, or procedural task. The agent should answer or solve the task itself.
- function: An intent/function-call task where the agent should select or invoke an API, tool, app action, or service function and fill its arguments. These are often short requests about email, calendar, devices, media, transport, alarms, and similar actions.
- culture: A task whose answer centrally depends on culture-specific customs, values, etiquette, social norms, history, or regional practices.

Tie rules: choose culture when culture-specific knowledge is essential. Choose function only for an app/tool/service action or intent invocation; an ordinary programming or coding question that mentions a function is general. Otherwise choose general.

Return exactly one JSON object and nothing else: {"tau":"general|function|culture"}."""

FEWSHOT_EXAMPLES = (
    ("A presentation object is stored in prs. Write the exact one-line Python expression that returns the text of shape 2 on slide 3, with no assignment or print.", "general"),
    ("给定 JSON 数组 [{\"x\":2},{\"x\":5}]，按题目定义的转换规则输出只含平方值的 JSON 数组。", "general"),
    ("次の Python 関数を input=[3,1,3] で実行したときの戻り値を、説明なしの JSON 配列で答えてください。", "general"),
    ("एक वीडियो में 22 फ्रेम हैं और interval=5 है। दिए गए extraction नियम के अनुसार अंतिम सेव फ़ाइल का सटीक पाथ लिखें।", "general"),
    ("Ukipewa jedwali lenye safu mbili, tumia kanuni iliyoelezwa kukokotoa thamani ya mwisho na urudishe nambari pekee.", "general"),
    ("send an email to Ana about tomorrow's meeting", "function"),
    ("पारसेक शब्द का अर्थ क्या है", "function"),
    ("面白いジョークを一つ教えて", "function"),
    ("saa ngapi sasa huko Nairobi", "function"),
    ("和我玩一局国际象棋", "function"),
    ("A Swedish office guide needs one principle for everyday workplace interaction. What should it emphasize?", "culture"),
    ("An Indian community handbook is describing how families preserve traditions abroad. Which institutions or activities matter?", "culture"),
    ("A Japanese etiquette note is explaining the meaning of a small informal bow. What does it communicate?", "culture"),
    ("A Mexican heritage guide is summarizing a family remembrance festival. Which practice should it mention?", "culture"),
    ("A Kenyan visitor guide asks about locally appropriate greeting norms. What should it advise?", "culture"),
)

def parse_tau(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    obj = json.loads(cleaned)
    if set(obj) != {"tau"} or obj["tau"] not in VALID_TAU:
        raise ValueError(f"Invalid classification object: {obj!r}")
    return obj["tau"]

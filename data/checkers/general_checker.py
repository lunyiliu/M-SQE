from __future__ import annotations

import re
from typing import Any


def _norm(text: str | None) -> str:
    text = (text or "").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().strip('"').strip("'").strip()


def evaluate_deterministic(task: dict[str, Any], answer: str) -> tuple[bool, str | None]:
    golds = task.get("golds") or []
    norm_golds = {_norm(g) for g in golds}
    candidates = [answer] + (answer or "").splitlines()
    for candidate in candidates:
        if _norm(candidate) in norm_golds:
            return True, candidate
    return False, None

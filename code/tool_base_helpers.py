from __future__ import annotations

import json
import re
from typing import Any

def json_find(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None

def inventory_block(row: dict[str, Any]) -> str:
    lines = []
    for func in row.get("function_inventory") or []:
        lines.append(f"- `{func.get('name')}`: {func.get('description')}")
        params = (func.get("parameters") or {}).get("properties") or {}
        required = set((func.get("parameters") or {}).get("required") or [])
        if params:
            slots = []
            for key, meta in params.items():
                req = "required" if key in required else "optional"
                slots.append(f"{key} ({req}): {meta.get('description', '')}")
            lines.append(f"  Slots: {'; '.join(slots)}")
    return "\n".join(lines)

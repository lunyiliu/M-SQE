"""General-domain combine.

The single combine rule used for the General domain,
`combine_scalar_0.6A_0.4T`: 0.6 * Action expected utility + 0.4 * Theory
overall score, descending, with the retrieval rank and the candidate id as
tie-breaks. The General Action scorer's `expected_utility` is consumed
directly (no risk subtraction).
"""

from __future__ import annotations

from typing import Any

def scalar_order(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in cands:
        row["combine_scalar_0.6A_0.4T_score"] = 0.6 * float(row["expected_utility"]) + 0.4 * float(row["theory_overall"])
    return sorted(
        cands,
        key=lambda row: (
            -row["combine_scalar_0.6A_0.4T_score"],
            row["raw_rank"],
            row["candidate_skill_id"],
        ),
    )

"""Culture-domain combine.

The single combine rule used for the Culture domain,
`combine_guideline_equal_z`: candidates are ranked by the equally weighted sum
of the z-scores of the retrieval score, the Theory score and the Action score
(the Culture scorer emits one scalar per view, so `expected_utility` carries
the Action score and the risk term is identically zero and therefore omitted).
Population standard deviation is used; ties fall back to Action score,
retrieval score, the fixed retrieval rank and finally the candidate id.
"""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

def zscore(values: list[float], value: float) -> float:
    sigma = pstdev(values)
    return 0.0 if math.isclose(sigma, 0.0) else (value - mean(values)) / sigma

def equal_z_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    retrieval_values = [row["stage3_deep_score"] for row in rows]
    theory_values = [row["theory_overall"] for row in rows]
    utility_values = [row["expected_utility"] for row in rows]

    def guideline_score(row: dict[str, Any]) -> float:
        return (
            zscore(retrieval_values, row["stage3_deep_score"])
            + zscore(theory_values, row["theory_overall"])
            + zscore(utility_values, row["expected_utility"])
        )

    return sorted(
        rows,
        key=lambda row: (
            -guideline_score(row),
            -row["action_score"],
            -row["stage3_deep_score"],
            row["fixed_rank"],
            row["skill_id"],
        ),
    )

"""Tool-domain combine.

Candidate enrichment plus the single combine rule used for the Tool domain:
`combine_strict_guarded65` — candidates are ordered by Action score, then
partitioned into a passing block (`theory_overall >= 65` and no language
red-line violation) and a back-fill block that preserves the same Action order.

Selector-score convention: the Tool ordering key is the materialised
`action_selector_score` (expected_utility - misleading_risk, see
`tool_action`), with `expected_utility` as the first tie-break.
"""

from __future__ import annotations

from typing import Any

def enrich_candidates(
    cands: list[dict[str, Any]],
    uid: str,
    retriever: str,
    a_scores: dict[tuple[str, str, str], dict[str, Any]],
    t_scores: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach Theory/Action scores to retrieved candidates.

    A missing Action score falls back to -999.0 (utility/selector) and 999.0
    (risk); a missing Theory score falls back to overall_quality 50.0.
    """
    out = []
    for cand in cands:
        sid = cand["skill_id"]
        action = a_scores.get((uid, retriever, sid), {})
        theory = t_scores.get(sid, {})
        rec = dict(cand)
        rec["candidate_skill_id"] = sid
        rec["raw_rank"] = int(cand["rank"])
        rec["retrieval_score"] = float(cand.get("score") or 0.0)
        rec["expected_utility"] = float(action.get("expected_utility") if action.get("expected_utility") is not None else -999.0)
        rec["misleading_risk"] = float(action.get("misleading_risk") if action.get("misleading_risk") is not None else 999.0)
        rec["action_score"] = float(action.get("action_selector_score") if action.get("action_selector_score") is not None else -999.0)
        rec["theory_overall"] = float(theory.get("overall_quality") if theory.get("overall_quality") is not None else 50.0)
        rec["theory_score"] = float(theory.get("theory_selector_score") if theory.get("theory_selector_score") is not None else 0.0)
        rec["language_violation"] = bool(theory.get("language_violation"))
        out.append(rec)
    return out

def strict_guarded_order(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`combine_strict_guarded65`: Action order, with `theory_overall >= 65`
    and no language violation promoted to the front and the remainder appended
    in the same Action order."""
    action = sorted(cands, key=lambda r: (-r["action_score"], -r["expected_utility"], r["raw_rank"], r["candidate_skill_id"]))
    passed = [r for r in action if r["theory_overall"] >= 65 and not r["language_violation"]]
    return passed + [r for r in action if r not in passed]

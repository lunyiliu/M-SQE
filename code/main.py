"""Reference runner: query -> router -> Theory/Action scoring -> combine -> final scores.

Wires the released components end to end for one query and a small set of
candidate skills, and prints the ranked final scores for the routed domain.

Environment:
  MSQE_API_BASE   OpenAI-compatible endpoint base, e.g. https://api.example.com/v1
  MSQE_API_KEY    Bearer token for that endpoint
  MSQE_MODEL      Optional model override (defaults to each scorer's request spec)

Usage:
  python3 main.py ../examples/general_example.json
  python3 main.py ../examples/tool_example.json
  python3 main.py ../examples/culture_example.json --domain function   # skip routing

Example input format (see ../examples/*.json):
  {
    "query": "...",
    "function_inventory": [...],            # tool domain only
    "candidates": [
      {"skill_id": "...", "body": "...", "locale": "...", "retrieval_score": 12.3},
      ...
    ]
  }
`retrieval_score` is the caller's retriever score for the candidate; it enters
the Cultural fusion as its Retrieval term.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

import combine_culture as cc
import combine_general as cg
import combine_tool as ct
import culture_scorer as cs
import general_action as ga
import general_theory as gt
import router
import tool_action as ta
import tool_base_helpers as base
import tool_theory as tt

HERE = os.path.dirname(os.path.abspath(__file__))
SPECS = json.load(open(os.path.join(HERE, "scorer_request_specs.json")))["scorers"]
ROUTER_FREEZE = json.load(open(os.path.join(HERE, "tau_router_5shot_freeze.json")))

def call_llm(messages: list[dict[str, str]], request: dict) -> str:
    api_base = os.environ.get("MSQE_API_BASE", "").rstrip("/")
    api_key = os.environ.get("MSQE_API_KEY", "")
    if not api_base or not api_key:
        sys.exit("Set MSQE_API_BASE and MSQE_API_KEY to an OpenAI-compatible endpoint.")
    payload = {
        "model": os.environ.get("MSQE_MODEL") or request.get("model") or router.MODEL,
        "messages": messages,
        "temperature": request.get("temperature", 0),
        "max_tokens": request.get("max_tokens", 1024),
    }
    if "thinking_level" in request:
        payload["thinking_level"] = request["thinking_level"]
    if request.get("extra_body"):
        payload["extra_body"] = request["extra_body"]
    req = urllib.request.Request(
        f"{api_base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as exc:
            if attempt == 2 or exc.code not in (429, 500, 502, 503):
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")

def route(query: str) -> str:
    messages = [{"role": "system", "content": router.BASE_SYSTEM_PROMPT}]
    for example_query, tau in router.FEWSHOT_EXAMPLES:
        messages.append({"role": "user", "content": example_query})
        messages.append({"role": "assistant", "content": json.dumps({"tau": tau})})
    messages.append({"role": "user", "content": query})
    return router.parse_tau(call_llm(messages, ROUTER_FREEZE["request"]))

def score_general(query: str, cands: list[dict]) -> list[dict]:
    dims = gt.active_dims("theory_full_fixed")
    rows = []
    for i, cand in enumerate(cands, 1):
        theory_prompt = gt.build_prompt(cand["body"], cand.get("locale", "en"), dims, anchor=True)
        theory_obj = gt.parse_scores(call_llm([{"role": "user", "content": theory_prompt}], SPECS["general_theory"]["request"]), dims)
        theory = gt.cap_overall(theory_obj, dims)
        action_row = {"task_input": query, "candidate_title": ga.title_from_body(cand["body"]), "candidate_body": cand["body"]}
        action = ga.parse_action_json(call_llm(ga.action_prompt(action_row), SPECS["general_action"]["request"]))
        rows.append({
            "candidate_skill_id": cand["skill_id"], "raw_rank": i,
            "theory_overall": theory["overall"], "expected_utility": action["expected_utility"],
        })
    ranked = cg.scalar_order(rows)
    return [{**r, "final_score": r["combine_scalar_0.6A_0.4T_score"]} for r in ranked]

def score_tool(query: str, cands: list[dict], inventory: list[dict]) -> list[dict]:
    inventory_text = base.inventory_block({"function_inventory": inventory})
    rec = {"locale": cands[0].get("locale", "en-US"), "question": query, "function_inventory": inventory}
    rows = []
    for i, cand in enumerate(cands, 1):
        theory = tt.parse_theory_json(call_llm(tt.theory_messages(cand, inventory_text), SPECS["tool_theory"]["request"]))
        action = ta.parse_action_json(call_llm(ta.build_messages(rec, cand), SPECS["tool_action"]["request"]))
        rows.append({
            "candidate_skill_id": cand["skill_id"], "raw_rank": i,
            "theory_overall": theory["overall_quality"], "language_violation": theory["language_violation"],
            "expected_utility": action["expected_utility"],
            "action_score": action["expected_utility"] - action["misleading_risk"],
        })
    ranked = ct.strict_guarded_order(rows)
    return [{**r, "final_score": r["action_score"],
             "guard_passed": r["theory_overall"] >= 65 and not r["language_violation"]} for r in ranked]

def score_culture(query: str, cands: list[dict]) -> list[dict]:
    rows = []
    for i, cand in enumerate(cands, 1):
        card = {"name": cand["skill_id"], "content": cand["body"]}
        theory, terr = cs.parse_theory(call_llm(cs.scorer_messages("theory_sqe", "", card), SPECS["culture_theory"]["request"]))
        action, aerr = cs.parse_action(call_llm(cs.scorer_messages("action_sqe", query, card), SPECS["culture_action"]["request"]))
        if terr or aerr:
            sys.exit(f"culture scorer parse failed for {cand['skill_id']}: {terr or aerr}")
        rows.append({
            "skill_id": cand["skill_id"], "fixed_rank": i,
            "stage3_deep_score": float(cand.get("retrieval_score", 0.0)),
            "theory_overall": theory["overall"],
            "expected_utility": action["expected_utility"], "action_score": action["expected_utility"],
        })
    ranked = cc.equal_z_order(rows)
    retrieval = [r["stage3_deep_score"] for r in ranked]
    theory_v = [r["theory_overall"] for r in ranked]
    utility = [r["expected_utility"] for r in ranked]
    for r in ranked:
        r["final_score"] = round(
            cc.zscore(retrieval, r["stage3_deep_score"]) + cc.zscore(theory_v, r["theory_overall"]) + cc.zscore(utility, r["expected_utility"]), 4)
        r["candidate_skill_id"] = r["skill_id"]
    return ranked

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("example", help="path to an example JSON (query + candidates)")
    ap.add_argument("--domain", choices=sorted(router.VALID_TAU), help="skip routing and force a domain")
    args = ap.parse_args()

    ex = json.load(open(args.example))
    query, cands = ex["query"], ex["candidates"]
    tau = args.domain or route(query)
    print(f"query: {query[:100]}{'...' if len(query) > 100 else ''}")
    print(f"routed domain: {tau}")

    if tau == "function":
        ranked = score_tool(query, cands, ex.get("function_inventory") or [])
    elif tau == "culture":
        ranked = score_culture(query, cands)
    else:
        ranked = score_general(query, cands)

    print(f"\n{'rank':<5}{'final':>9}  {'theory':>7}  {'action':>7}  skill_id")
    for rank, r in enumerate(ranked, 1):
        act = r.get("expected_utility", "")
        extra = "" if r.get("guard_passed") in (None, True) else "  [guard: failed]"
        print(f"{rank:<5}{r['final_score']:>9}  {r['theory_overall']:>7}  {act:>7}  {r['candidate_skill_id']}{extra}")

if __name__ == "__main__":
    main()

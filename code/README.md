# M-SQE — Code

This directory contains the scoring components behind the paper's
query -> router -> Theory/Action scoring -> three-domain combine -> final
candidate score chain, exposed as a component library: the router contract,
the scorer prompt builders and response parsers, and the combine rule of each
domain.

## Method summary

A query is first classified by a lightweight 5-shot **task-type router** into
one of three types (`general`, `function`, `culture`), which selects the
domain-specific scorers and combine rule.

Each retrieved candidate skill is then scored from **two views**:

- **Theory** — intrinsic quality of the skill document, judged without the
  task. General Theory is scored on six dimensions with a level cap
  (red-line / basic / advanced); Tool and Culture Theory are scored on the
  same six dimensions with the same level cap, and Tool Theory additionally
  reports a language red-line flag consumed by the Tool combine guard.
- **Action** — task-specific expected utility of the candidate for the query
  at hand, together with a misleading-risk term.

The two views are then merged by the **combine rule of the domain**:

| Domain | Combine rule | Definition |
|---|---|---|
| General | `combine_scalar_0.6A_0.4T` | `0.6 * expected_utility + 0.4 * theory_overall`, descending |
| Tool | `combine_strict_guarded65` | Action order, with `theory_overall >= 65` and no language violation promoted to the front and the remainder appended in the same Action order |
| Culture | `combine_guideline_equal_z` | `z(retrieval) + z(theory) + z(action)` with population standard deviation, descending |

The evaluation domains are General (skills of the *ecological-style*, MT and
self-generated production layers), Tool (function calling over a 55-function
inventory) and Culture (short-answer tasks over six culture regions).

## Quick start

`main.py` is a reference runner that wires the released components end to
end for one query and a small set of candidate skills: query -> router ->
Theory/Action scoring -> combine -> a printed, ranked score table. It needs
Python 3.9+ and only the standard library.

Point it at an OpenAI-compatible chat-completions endpoint:

```bash
export MSQE_API_BASE=https://api.example.com/v1   # OpenAI-compatible endpoint
export MSQE_API_KEY=sk-...                         # bearer token for that endpoint
export MSQE_MODEL=...                              # optional: overrides each scorer's request-spec model
```

Then run it against one of the bundled examples:

```bash
python3 main.py ../examples/general_example.json
python3 main.py ../examples/tool_example.json
python3 main.py ../examples/culture_example.json
python3 main.py ../examples/general_example.json --domain general   # skip routing, force a domain
```

Each run prints the routed domain and a ranked table of `final` / `theory` /
`action` scores per candidate `skill_id`, for example:

```
query: Excelの「売上データ」シートの...
routed domain: general

rank     final   theory   action  skill_id
1         57.0     97.5       30  general_pool:145
2         39.7     99.2        0  general_pool:168
3         39.3     98.3        0  general_pool:154
```

(Exact scores depend on the model behind the endpoint; the table shape and
column meaning stay fixed.)

### Examples

`../examples/*_example.json` each hold one query and three candidate skills,
one file per domain, following the input format documented at the top of
`main.py` (`query`, `candidates` with `skill_id`/`body`/`locale`/optional
`retrieval_score`, and `function_inventory` for the Tool domain):

- `general_example.json` — a Japanese Excel/XLOOKUP question against three
  Hindi-language candidate skills.
- `tool_example.json` — a function-calling query against three candidate
  skills plus the 55-entry `function_inventory` the Tool scorers evaluate
  against.
- `culture_example.json` — a workplace-etiquette question against three
  candidate culture cards.

## What is included

Included:

- **Router**: the 5-shot task-type router contract
  (`tau_router_5shot_freeze.json`), its constants (`MODEL`, `VALID_TAU`,
  `BASE_SYSTEM_PROMPT`, `FEWSHOT_EXAMPLES`) and the response parser
  `parse_tau`.
- **Theory/Action scorers** (three domains): the prompt builders and response
  parsers. General theory, General action, Tool theory, Tool action, Culture
  scorer.
- **Request parameter specification**: `scorer_request_specs.json` lists the
  request parameters used by each scorer (model, temperature, token budget,
  provider options), in the same form as the `request` section of the router
  contract.
- **Combine** (three domains): General `scalar_order`, Tool
  `strict_guarded_order` / `enrich_candidates`, Culture `equal_z_order`.
- **Shared helpers** (`tool_base_helpers`): `json_find`, `inventory_block`,
  kept under the `base` import alias used by the Tool scorers.

To execute the router and scorers, supply an OpenAI-compatible client and
issue requests as specified by `tau_router_5shot_freeze.json` (router) and
`scorer_request_specs.json` (scorers).

## Module reference (input contracts)

| Module | Functions | Required input fields |
|---|---|---|
| `router.py` | `parse_tau(text)`; constants + `tau_router_5shot_freeze.json` | router response text `{"tau": ...}` |
| `general_theory.py` | `active_dims`, `build_prompt(body,lang,dims,anchor)`, `parse_scores(text,dims)`, `cap_overall(obj,dims)` | skill `body`, `lang`; dims from `DIMS`/`FIXED_DIMS` |
| `general_action.py` | `action_prompt(row)`, `title_from_body(body)`, `parse_action_json(text)` | row: `task_input`, `candidate_title`, `candidate_body` |
| `tool_theory.py` | `theory_messages(skill,inventory_text)`, `parse_theory_json(text)`, `clamp_int` | skill: `locale`, `body`; inventory text |
| `tool_action.py` | `build_messages(rec,skill)`, `short_body(text,n=6000)`, `parse_action_json(text)`, `json_find`, `clamp_int` | rec: `locale`, `question`, `function_inventory`; skill: `body` |
| `culture_scorer.py` | `scorer_messages(kind,task_prompt,card)`, `parse_theory(text)`, `parse_action(text)`, `parse_json_object(text)` | card: `{"name","content"}` |
| `combine_general.py` | `scalar_order(cands)` | cands: `expected_utility`, `theory_overall`, `raw_rank`, `candidate_skill_id` |
| `combine_tool.py` | `strict_guarded_order(cands)`, `enrich_candidates(...)` | cands: `raw_rank`, `candidate_skill_id`, `theory_overall`, `action_score`, `expected_utility`, `language_violation` |
| `combine_culture.py` | `equal_z_order(rows)`, `zscore` | rows: `skill_id`, `fixed_rank`, `stage3_deep_score`, `theory_overall`, `action_score`, `expected_utility` |
| `tool_base_helpers.py` | `json_find(text)`, `inventory_block(row)` | row: `function_inventory` |

Each function keeps the input-field contract of the domain it belongs to;
callers provide candidate rows carrying the fields listed above. Per-module caller contracts
(prompt variant, inventory scope, selector-score convention) are documented in
the module docstrings.

## Notes

- `tool_theory.py` carries the Tool Theory prompt as an immutable literal.
- `combine_tool.enrich_candidates` fills a missing Action score with `-999.0`
  (utility / selector score) and `999.0` (risk), and a missing Theory score
  with overall quality `50.0`.
- The Culture combine consumes the overall Action score via `expected_utility`;
  the risk term does not enter the Cultural fusion.

## License

MIT (see `LICENSE`).

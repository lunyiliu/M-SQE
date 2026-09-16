# SQE Supplementary Data Package

This directory contains the skill pools, test tasks, and deterministic
checkers for the three evaluation domains: **General**, **Tool**, and **Culture**.

## License

Data is released under **CC-BY 4.0**. Checker source code is released under **MIT**
(see `../code/LICENSE`).

## Directory Structure

```
data/
├── pools/
│   ├── general_pool.jsonl   # 1,750 skills (ecological-style / MT / self-generated)
│   ├── tool_pool.jsonl      # 2,299 skills
│   └── culture_pool.jsonl   # 5,285 skills
├── tasks/
│   ├── general_tasks.jsonl  # 94 test tasks
│   ├── tool_tasks.jsonl     # 265 test tasks
│   └── culture_tasks.jsonl  # 52 test tasks
└── checkers/
    ├── general_checker.py   # deterministic answer checker
    ├── tool_checker.py      # function-call checker
    └── culture_checker.py   # short-answer checker
```

## Skill Pools

> **Note**: The skill pools are largely synthesized (machine-translated and
> model-generated layers) and may contain noise. They are evaluation material
> rather than skills curated for direct production use; we recommend applying
> M-SQE quality estimation when consuming skills from these pools.


Each pool record is a JSON object with the following fields:

### General pool & Tool pool

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Sequential identifier (1-based, unique within domain) |
| `body` | str | Skill content text |
| `locale` | str | Language/locale tag (e.g., `en`, `fr`, `en-US`) |
| `production_layer` | str | One of `ecological-style`, `MT`, `self-generated` |

### Culture pool

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Sequential identifier (1-based, unique) |
| `body` | str | Skill content text |
| `production_layer` | str | One of `ecological-style`, `MT`, `self-generated` |

### Production Layer Counts

| Domain | ecological-style | MT | self-generated | Total |
|--------|-----------------|-----|----------------|-------|
| General | 400 | 550 | 800 | 1,750 |
| Tool | 1,254 | 660 | 385 | 2,299 |
| Culture | 3,384 | 1,283 | 618 | 5,285 |

## Test Tasks

### General tasks (94)

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Sequential identifier |
| `query` | str | Task prompt |
| `domain` | str | Always `"general"` |
| `golds` | list[str] | Accepted answers for deterministic checking |

### Tool tasks (265)

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Sequential identifier |
| `query` | str | Task prompt (user question) |
| `domain` | str | Always `"tool"` |
| `locale` | str | Locale tag (e.g., `en-US`) |
| `function_inventory` | list[dict] | Available function schemas |
| `gold_call` | dict | Expected function call (e.g., `{"alarm.query": {}}`) |
| `gold_function` | str | Expected function name |
| `gold_function_schema` | dict \| null | Schema of the gold function |

### Culture tasks (52)

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Sequential identifier |
| `query` | str | Task prompt |
| `domain` | str | Always `"culture"` |
| `culture_region` | str | One of six culture regions (see below) |
| `answer_key` | dict | Checker data: `canonical`, `accept_examples`, `reject_examples`, `scorer_rule` (`required_any_terms`) |

### Six Culture Regions

| Region | Task Count |
|--------|-----------|
| East and Southeast Asia | 20 |
| Europe | 12 |
| Africa and the Middle East | 6 |
| South Asia | 5 |
| the Americas | 5 |
| Oceania | 4 |

## Checkers

Each checker module contains the deterministic scoring logic used to grade
a model answer for its domain.

### General checker (`general_checker.py`)

```python
evaluate_deterministic(task: dict, answer: str) -> tuple[bool, str | None]
```

Normalizes the answer and checks membership in `task["golds"]`.

### Tool checker (`tool_checker.py`)

```python
check_call(prediction, gold: dict, *, function_schema: dict | None = None) -> CheckResult
```

Parses the prediction into a single function call, then compares function name
and slot values against the gold call. Returns a `CheckResult` dataclass with
`ok`, `reason`, `pred_name`, `gold_name` fields.

### Culture checker (`culture_checker.py`)

```python
parse_json_object(text: str) -> tuple[dict | None, str | None]
score_answer(task: dict, parsed: dict | None, parse_error: str | None) -> dict
```

Parses the model output as JSON, then scores against `task["answer_key"]` using
alias matching and required-term matching. Returns a dict with `strict_score`
(`"pass"` / `"fail"` / `"invalid"`), `lenient_pass`, and diagnostic fields.

## Usage

Load JSONL files with any JSONL parser. Import checker modules directly.
Each checker function is self-contained and requires no external dependencies
beyond the Python standard library.

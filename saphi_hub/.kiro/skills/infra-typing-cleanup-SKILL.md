---
name: infra-typing-cleanup
description: >
  Guides agents through eliminating Pyright warnings in infrastructure layers without
  touching domain logic. Applies the correct technique per data source: Pydantic for
  external JSON boundaries, native annotations for internal data, Dialect for
  SQLAlchemy TypeDecorators, and TypedDict for known internal structures like JWT
  payloads. Use when Pyright reports warnings in adapter, mapper, persistence, or
  router files and you need to resolve them with minimal, correct typing.
metadata:
  model: claude-sonnet-4-5
---

# Infra Typing Cleanup

## Overview

Infrastructure code accumulates Pyright warnings because it sits at the boundary
between typed domain logic and untyped external systems — HTTP APIs, ORMs, JWT
libraries. The instinct is to silence warnings with `# type: ignore`. That's wrong.
Each warning is a signal about a real gap in type safety, and each gap has a specific
fix that matches the source of the data.

This skill gives agents a decision tree: identify the warning category, pick the right
technique, apply it in the right order, verify at each step. The result is
infrastructure that is both clean to Pyright and correct at runtime.

## When to Use

- Pyright reports `reportUnknownVariableType`, `reportUnknownMemberType`, or
  `reportUnknownArgumentType` in infrastructure files (adapters, mappers, persistence,
  routers, security).
- You need to choose between Pydantic, `TypedDict`, `cast()`, or explicit annotations
  and want the correct tool for the job.
- You are adding a new integration with an external API or ORM column and want to type
  it correctly from the start.
- A teammate left `# type: ignore` comments you need to replace with real fixes.

## Process

### Step 1 — Run Pyright and triage every warning

```bash
PYTHONPATH=app pyright app/<module>/
```

Do not fix anything yet. Collect all warnings and classify each one using this table:

| Category | Pyright symptom | Correct technique |
|----------|----------------|-------------------|
| **External boundary** | `dict[Unknown, Unknown]` from `.json()` on an HTTP response | Pydantic `BaseModel` |
| **Internal JSONB / ORM** | `dict[Unknown, Unknown]` from a SQLAlchemy JSON/JSONB column | `cast(list[dict[str, Any]], ...)` + explicit annotations |
| **TypeDecorator dialect** | Untyped `dialect` parameter in `process_bind_param` / `process_result_value` | `from sqlalchemy.engine import Dialect` |
| **Decoded payload** | `dict[str, Unknown]` from `jwt.decode()` or similar internal deserializer | `TypedDict` + `cast()` |
| **Untyped empty list** | `list[Unknown]` from bare `= []` or `field(default_factory=list)` with no context | Explicit annotation or `default_factory=list[str]` |

Stop here if you cannot classify a warning. Ask for clarification before proceeding.

### Step 2 — Order fixes from least to most invasive

Work in this sequence to minimize risk at each step:

1. **One-liner fixes** — import + parameter annotation (e.g. `Dialect`, untyped lists)
2. **Signature annotations** — add types to existing function signatures without changing logic (e.g. mappers)
3. **Local TypedDict + cast** — define a TypedDict and cast the decoded value (e.g. JWT router)
4. **Pydantic models + refactor** — new private models and method changes (e.g. HTTP adapters)

**Checkpoint:** run Pyright on each file after completing its fix before moving to the
next file. Do not batch fixes across files.

### Step 3 — Apply the technique for each category

#### External boundary → Pydantic BaseModel

```python
from pydantic import BaseModel, Field, ValidationError

class _ExternalResponse(BaseModel):   # _ prefix = private to this module
    required_field: str
    optional_field: str | None = None
    list_field: list[str] = Field(default_factory=list)

# At the call site:
try:
    data = _ExternalResponse.model_validate(response.json())
except ValidationError as exc:
    logger.error("Invalid response: %s", exc)
    return Err(ApiError(...))

result = data.required_field   # typed attribute access, not dict subscript
```

Rules:
- Prefix private models with `_`. They are implementation details, not exports.
- Optional fields use `= None`, not `Optional[...]`.
- Mutable defaults use `Field(default_factory=list)`, never `= []`.
- Always catch `ValidationError` and convert it to a domain error at the boundary.

#### Internal JSONB → cast + explicit annotations

```python
from typing import Any, cast

def _parse_items(raw: list[dict[str, Any]] | None) -> list[DomainObject]:
    if not raw:
        return []
    result: list[DomainObject] = []   # explicit annotation, not inferred
    for item in raw:
        result.append(DomainObject(
            name=item.get("name", "") or "",   # guard against None with `or`
        ))
    return result

# In the mapper reading the JSONB column:
raw_data = cast(list[dict[str, Any]] | None, row.jsonb_column)  # type: ignore[arg-type]
items = _parse_items(raw_data)
```

Do not use Pydantic here. JSONB data is internal — the system wrote it, so runtime
validation adds overhead without safety benefit. Annotations are sufficient.

#### TypeDecorator dialect → SQLAlchemy Dialect

```python
from sqlalchemy.engine import Dialect

class MyTypeDecorator(TypeDecorator):
    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        ...

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        ...
```

This is always a two-line fix: one import, one annotation per method. Nothing else changes.

#### Decoded payload → TypedDict + cast

```python
from typing import TypedDict, cast

class _JWTPayload(TypedDict):   # _ prefix if private to this module
    sub:  str
    role: str
    iat:  int
    exp:  int

# At the call site:
case Ok(value=payload):
    jwt_payload = cast(_JWTPayload, payload)
    user_id = uuid.UUID(jwt_payload["sub"])   # no type: ignore needed
```

`TypedDict` is static documentation only. It does not validate at runtime. The decode
call must already have error handling; this only tells Pyright what shape to expect.

#### Untyped empty list → explicit annotation or parametrized factory

```python
# Before — Pyright infers list[Unknown]
codes_seen = []
tokens_seen: list[str] = field(default_factory=list)

# After — Pyright knows the element type
codes_seen: list[str] = []
tokens_seen: list[str] = field(default_factory=list[str])
```

### Step 4 — Verify each file before moving on

```bash
PYTHONPATH=app pyright app/path/to/file.py
```

Required output: `0 errors, 0 warnings`. If warnings remain, do not move to the next
file. Diagnose and fix before continuing.

### Step 5 — Verify the full module

```bash
PYTHONPATH=app pyright app/<module>/
```

Required output: `0 errors, 0 warnings` across all modified files. Note: a fix in one
file can surface new warnings in another by tightening a previously loose type. These
are real issues — apply the same triage process.

### Step 6 — Run the test suite

```bash
pytest tests/<module>/ -v
```

Required output: all tests green, no modifications to test files. A typing change that
breaks tests modified behavior, not just annotations — investigate before shipping.

---

## Rationalizations

Agents often rationalize skipping steps. These are the common ones and why they are wrong.

| Rationalization | Why it's wrong |
|-----------------|----------------|
| "I'll just add `# type: ignore` and move on." | `# type: ignore` silences the signal without fixing the problem. It hides real type errors and makes the next engineer's job harder. It is never an acceptable final state. |
| "Pydantic everywhere — even for internal data." | Pydantic validates at runtime. Internal JSONB data was written by your own system. Running validation on every read adds overhead without safety benefit. Use `cast` + annotations for internal data. |
| "TypedDict is enough for external API responses." | TypedDict does not validate at runtime. If the external API changes its contract, the error surfaces late and in a confusing place. Always use Pydantic at external boundaries. |
| "Pyright will infer the return type for me." | It won't — not with SQLAlchemy mapped columns, `jose`, `httpx`, or any library missing type stubs. Explicit annotations are the contract, not a Pyright workaround. |
| "I'll fix all files in one commit." | One commit per file makes it easy to review, bisect, and revert. The ordering in Step 2 exists for a reason — each step builds on a verified baseline. |
| "The warning is in a test double, it doesn't matter." | Test doubles define contracts. An untyped `list[Unknown]` in a fake adapter means the fake's interface drifts silently from the real one. Fix it. |

---

## Red Flags

Stop and reassess if you observe any of these during the fix:

- `# type: ignore` appears in the diff where it did not exist before.
- Tests fail after a typing change — the change touched logic, not just annotations.
- Pyright reports new warnings in files you did not modify — a type contract upstream changed.
- A Pydantic model grows beyond ~8 fields — the boundary may be too wide; check whether all fields are actually used downstream.
- You reach for `Any` on a field that represents a specific, known structure — define the structure instead.
- The same `cast()` appears in more than two places — the type gap should be fixed at the source, not papered over at every call site.

---

## Verification

The following evidence is required before this skill is considered complete. "Seems
right" is not evidence.

1. **Pyright passes on the full module**
   ```bash
   PYTHONPATH=app pyright app/<module>/
   # Required: 0 errors, 0 warnings
   ```

2. **Tests pass without modification**
   ```bash
   pytest tests/<module>/ -v
   # Required: all green, no test files changed
   ```

3. **Diff is scoped to planned files**
   ```bash
   git diff --stat
   # Required: only the files identified in triage appear
   ```

4. **No new `# type: ignore` comments**
   ```bash
   git diff | grep "type: ignore"
   # Required: no new occurrences (existing ones are acceptable if pre-existing)
   ```

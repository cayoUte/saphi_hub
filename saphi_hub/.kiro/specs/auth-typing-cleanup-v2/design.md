# Design Document

## Overview

This design implements the infra-typing-cleanup skill to resolve 2 Pyright warnings in the auth module infrastructure layer. The warnings fall into two categories:

1. **Internal JSONB data** (`orm_models.py:85`) - `raw_repos` column needs explicit type annotation
2. **JWT payload** (`token_issuer.py:69`) - decoded payload needs TypedDict definition

The fix strategy follows the skill's least-to-most invasive ordering: start with simple signature annotations (JSONB), then introduce TypedDict for the JWT payload. Each file is verified individually before moving to the next.

**Why this approach:**
- Explicit annotations for JSONB avoid runtime validation overhead for internal data
- TypedDict for JWT provides static type safety without changing decode behavior
- Incremental verification catches regressions early
- No changes to domain logic or tests required

## Architecture

This is not a new feature - it's a typing improvement to existing infrastructure. No architectural changes are needed.

**Affected layers:**
- **Persistence layer**: `orm_models.py` (ORM model annotations)
- **Security layer**: `token_issuer.py` (JWT decode typing)

**No changes to:**
- Domain entities or value objects
- Application use cases
- API routes or schemas
- Test files

## Components and Interfaces

### Component 1: ORM Models (`orm_models.py`)

**Current state:**
```python
raw_repos: Mapped[dict | None] = mapped_column(JSONB)
```

Pyright infers `dict[Unknown, Unknown] | None` because the generic `dict` lacks type parameters.

**Target state:**
```python
from typing import Any

raw_repos: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
```

**Rationale:**
- `raw_repos` stores GitHub repository data written by our own system
- The structure is internal - no external validation needed
- `dict[str, Any]` tells Pyright "string keys, any values"
- This is the correct annotation for JSONB columns per the skill

**Interface impact:** None. This is a type annotation change only. Mappers that read this field will see the same runtime value.

### Component 2: JWT Token Issuer (`token_issuer.py`)

**Current state:**
```python
def decode(self, token: str) -> Result[dict[str, Any], TokenExpiredError | TokenInvalidError]:
    # ...
    payload = jwt.decode(...)  # Pyright infers dict[str, Unknown]
    return Ok(payload)
```

**Target state:**
```python
from typing import TypedDict, cast

class _JWTPayload(TypedDict):
    """Structure of JWT payload decoded by jose.jwt.decode()."""
    sub: str   # user_id as string
    role: str  # user role value
    iat: int   # issued at (UTC epoch)
    exp: int   # expires at (UTC epoch)

def decode(self, token: str) -> Result[_JWTPayload, TokenExpiredError | TokenInvalidError]:
    # ...
    raw_payload = jwt.decode(...)
    payload = cast(_JWTPayload, raw_payload)
    return Ok(payload)
```

**Changes:**
1. Define `_JWTPayload` TypedDict with exact structure documented in module docstring
2. Cast the decoded payload to `_JWTPayload`
3. Update return type from `dict[str, Any]` to `_JWTPayload`

**Rationale:**
- `jose.jwt.decode()` returns `dict[str, Any]` at runtime
- The skill specifies TypedDict + cast for known internal structures like JWT
- TypedDict is static documentation - no runtime validation
- Underscore prefix indicates this is private to the module
- The decode call already has error handling via `options={"require": [...]}`

**Interface impact:** 
- Callers of `decode()` will receive `Result[_JWTPayload, ...]` instead of `Result[dict[str, Any], ...]`
- This is a refinement - callers can access payload fields with better type safety
- No runtime behavior changes

## Data Models

No new data models. The changes are type annotations for existing structures.

**Existing structures being typed:**

1. **raw_repos (JSONB column):**
   - Type: `dict[str, Any] | None`
   - Purpose: Store raw GitHub repository data
   - Source: GitHub API via adapter
   - Destination: Mappers for domain entity construction

2. **JWT Payload (TypedDict):**
   - Structure defined in `_JWTPayload`
   - Fields match JWT RFC 7519 claims plus private `role` claim
   - Source: `jose.jwt.decode()`
   - Destination: FastAPI dependency for user authentication

## Error Handling

No new error handling required. The typing changes do not alter error conditions or handling:

1. **ORM models:** JSONB column annotation doesn't change null handling or SQLAlchemy behavior
2. **JWT decode:** TypedDict cast doesn't change JWT validation or error paths. Existing error handling for `ExpiredSignatureError` and `JWTError` remains unchanged.

**Type safety improvements:**
- Pyright will catch missing or mistyped JWT payload field accesses at static analysis time
- JSONB column access will be properly typed for downstream mappers

## Testing Strategy

**Test philosophy for typing changes:**
- Typing annotations should NOT require test modifications
- If tests fail, the typing change altered behavior (red flag)
- Verification is via Pyright + test suite confirmation, not new tests

**Verification approach:**

1. **Unit tests:** Run existing `pytest tests/auth/` suite
   - Expected: All tests pass without modification
   - Purpose: Confirm typing changes didn't alter runtime behavior

2. **Static type checking:** Run Pyright at each stage
   - After each file fix: `pyright <file>`
   - After all fixes: `pyright app/auth/infrastructure/`
   - Expected: 0 errors, 0 warnings

3. **Integration verification:** No separate integration tests needed
   - The existing auth flow tests cover JWT issuance and decode
   - The existing persistence tests cover JSONB column read/write

**Why no property-based testing:**
This is not a new feature with universal properties to verify. It's a type annotation improvement to existing code. The correct verification is:
1. Pyright accepts the types (static verification)
2. Existing tests pass (behavior unchanged)
3. No new `# type: ignore` comments (proper fixes, not suppressions)

**Test execution order:**
1. Run Pyright on individual files as they're fixed
2. Run Pyright on full module after all fixes
3. Run full auth test suite: `pytest tests/auth/ -v`

**Red flags:**
- Any test failure → typing change broke behavior
- New `# type: ignore` in diff → warning suppressed instead of fixed
- Pyright reports new warnings in other files → type contract changed upstream

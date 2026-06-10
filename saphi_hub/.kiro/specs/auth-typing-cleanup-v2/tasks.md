# Implementation Plan: Auth Typing Cleanup V2

## Overview

Apply the infra-typing-cleanup skill to eliminate 2 Pyright warnings in the auth module infrastructure. Fix order follows least-to-most invasive: start with simple JSONB annotation, then introduce TypedDict for JWT payload. Each file is verified before moving to the next.

**Target warnings:**
1. `orm_models.py:85` - `raw_repos` field (Internal JSONB/ORM category)
2. `token_issuer.py:69` - `payload` variable (Decoded payload category)

**Success criteria:**
- Pyright reports 0 errors, 0 warnings on `app/auth/infrastructure/`
- All tests pass without modification
- No new `# type: ignore` comments

## Tasks

- [x] 1. Fix JSONB column annotation in orm_models.py
  - Add `from typing import Any` import
  - Change `raw_repos: Mapped[dict | None]` to `Mapped[dict[str, Any] | None]`
  - Run Pyright verification: `PYTHONPATH=app pyright app/auth/infrastructure/persistence/orm_models.py`
  - Confirm output is 0 errors, 0 warnings
  - _Requirements: 2.1, 2.2, 2.3, 5.1, 5.2_

- [x] 2. Define JWT payload TypedDict and update token_issuer.py
  - [x] 2.1 Add TypedDict import and define `_JWTPayload`
    - Add `from typing import TypedDict, cast`
    - Define `_JWTPayload` with fields: `sub` (str), `role` (str), `iat` (int), `exp` (int)
    - Add docstring explaining structure
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 2.2 Update decode method to use TypedDict
    - Change return type from `Result[dict[str, Any], ...]` to `Result[_JWTPayload, ...]`
    - Assign `jwt.decode()` result to `raw_payload` variable
    - Cast with `payload = cast(_JWTPayload, raw_payload)`
    - Return `Ok(payload)`
    - _Requirements: 3.3, 4.1_

  - [x] 2.3 Verify token_issuer.py with Pyright
    - Run: `PYTHONPATH=app pyright app/auth/infrastructure/security/token_issuer.py`
    - Confirm output is 0 errors, 0 warnings
    - _Requirements: 3.5, 5.1, 5.2, 5.3_

- [x] 3. Verify full auth/infrastructure/ module
  - Run: `PYTHONPATH=app pyright app/auth/infrastructure/`
  - Confirm output is 0 errors, 0 warnings across all files
  - Check for any new warnings in files not directly modified
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 4. Run auth module test suite
  - Run: `pytest tests/auth/ -v`
  - Confirm all tests pass with 0 failures
  - Verify no test files were modified
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 5. Verify no new type ignore comments
  - Run: `git diff | grep "type: ignore"`
  - Confirm no new occurrences appear in the diff
  - _Requirements: 8.1, 8.2, 8.3_

- [x] 6. Final checkpoint - Review diff and verify completion
  - Ensure all tests pass, ask the user if questions arise.
  - Review `git diff --stat` to confirm only expected files modified
  - Verify Pyright output shows 0 errors, 0 warnings
  - Verify test suite shows all green

## Notes

- Tasks follow the skill's least-to-most invasive ordering
- Each file is verified individually before proceeding
- No test modifications should be needed (typing-only changes)
- The skill explicitly prohibits `# type: ignore` as a solution
- JSONB uses explicit annotation (no Pydantic - internal data)
- JWT uses TypedDict + cast (static typing without runtime validation)

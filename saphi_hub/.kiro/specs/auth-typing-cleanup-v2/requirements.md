# Requirements Document

## Introduction

This spec applies the infra-typing-cleanup skill to eliminate Pyright warnings in the auth module infrastructure layer. The goal is to achieve 0 errors and 0 warnings by applying the correct typing technique for each data source category: explicit annotations for internal JSONB data and TypedDict+cast for JWT payloads.

**Current State:**
- Pyright reports 2 warnings in auth/infrastructure/
- Warning 1: `orm_models.py:85` - `raw_repos` field typed as `dict[Unknown, Unknown] | None`
- Warning 2: `token_issuer.py:69` - `payload` variable typed as `dict[str, Unknown]`

**Target State:**
- 0 errors, 0 warnings from Pyright on the full auth/infrastructure/ directory
- All tests pass without modification
- No new `# type: ignore` comments introduced

## Glossary

- **System**: The auth module infrastructure layer
- **Pyright**: Static type checker for Python
- **JSONB**: PostgreSQL JSON Binary column type used for storing internal structured data
- **JWT**: JSON Web Token - structured payload decoded from authenticated requests
- **TypedDict**: Python typing construct for defining dictionary structure statically
- **ORM**: Object-Relational Mapping layer (SQLAlchemy)

## Requirements

### Requirement 1: Triage and Classify Warnings

**User Story:** As a developer, I want all Pyright warnings classified by category, so that I can apply the correct typing technique to each one.

#### Acceptance Criteria

1. WHEN Pyright runs on `app/auth/infrastructure/`, THE System SHALL identify all warnings by file and line number
2. WHEN a warning involves a JSONB column (internal data), THE System SHALL classify it as "Internal JSONB/ORM"
3. WHEN a warning involves a decoded JWT payload, THE System SHALL classify it as "Decoded payload"
4. THE System SHALL document the classification decision for each warning with rationale

### Requirement 2: Fix Internal JSONB Type Warnings

**User Story:** As a developer, I want JSONB column types properly annotated, so that Pyright understands the structure of internal data without runtime validation overhead.

#### Acceptance Criteria

1. WHEN `raw_repos` is a JSONB column storing internal data, THE System SHALL use explicit type annotation `Mapped[dict[str, Any] | None]`
2. WHEN the column may be null, THE System SHALL include `| None` in the annotation
3. THE System SHALL NOT use Pydantic validation for internal JSONB data
4. WHEN the fix is applied, Pyright SHALL report 0 warnings for `orm_models.py`

### Requirement 3: Fix JWT Payload Type Warnings

**User Story:** As a developer, I want JWT payload structure explicitly typed, so that Pyright knows the expected shape without runtime validation.

#### Acceptance Criteria

1. WHEN a JWT is decoded, THE System SHALL define a `_JWTPayload` TypedDict with all expected fields
2. THE `_JWTPayload` TypedDict SHALL include fields: `sub` (str), `role` (str), `iat` (int), `exp` (int)
3. WHEN the payload is decoded, THE System SHALL cast it to `_JWTPayload`
4. THE System SHALL use underscore prefix for private module-level TypedDict definitions
5. WHEN the fix is applied, Pyright SHALL report 0 warnings for `token_issuer.py`

### Requirement 4: Apply Fixes in Least-to-Most Invasive Order

**User Story:** As a developer, I want fixes applied incrementally, so that each change can be verified before proceeding to the next.

#### Acceptance Criteria

1. THE System SHALL fix signature annotations before introducing new types
2. WHEN fixing multiple files, THE System SHALL complete and verify one file before starting the next
3. WHEN a file is fixed, Pyright SHALL report 0 errors and 0 warnings for that file before moving on

### Requirement 5: Verify Each File After Fixing

**User Story:** As a developer, I want each file verified immediately after fixing, so that regressions are caught early.

#### Acceptance Criteria

1. WHEN a file's types are modified, THE System SHALL run Pyright on that specific file
2. THE verification SHALL require 0 errors and 0 warnings as output
3. IF warnings remain after a fix attempt, THE System SHALL NOT proceed to the next file

### Requirement 6: Verify Full Module After All Fixes

**User Story:** As a developer, I want the entire auth/infrastructure/ directory verified, so that cross-file type interactions are validated.

#### Acceptance Criteria

1. WHEN all individual file fixes are complete, THE System SHALL run Pyright on `app/auth/infrastructure/`
2. THE full module verification SHALL require 0 errors and 0 warnings as output
3. IF new warnings surface in previously fixed files, THE System SHALL diagnose and fix them before completion

### Requirement 7: Verify Tests Pass Without Modification

**User Story:** As a developer, I want all tests to pass without changes, so that I know typing changes did not alter behavior.

#### Acceptance Criteria

1. WHEN typing fixes are complete, THE System SHALL run the auth module test suite
2. THE test suite SHALL pass with 0 failures
3. THE System SHALL NOT modify any test files to make tests pass
4. IF tests fail, THE System SHALL diagnose whether the typing change altered behavior

### Requirement 8: Prevent Introduction of Type Ignore Comments

**User Story:** As a developer, I want to ensure no new `# type: ignore` comments are added, so that type warnings are properly resolved rather than silenced.

#### Acceptance Criteria

1. THE System SHALL NOT add new `# type: ignore` comments to any file
2. WHEN a diff is generated, THE System SHALL verify no new occurrences of `type: ignore` appear
3. IF a fix requires `# type: ignore`, THE System SHALL document why and seek an alternative approach

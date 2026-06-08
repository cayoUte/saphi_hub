# Requirements Document

## Introduction

Este spec documenta la aplicación del skill de infra-typing para eliminar los 27 warnings de Pyright en 4 archivos de la capa de infraestructura del módulo auth. El objetivo es mejorar la seguridad de tipos sin modificar la lógica de dominio, usando las técnicas apropiadas para cada caso: modelos Pydantic para JSON externo, anotaciones explícitas para datos internos, y tipos de SQLAlchemy para el ORM.

## Requirements

### Requirement 1: Eliminar warnings de Pyright en adapter.py usando modelos Pydantic

**User Story:** Como desarrollador, quiero que el adaptador de GitHub tenga tipos explícitos para las respuestas de API, para que Pyright pueda validar el manejo correcto de datos externos.

#### Acceptance Criteria

1. WHEN se procesan respuestas JSON de la API de GitHub THEN el sistema SHALL usar modelos Pydantic para validar estructura y tipos
2. WHEN se define el modelo `_GitHubTokenResponse` THEN SHALL incluir campos `access_token`, `error` y `error_description` como opcionales
3. WHEN se define el modelo `_GitHubEmailEntry` THEN SHALL incluir campos `email` (str), `primary` (bool) y `verified` (bool)
4. WHEN se define el modelo `_GitHubRepoEntry` THEN SHALL incluir campos `name`, `language`, `topics`, `stargazers_count` y `fork`
5. WHEN se define el modelo `_GitHubProfileResponse` THEN SHALL incluir campos `id`, `login`, `name` y `email`
6. WHEN se ejecuta `pyright app/auth/infrastructure/github/adapter.py` THEN SHALL reportar 0 warnings

### Requirement 2: Eliminar warnings de Pyright en mappers.py con anotaciones explícitas

**User Story:** Como desarrollador, quiero que las funciones de mapeo tengan tipos explícitos para dict[str, Any], para que Pyright entienda el manejo de datos JSONB sin necesidad de modelos Pydantic adicionales.

#### Acceptance Criteria

1. WHEN se define la función `_parse_raw_repos` THEN SHALL anotarse con parámetro `list[dict[str, Any]] | None`
2. WHEN se define la función `_serialize_raw_repos` THEN SHALL retornar `list[dict[str, Any]]`
3. WHEN se accede a `row.raw_repos` en `orm_to_github_identity` THEN SHALL usar `cast(list[dict[str, Any]] | None, row.raw_repos)`
4. WHEN se ejecuta `pyright app/auth/infrastructure/persistence/mappers.py` THEN SHALL reportar 0 warnings

### Requirement 3: Eliminar warnings de Pyright en encryption.py con tipos de SQLAlchemy

**User Story:** Como desarrollador, quiero que los métodos de TypeDecorator tengan el parámetro dialect tipado correctamente, para que Pyright reconozca el tipo del engine de SQLAlchemy.

#### Acceptance Criteria

1. WHEN se define `process_bind_param` THEN el parámetro `dialect` SHALL tener tipo `Dialect`
2. WHEN se define `process_result_value` THEN el parámetro `dialect` SHALL tener tipo `Dialect`
3. WHEN se importa el tipo Dialect THEN SHALL importarse desde `sqlalchemy.engine`
4. WHEN se ejecuta `pyright app/auth/infrastructure/persistence/encryption.py` THEN SHALL reportar 0 warnings

### Requirement 4: Eliminar warnings de Pyright en router.py con JWT payload tipado

**User Story:** Como desarrollador, quiero que el payload del JWT tenga una estructura tipada explícita, para que Pyright pueda validar el acceso a campos del token decodificado.

#### Acceptance Criteria

1. WHEN se define `_JWTPayload` THEN SHALL ser un TypedDict con campos `sub` (str), `role` (str), `iat` (int) y `exp` (int)
2. WHEN se decodifica un JWT en `get_me` THEN el payload SHALL validarse contra la estructura `_JWTPayload`
3. WHEN se accede a campos del payload THEN NO SHALL requerir comentarios `# type: ignore`
4. WHEN se ejecuta `pyright app/auth/routes/router.py` THEN SHALL reportar 0 warnings

### Requirement 5: Verificación completa del módulo auth

**User Story:** Como desarrollador, quiero que todos los archivos del módulo auth estén libres de warnings de Pyright y que los tests sigan pasando, para garantizar que los cambios de tipado no introdujeron regresiones.

#### Acceptance Criteria

1. WHEN se ejecuta `pyright app/auth/` THEN SHALL reportar 0 warnings en los 4 archivos modificados
2. WHEN se ejecutan los tests THEN `pytest tests/auth/ -v` SHALL completar exitosamente
3. WHEN se revisan los cambios THEN NO SHALL existir comentarios `# type: ignore` nuevos
4. WHEN se implementan los modelos Pydantic THEN SHALL tener prefijo `_` para indicar que son privados al módulo

# Implementation Plan

- [x] 1. Fix encryption.py con tipos de SQLAlchemy Dialect

  - Agregar import `from sqlalchemy.engine import Dialect`
  - Anotar parámetro `dialect: Dialect` en `process_bind_param()`
  - Anotar parámetro `dialect: Dialect` en `process_result_value()`
  - Ejecutar `pyright app/auth/infrastructure/persistence/encryption.py` para verificar 0 warnings
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 2. Fix mappers.py con anotaciones explícitas dict[str, Any]

  - Agregar import `from typing import Any` si no existe
  - Modificar firma de `_parse_raw_repos()` para aceptar `list[dict[str, Any]] | None`
  - Agregar anotación explícita `result: list[GitHubRawRepo] = []` en `_parse_raw_repos()`
  - Proteger accesos con `or` operator: `item.get("name", "") or ""`
  - Modificar firma de `_serialize_raw_repos()` para retornar `list[dict[str, Any]]`
  - Agregar `cast(list[dict[str, Any]] | None, row.raw_repos)` en `orm_to_github_identity()`
  - Ejecutar `pyright app/auth/infrastructure/persistence/mappers.py` para verificar 0 warnings
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3. Fix router.py usando el TypedDict JWTPayload existente

  - Verificar que `JWTPayload` TypedDict ya está definido con campos `sub`, `role`, `iat`, `exp`
  - Modificar el pattern matching en `get_me()` para usar `cast(JWTPayload, payload)`
  - Asignar resultado del cast a variable `jwt_payload`
  - Usar `jwt_payload["sub"]` sin comentarios `# type: ignore`
  - Ejecutar `pyright app/auth/routes/router.py` para verificar 0 warnings
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 4. Fix adapter.py con modelos Pydantic para respuestas de GitHub

- [x] 4.1 Crear modelos Pydantic privados

  - Agregar imports: `from pydantic import BaseModel, Field`
  - Definir `_GitHubTokenResponse` con campos `access_token`, `error`, `error_description`
  - Definir `_GitHubProfileResponse` con campos `id`, `login`, `name`, `email`
  - Definir `_GitHubEmailEntry` con campos `email`, `primary`, `verified`
  - Definir `_GitHubRepoEntry` con campos `name`, `language`, `topics`, `stargazers_count`, `fork`
  - _Requirements: 1.2, 1.3, 1.4, 1.5_

- [x] 4.2 Refactorizar exchange_code() con validación Pydantic

  - Reemplazar `data = response.json()` con `data = _GitHubTokenResponse.model_validate(response.json())`
  - Agregar try/except para capturar `ValidationError` de Pydantic
  - Cambiar accesos de dict a atributos: `data.error`, `data.access_token`
  - Mejorar validación: verificar `if not data.access_token` antes de crear GitHubToken

  - _Requirements: 1.1, 1.6_

- [x] 4.3 Refactorizar fetch_user() eliminando \_get_json()

  - Hacer request HTTP inline en lugar de usar `_get_json()`
  - Validar respuesta con `profile = _GitHubProfileResponse.model_validate(resp.json())`
  - Agregar try/except para `HTTPStatusError` y `RequestError`

  - Acceder a campos tipados: `profile.id`, `profile.login`, `profile.name`, `profile.email`
  - Actualizar construcción de `GitHubUserPayload` con campos del modelo
  - _Requirements: 1.1, 1.6_

- [x] 4.4 Refactorizar \_fetch_primary_email() con validación Pydantic

  - Validar cada entrada: `entries = [_GitHubEmailEntry.model_validate(e) for e in response.json()]`
  - Cambiar accesos de dict a atributos: `entry.primary`, `entry.verified`, `entry.email`
  - Mantener lógica de fallback si no hay email primario verificado
  - _Requirements: 1.1, 1.6_

- [x] 4.5 Refactorizar \_fetch_repos() con validación Pydantic

  - Validar cada repo: `entries = [_GitHubRepoEntry.model_validate(r) for r in response.json()]`
  - Filtrar usando atributo: `if not entry.fork`
  - Mapear a GitHubRawRepo usando atributos: `entry.name`, `entry.language`, etc.
  - _Requirements: 1.1, 1.6_

- [x] 4.6 Verificar adapter.py completo

  - Ejecutar `pyright app/auth/infrastructure/github/adapter.py` para verificar 0 warnings
  - Verificar que no se usa `_get_json()` en ningún lugar
  - _Requirements: 1.6_

- [x] 5. Ejecutar verificación completa del módulo auth


  - Ejecutar `pyright app/auth/` para verificar 0 warnings en todos los archivos
  - Ejecutar `pytest tests/auth/ -v` para verificar que todos los tests pasan
  - Verificar que no hay comentarios `# type: ignore` nuevos en los archivos modificados
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

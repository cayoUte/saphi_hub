# Design Document

## Overview

Este documento describe la estrategia de implementación para eliminar los 27 warnings de Pyright en 4 archivos de infraestructura del módulo auth. La solución aplica técnicas específicas según la naturaleza de cada archivo:

1. **adapter.py**: Modelos Pydantic para validar JSON externo de la API de GitHub
2. **mappers.py**: Anotaciones explícitas `dict[str, Any]` para datos JSONB internos
3. **encryption.py**: Tipo `Dialect` de SQLAlchemy para parámetros de TypeDecorator
4. **router.py**: TypedDict para estructurar el payload JWT decodificado

El diseño prioriza la seguridad de tipos sin modificar la lógica de dominio, usando herramientas apropiadas para cada caso (Pydantic para boundaries externos, anotaciones nativas para infra interna).

## Architecture

### Principios de diseño

1. **Boundary validation con Pydantic**: Los datos externos (API de GitHub) se validan en el punto de entrada con modelos Pydantic privados al módulo.

2. **Anotaciones explícitas internas**: Los datos internos (JSONB de SQLAlchemy) se tipan con anotaciones nativas de Python sin overhead de validación.

3. **Tipos de SQLAlchemy correctos**: Los métodos de TypeDecorator usan el tipo `Dialect` para que Pyright reconozca la interfaz del engine.

4. **Estructuras tipadas para JWT**: El payload decodificado usa TypedDict para documentar estructura y permitir verificación estática.

### Orden de implementación

La implementación debe seguir este orden específico para minimizar riesgos:

```
encryption.py (2 líneas) → mappers.py (anotaciones) → router.py (TypedDict) → adapter.py (Pydantic completo)
```

Cada paso debe verificarse con Pyright antes de continuar al siguiente.

## Components and Interfaces

### 1. adapter.py — Modelos Pydantic privados

Se crean 4 modelos Pydantic con prefijo `_` (privados al módulo) que mapean las respuestas de la API de GitHub:

#### `_GitHubTokenResponse`
```python
class _GitHubTokenResponse(BaseModel):
    """Respuesta de POST /login/oauth/access_token"""
    access_token: str | None = None
    error: str | None = None
    error_description: str | None = None
```

**Uso**: Reemplaza el acceso directo a `response.json()` en `exchange_code()`. Valida la estructura y elimina los warnings de `dict[Unknown, Unknown]`.

#### `_GitHubProfileResponse`
```python
class _GitHubProfileResponse(BaseModel):
    """Respuesta de GET /user"""
    id: int
    login: str
    name: str | None = None
    email: str | None = None
```

**Uso**: Valida el perfil principal del usuario en `fetch_user()`.

#### `_GitHubEmailEntry`
```python
class _GitHubEmailEntry(BaseModel):
    """Entrada de GET /user/emails"""
    email: str
    primary: bool
    verified: bool
```

**Uso**: Valida cada email en la lista devuelta por `/user/emails` en `_fetch_primary_email()`.

#### `_GitHubRepoEntry`
```python
class _GitHubRepoEntry(BaseModel):
    """Entrada de GET /user/repos"""
    name: str
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    stargazers_count: int = 0
    fork: bool = False
```

**Uso**: Valida cada repo en la lista devuelta por `/user/repos` en `_fetch_repos()`.

#### Refactorización de métodos

**`exchange_code()`**: Eliminar el acceso directo a dict y usar validación Pydantic:
- `data = _GitHubTokenResponse.model_validate(response.json())`
- Acceder a campos como `data.access_token` en lugar de `data.get("access_token")`
- Mejorar el manejo de errores con validación temprana

**`fetch_user()`**: Refactorizar para eliminar `_get_json()` y validar directamente:
- Hacer la request HTTP inline
- Validar con `_GitHubProfileResponse.model_validate(resp.json())`
- Acceder a campos tipados: `profile.id`, `profile.login`, etc.

**`_fetch_primary_email()`**: Validar cada entrada de la lista:
- `entries = [_GitHubEmailEntry.model_validate(e) for e in response.json()]`
- Acceder a campos tipados: `entry.primary`, `entry.verified`, `entry.email`

**`_fetch_repos()`**: Validar cada repo y filtrar:
- `entries = [_GitHubRepoEntry.model_validate(r) for r in response.json()]`
- Filtrar forks: `if not entry.fork`
- Mapear a `GitHubRawRepo` con campos tipados

### 2. mappers.py — Anotaciones explícitas

El archivo trabaja con datos JSONB de SQLAlchemy que Pyright infiere como `dict[Unknown, Unknown]`. La solución usa anotaciones explícitas sin Pydantic (overhead innecesario para datos internos).

#### Cambios en `_parse_raw_repos`

```python
def _parse_raw_repos(raw: list[dict[str, Any]] | None) -> list[GitHubRawRepo]:
    if not raw:
        return []
    result: list[GitHubRawRepo] = []
    for item in raw:
        result.append(GitHubRawRepo(
            name=item.get("name", "") or "",
            language=item.get("language"),
            topics=list(item.get("topics") or []),
            stargazers_count=int(item.get("stargazers_count") or 0),
        ))
    return result
```

**Cambios clave**:
- Parámetro anotado como `list[dict[str, Any]] | None` en lugar de `dict | list | None`
- Variable `result` anotada explícitamente como `list[GitHubRawRepo]`
- Protección contra None en `item.get()` con operador `or`

#### Cambios en `_serialize_raw_repos`

```python
def _serialize_raw_repos(repos: tuple[GitHubRawRepo, ...] | list[GitHubRawRepo]) -> list[dict[str, Any]]:
    return [
        {
            "name": r.name,
            "language": r.language,
            "topics": list(r.topics),
            "stargazers_count": r.stargazers_count,
        }
        for r in repos
    ]
```

**Cambios clave**:
- Tipo de retorno anotado como `list[dict[str, Any]]`
- Parámetro acepta tuple o list para flexibilidad

#### Cambios en `orm_to_github_identity`

```python
from typing import cast

raw_repos=tuple(_parse_raw_repos(cast(list[dict[str, Any]] | None, row.raw_repos))),
```

**Razón del cast**: SQLAlchemy JSONB no tiene type hints precisos. El cast informa a Pyright del tipo esperado sin afectar runtime.

### 3. encryption.py — Tipos de SQLAlchemy

El TypeDecorator tiene parámetros `dialect` sin tipo, causando warnings. La solución importa `Dialect` de SQLAlchemy.

```python
from sqlalchemy.engine import Dialect

def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
    # ... implementación existente

def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
    # ... implementación existente
```

**Cambios**:
- Agregar import: `from sqlalchemy.engine import Dialect`
- Anotar parámetro `dialect` en ambos métodos

### 4. router.py — JWT payload tipado

El método `decode()` del token issuer retorna `dict[Unknown, Unknown]` porque `python-jose` no exporta tipos. La solución define un TypedDict local.

#### Definición de `JWTPayload`

El TypedDict ya existe en el archivo pero no se está usando correctamente:

```python
class JWTPayload(TypedDict):
    sub:  str        # UUID del usuario como string
    role: str        # valor del UserRole enum
    iat:  int        # issued at (epoch)
    exp:  int        # expiry (epoch)
```

#### Cambios en `get_me()`

```python
case Ok(value=payload):
    jwt_payload = cast(JWTPayload, payload)
    
    uow = container.new_uow()
    with uow:
        user_opt = uow.users.find_by_id(uuid.UUID(jwt_payload["sub"]))
```

**Cambios clave**:
- Usar `cast(JWTPayload, payload)` para informar a Pyright del tipo
- Acceder a `jwt_payload["sub"]` sin necesidad de `# type: ignore`
- El TypedDict documenta la estructura esperada del JWT

**Nota**: Ya existe un cast en el código actual, solo asegurar que el pattern matching extraiga `payload` correctamente.

## Data Models

No se modifican los modelos de dominio. Todos los cambios son en la capa de infraestructura:

- **Modelos Pydantic**: Son privados al módulo adapter, no se exportan
- **TypedDict JWT**: Es privado al módulo router
- **Anotaciones en mappers**: No crean nuevos tipos, solo documentan los existentes

## Error Handling

### Validación Pydantic en adapter.py

Si GitHub devuelve JSON inválido, Pydantic lanzará `ValidationError`. Este error debe capturarse y convertirse en `GitHubApiError`:

```python
try:
    data = _GitHubTokenResponse.model_validate(response.json())
except ValidationError as exc:
    logger.error("GitHub devolvió JSON inválido: %s", exc)
    return Err(GitHubApiError(
        status_code=response.status_code,
        detail="Respuesta inválida de GitHub"
    ))
```

### Cast en mappers.py

El `cast()` es solo para el type checker, no afecta runtime. Si SQLAlchemy devuelve un tipo inesperado, el error ocurrirá en `_parse_raw_repos()` al intentar iterar sobre None o acceder a keys inexistentes.

### TypedDict en router.py

`JWTPayload` es solo documentación estática. Si el JWT tiene estructura incorrecta, el error ocurrirá en runtime al acceder a las keys. El código ya maneja esto con try/except en el decode.

## Testing Strategy

### Verificación de Pyright

Después de cada archivo modificado:

```bash
pyright app/auth/infrastructure/github/adapter.py
pyright app/auth/infrastructure/persistence/mappers.py
pyright app/auth/infrastructure/persistence/encryption.py
pyright app/auth/routes/router.py
```

Al final, verificar el módulo completo:

```bash
pyright app/auth/
```

**Criterio de éxito**: 0 warnings en los 4 archivos.

### Tests funcionales

Los tests existentes deben seguir pasando sin modificaciones:

```bash
pytest tests/auth/ -v
```

**Criterio de éxito**: Todos los tests verdes.

### Validación de modelos Pydantic

Los modelos Pydantic agregan validación en runtime. Considerar agregar tests unitarios para casos edge:

1. GitHub devuelve `access_token` null
2. GitHub devuelve email sin campo `verified`
3. GitHub devuelve repo sin campo `language`

Estos tests validarían que los defaults de Pydantic funcionan correctamente.

## Implementation Notes

### No usar Pydantic en mappers.py

El JSONB de `raw_repos` es datos internos controlados. Pydantic agregaría overhead de validación innecesario. Las anotaciones `dict[str, Any]` son suficientes.

### Prefijo `_` en modelos Pydantic

Los modelos en adapter.py son detalles de implementación. El prefijo `_` señala que no deben importarse desde otros módulos.

### Orden de implementación

Empezar por encryption.py (más simple, 2 líneas) construye confianza antes de abordar adapter.py (más extenso, requiere refactorización).

### Validación Pydantic vs TypedDict

- **Pydantic**: Usar en boundaries con datos externos (GitHub API)
- **TypedDict**: Usar para documentar estructuras internas conocidas (JWT payload)

La diferencia: Pydantic valida en runtime, TypedDict solo documenta para el type checker.

# Skill: Typing de Capa de Infraestructura — Auth

## Objetivo

Eliminar los 27 warnings de Pyright en 4 archivos de infraestructura sin
tocar el dominio. Cada archivo tiene una causa distinta; la fix es diferente
para cada uno.

## Archivos en Scope

```
app/auth/infrastructure/github/adapter.py         → Pydantic para JSON de GitHub API
app/auth/infrastructure/persistence/mappers.py    → dict[str, Any] + anotaciones explícitas
app/auth/infrastructure/persistence/encryption.py → Dialect de SQLAlchemy
app/auth/routes/router.py                         → JWTPayload TypedDict o Pydantic
```

---

## 1. `adapter.py` — Modelos Pydantic para JSON externo

### Por qué Pydantic aquí

El JSON de GitHub es entrada externa no confiable. Pydantic valida estructura
y tipos en el boundary. Los `dict[Unknown, Unknown]` desaparecen porque
Pydantic devuelve objetos con atributos tipados.

### Modelos a crear (al inicio del archivo, antes de la clase)

```python
from pydantic import BaseModel, Field

class _GitHubTokenResponse(BaseModel):
    """Respuesta de POST /login/oauth/access_token"""
    access_token: str | None = None
    error: str | None = None
    error_description: str | None = None


class _GitHubEmailEntry(BaseModel):
    """Entrada de GET /user/emails"""
    email: str
    primary: bool
    verified: bool


class _GitHubRepoEntry(BaseModel):
    """Entrada de GET /user/repos"""
    name: str
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    stargazers_count: int = 0
    fork: bool = False


class _GitHubProfileResponse(BaseModel):
    """Respuesta de GET /user"""
    id: int
    login: str
    name: str | None = None
    email: str | None = None
```

> Los prefijos `_` indican que son privados al módulo — no se exportan.

### Cambios en `exchange_code`

```python
# ANTES
data = response.json()
if "error" in data:
    description = data.get("error_description", data["error"])
token_value = data.get("access_token")

# DESPUÉS
data = _GitHubTokenResponse.model_validate(response.json())
if data.error:
    description = data.error_description or data.error
    return Err(GitHubCodeExchangeError(raw_response=description))
if not data.access_token:
    return Err(GitHubCodeExchangeError(
        raw_response="GitHub no devolvió access_token en la respuesta"
    ))
return Ok(GitHubToken.create(data.access_token))
```

### Cambios en `_get_json`

```python
# ANTES
async def _get_json(
    self, url: str, headers: dict[str, str]
) -> Result[dict[str, Any], GitHubApiError]:
    ...
    return Ok(response.json())

# DESPUÉS — eliminar _get_json o hacerla genérica con TypeVar
# Más simple: inlinear las llamadas tipadas directamente en fetch_user
```

### Cambios en `fetch_user`

```python
async def fetch_user(
    self, token: GitHubToken
) -> Result[GitHubUserPayload, GitHubApiError]:
    auth_headers = {**_GITHUB_HEADERS, "Authorization": f"Bearer {token.value}"}

    # 1. Perfil
    try:
        resp = await self._http.get(f"{_API_BASE}/user", headers=auth_headers, timeout=10.0)
        resp.raise_for_status()
        profile = _GitHubProfileResponse.model_validate(resp.json())
    except httpx.HTTPStatusError as exc:
        return Err(GitHubApiError(
            status_code=exc.response.status_code,
            detail=_extract_github_message(exc.response),
        ))
    except httpx.RequestError as exc:
        return Err(GitHubApiError(status_code=0, detail=f"Error de red: {exc}"))

    email = profile.email or await self._fetch_primary_email(auth_headers)
    repos = await self._fetch_repos(auth_headers)

    return Ok(GitHubUserPayload(
        github_id=profile.id,
        login=profile.login,
        name=profile.name,
        email=email,
        repos=repos,
    ))
```

### Cambios en `_fetch_primary_email`

```python
async def _fetch_primary_email(self, headers: dict[str, str]) -> str | None:
    try:
        response = await self._http.get(
            f"{_API_BASE}/user/emails", headers=headers, timeout=10.0
        )
        if response.status_code != 200:
            return None
        entries = [_GitHubEmailEntry.model_validate(e) for e in response.json()]
        for entry in entries:
            if entry.primary and entry.verified:
                return entry.email
        for entry in entries:
            if entry.primary:
                return entry.email
        return None
    except httpx.RequestError:
        return None
```

### Cambios en `_fetch_repos`

```python
async def _fetch_repos(self, headers: dict[str, str]) -> list[GitHubRawRepo]:
    try:
        response = await self._http.get(
            f"{_API_BASE}/user/repos",
            headers=headers,
            params={"type": "owner", "sort": "pushed", "per_page": "100"},
            timeout=15.0,
        )
        if response.status_code != 200:
            return []
        entries = [_GitHubRepoEntry.model_validate(r) for r in response.json()]
        return [
            GitHubRawRepo(
                name=entry.name,
                language=entry.language,
                topics=entry.topics,
                stargazers_count=entry.stargazers_count,
            )
            for entry in entries
            if not entry.fork
        ]
    except httpx.RequestError as exc:
        logger.warning("Error de red obteniendo repos: %s", exc)
        return []
```

---

## 2. `mappers.py` — `dict[str, Any]` explícito

### Causa

`raw_repos` es `JSONB` de SQLAlchemy → Pyright lo infiere como
`dict[Unknown, Unknown]`. No necesita Pydantic — solo anotaciones explícitas.

```python
# Añadir al inicio del archivo
from typing import Any

# ANTES
def _parse_raw_repos(raw: dict | list | None) -> list[GitHubRawRepo]:
    items = raw if isinstance(raw, list) else []
    for item in items:
        result.append(GitHubRawRepo(
            name=item.get("name", ""),
            ...
        ))

# DESPUÉS
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

### Anotar `raw_repos` en `orm_to_github_identity`

```python
# ANTES
raw_repos=tuple(_parse_raw_repos(row.raw_repos)),

# DESPUÉS — cast explícito para que Pyright entienda el tipo del JSONB
from typing import cast

raw_repos=tuple(_parse_raw_repos(cast(list[dict[str, Any]] | None, row.raw_repos))),
```

---

## 3. `encryption.py` — Dialect de SQLAlchemy

### Causa

`dialect` no tiene anotación de tipo.

```python
# ANTES
from sqlalchemy import String, TypeDecorator

def process_bind_param(self, value: str | None, dialect) -> str | None:
def process_result_value(self, value: str | None, dialect) -> str | None:

# DESPUÉS
from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine import Dialect

def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
```

Un solo import, dos líneas cambiadas.

---

## 4. `router.py` — JWT payload tipado

### Causa

`decode()` devuelve `Ok[dict[Unknown, Unknown]]` porque `python-jose`
no exporta tipos. Crear un `TypedDict` local que coincida con la estructura
del payload emitido en `token_issuer.py`.

```python
# Añadir en router.py, después de los imports
from typing import TypedDict

class _JWTPayload(TypedDict):
    sub:  str        # UUID del usuario como string
    role: str        # valor del UserRole enum
    iat:  int        # issued at (epoch)
    exp:  int        # expiry (epoch)
```

### Cambio en `get_me`

```python
# ANTES
case Ok(value=payload):
    pass
...
user_opt = uow.users.find_by_id(uuid.UUID(payload["sub"]))  # type: ignore[possibly-undefined]

# DESPUÉS
case Ok(value=raw_payload):
    payload = _JWTPayload(**raw_payload)   # valida estructura en runtime
...
user_opt = uow.users.find_by_id(uuid.UUID(payload["sub"]))  # sin type: ignore
```

> Si prefieres Pydantic sobre TypedDict para validación runtime más robusta:
>
> ```python
> from pydantic import BaseModel
>
> class _JWTPayload(BaseModel):
>     sub:  str
>     role: str
>     iat:  int
>     exp:  int
>
> # uso:
> payload = _JWTPayload.model_validate(raw_payload)
> user_opt = uow.users.find_by_id(uuid.UUID(payload.sub))
> ```

---

## Proceso de Implementación

Implementar en este orden — cada paso debe dejar Pyright sin nuevos errores:

```
1. encryption.py   → más simple, 2 líneas, sin riesgo
2. mappers.py      → dict[str, Any] + cast
3. router.py       → _JWTPayload TypedDict/Pydantic
4. adapter.py      → modelos Pydantic, el más extenso
```

### Verificación por paso

```bash
# Después de cada archivo:
pyright app/auth/<archivo>.py

# Al final — debe ser 0 warnings en los 4 archivos:
pyright app/auth/

# Tests siguen verdes:
pytest tests/auth/ -v
```

---

## Definition of Done

- [ ] `pyright app/auth/` → 0 warnings en los 4 archivos modificados
- [ ] Sin `# type: ignore` nuevos introducidos
- [ ] `pytest tests/auth/ -v` verde
- [ ] `_GitHubTokenResponse`, `_GitHubEmailEntry`, `_GitHubRepoEntry`, `_GitHubProfileResponse` existen en `adapter.py`
- [ ] `_parse_raw_repos` anotada como `list[dict[str, Any]] | None`
- [ ] `process_bind_param` y `process_result_value` reciben `dialect: Dialect`
- [ ] `_JWTPayload` definido en `router.py`, sin `type: ignore[possibly-undefined]`

## Anti-patrones a Evitar

| Anti-patrón | Corrección |
|-------------|------------|
| Meter modelos Pydantic en `domain/` | Solo en `infrastructure/` y `routes/` |
| Usar `Any` para "silenciar" el warning | Anotar con el tipo real |
| `cast(Any, x)` para todo | `cast` solo donde SQLAlchemy obliga |
| Pydantic en `mappers.py` | `dict[str, Any]` es suficiente — es infra interna |

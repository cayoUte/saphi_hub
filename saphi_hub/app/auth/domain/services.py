"""
auth/domain/services.py
=======================
Servicios de dominio puros — sin I/O, sin efectos secundarios.

Cada función es determinista dado el mismo input, por lo tanto
es trivialmente testeable sin mocks.
"""

from __future__ import annotations

from collections.abc import Sequence

from auth.domain.entities import Skill
from auth.domain.value_objects import GitHubRawRepo, UserSlug
from shared.result import Err, Ok, Result
from auth.domain.errors import InvalidSlugError


# ---------------------------------------------------------------------------
# Extracción de skills desde repositorios de GitHub
# ---------------------------------------------------------------------------

# Lenguajes → categoría canónica
_LANGUAGE_CATEGORY = "language"
_TOPIC_CATEGORY    = "topic"

# Topics que mapeamos a categoría "framework" explícitamente
_FRAMEWORK_TOPICS: frozenset[str] = frozenset({
    "fastapi", "django", "flask", "react", "nextjs", "vue", "angular",
    "spring", "rails", "laravel", "express", "nestjs", "sqlalchemy",
    "pytorch", "tensorflow", "scikit-learn",
})


def extract_skills_from_repos(repos: Sequence[GitHubRawRepo]) -> list[Skill]:
    """
    Extrae skills ponderadas a partir de los repositorios de GitHub.

    Algoritmo:
      - Cada lenguaje suma +10 de peso por repo en que aparece.
      - Cada topic suma +5 de peso por repo en que aparece.
      - El peso se normaliza a [1, 100].
      - Solo se incluyen skills con peso mínimo de 5 (al menos 1 aparición).

    Returns una lista ordenada de mayor a menor peso.
    """
    raw_weights: dict[tuple[str, str], int] = {}   # (name, category) → peso acumulado

    for repo in repos:
        if repo.language:
            key = (repo.language.lower(), _LANGUAGE_CATEGORY)
            raw_weights[key] = raw_weights.get(key, 0) + 10

        for topic in repo.topics:
            normalized = topic.lower().strip()
            category = "framework" if normalized in _FRAMEWORK_TOPICS else _TOPIC_CATEGORY
            key = (normalized, category)
            raw_weights[key] = raw_weights.get(key, 0) + 5

    if not raw_weights:
        return []

    max_weight = max(raw_weights.values())

    skills: list[Skill] = []
    for (name, category), raw in raw_weights.items():
        normalized_weight = max(1, min(100, round((raw / max_weight) * 100)))
        if normalized_weight >= 5:
            skills.append(Skill(name=name, category=category, weight=normalized_weight))

    return sorted(skills, key=lambda s: s.weight, reverse=True)


# ---------------------------------------------------------------------------
# Generación de slug único
# ---------------------------------------------------------------------------

def generate_unique_slug(
    display_name: str,
    existing_slugs: frozenset[str],
    max_attempts: int = 10,
) -> Result[UserSlug, InvalidSlugError]:
    """
    Genera un UserSlug único dado un conjunto de slugs ya existentes.

    Intenta primero sin sufijo, luego con -2, -3, … hasta max_attempts.

    Args:
        display_name:   Nombre del usuario (ej. "María Ruiz").
        existing_slugs: Conjunto de slugs ya ocupados en el sistema.
        max_attempts:   Límite de intentos antes de devolver Err.

    Returns:
        Ok(UserSlug) si se encontró un slug disponible.
        Err(InvalidSlugError) si se agotaron los intentos.
    """
    for attempt in range(max_attempts):
        suffix = 0 if attempt == 0 else attempt + 1
        result = UserSlug.from_display_name(display_name, suffix=suffix)

        match result:
            case Ok(value=slug) if slug.value not in existing_slugs:
                return Ok(slug)
            case Err() as e:
                return e   # fallo de formato, sin sentido reintentar

    return Err(InvalidSlugError(attempted=display_name))


__all__: list[str] = [
    "extract_skills_from_repos",
    "generate_unique_slug",
]
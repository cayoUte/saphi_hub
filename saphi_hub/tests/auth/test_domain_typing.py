"""
tests/auth/test_domain_typing.py
================================
Tests de integridad de tipos en la capa de dominio (auth-pydantic-typing).

Verifica que el dominio no depende de Pydantic y que los DTOs no están duplicados.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "app" / "auth" / "domain"
DOMAIN_MODULES = ("entities.py", "value_objects.py", "services.py", "repositories.py", "errors.py")


def _collect_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


class TestDomainPurity:

    @pytest.mark.parametrize("module", DOMAIN_MODULES)
    def test_domain_module__does_not_import_pydantic(self, module: str):
        source = (DOMAIN_DIR / module).read_text(encoding="utf-8")
        imports = _collect_imports(source)
        pydantic_imports = {name for name in imports if "pydantic" in name}
        assert pydantic_imports == set(), f"{module} importa Pydantic: {pydantic_imports}"


class TestGitHubUserPayloadCanonical:

    def test_github_user_payload__single_definition(self):
        from auth.domain import entities, value_objects

        assert entities.GitHubUserPayload is value_objects.GitHubUserPayload

    def test_entities__does_not_redefine_github_user_payload(self):
        source = (DOMAIN_DIR / "entities.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        class_defs = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "GitHubUserPayload"
        ]
        assert class_defs == [], "GitHubUserPayload no debe redefinirse en entities.py"

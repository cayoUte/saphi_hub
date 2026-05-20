"""
tests/auth/test_github_login.py
================================
Tests del caso de uso US-01: login con GitHub.

Estrategia:
  - Tests unitarios puros — sin DB, sin HTTP, sin filesystem.
  - FakeUnitOfWork + FakeGitHubOAuthAdapter como dobles.
  - asyncio.run() para ejecutar coroutines sin plugin extra.
  - Un test = un comportamiento observable = una sola razón de falla.

Nomenclatura:
  test_<escenario>__<resultado_esperado>
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.auth.models import user
from auth.domain.errors import (
    GitHubApiError,
    GitHubCodeExchangeError,
    GithubProfilePersistenceError,
    UserPersistenceError,
)
from auth.domain.value_objects import GitHubCode, GitHubRawRepo
from auth.infrastructure.github.fake_adapter import FakeGitHubOAuthAdapter
from auth.infrastructure.persistence.fake_unit_of_work import FakeUnitOfWork
from shared.result import Err, Ok
from tests.auth.conftest import (
    FAKE_TOKEN_VALUE,
    MIXED_REPOS,
    PYTHON_REPOS,
    build_use_case,
)

# Código OAuth genérico para todos los tests
CODE = GitHubCode(value="github-oauth-code-xyz")


# ===========================================================================
# Helpers
# ===========================================================================

def run(github: FakeGitHubOAuthAdapter, uow: FakeUnitOfWork):
    """Ejecuta el caso de uso de forma síncrona. Reduce boilerplate en tests."""
    execute= build_use_case(github, uow)
    return asyncio.run(execute(CODE))


# ===========================================================================
# 1. CAMINO FELIZ — usuario nuevo
# ===========================================================================

class TestNewUserCreation:

    def test_happy_path__returns_ok(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(), FakeUnitOfWork())
        assert isinstance(result, Ok)

    def test_happy_path__is_new_user_true(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(), FakeUnitOfWork())
        assert result.unwrap().is_new_user is True

    def test_happy_path__user_stored_in_repo(self):
        uow = FakeUnitOfWork()
        result = run(FakeGitHubOAuthAdapter.happy_path(), uow)
        user = result.unwrap().user
        assert uow.users._store.get(user.id) is not None

    def test_happy_path__email_matches_github(self):
        github = FakeGitHubOAuthAdapter.happy_path(email="maria@epn.edu.ec")
        result = run(github, FakeUnitOfWork())
        assert result.unwrap().user.email.value == "maria@epn.edu.ec"

    def test_happy_path__display_name_matches_github(self):
        github = FakeGitHubOAuthAdapter.happy_path(name="María Ruiz")
        result = run(github, FakeUnitOfWork())
        assert result.unwrap().user.display_name == "María Ruiz"

    def test_happy_path__slug_derived_from_name(self):
        github = FakeGitHubOAuthAdapter.happy_path(name="María Ruiz")
        result = run(github, FakeUnitOfWork())
        slug = result.unwrap().user.slug.value
        # slug debe ser URL-safe y contener parte del nombre normalizado
        assert "maria" in slug
        assert " " not in slug

    def test_happy_path__user_role_is_student(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(), FakeUnitOfWork())
        assert result.unwrap().user.role.value == "student"

    def test_happy_path__user_is_active(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(), FakeUnitOfWork())
        assert result.unwrap().user.is_active is True

    def test_happy_path__jwt_is_returned(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(), FakeUnitOfWork())
        assert result.unwrap().access_token.value == FAKE_TOKEN_VALUE

    def test_happy_path__jwt_expires_in_is_set(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(), FakeUnitOfWork())
        assert result.unwrap().access_token.expires_in > 0


# ===========================================================================
# 2. GITHUB IDENTITY VINCULADA
# ===========================================================================

class TestGithubIdentityLinking:

    def test_identity_stored_in_profile_repo(self):
        uow    = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter.happy_path(github_id=42001)
        run(github, uow)
        assert 42001 in uow.github_profiles._store

    def test_identity_user_id_matches_created_user(self):
        uow    = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter.happy_path(github_id=42002)
        result = run(github, uow)
        user     = result.unwrap().user
        identity = uow.github_profiles._store[42002]
        assert identity.user_id == user.id

    def test_identity_github_login_matches_payload(self):
        uow    = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter.happy_path(github_id=42003, login="dev_user")
        run(github, uow)
        identity = uow.github_profiles._store[42003]
        assert identity.github_login == "dev_user"

    def test_user_has_github_identity_after_login(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(github_id=42004), FakeUnitOfWork())
        assert result.unwrap().user.github_identity is not None

    def test_user_github_identity_id_matches_stored(self):
        uow    = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter.happy_path(github_id=42005)
        result = run(github, uow)
        user     = result.unwrap().user
        stored   = uow.github_profiles._store[42005]
        assert user.github_identity.id == stored.id


# ===========================================================================
# 3. USUARIO EXISTENTE — reautenticación
# ===========================================================================

class TestReturningUser:

    def _seed_user(self, uow: FakeUnitOfWork, github_id: int) -> None:
        """Primera autenticación para poblar repos y usuario."""
        github = FakeGitHubOAuthAdapter.happy_path(github_id=github_id)
        run(github, uow)

    def test_second_login__is_new_user_false(self):
        uow = FakeUnitOfWork()
        self._seed_user(uow, github_id=55001)
        github = FakeGitHubOAuthAdapter.happy_path(github_id=55001)
        result = run(github, uow)
        assert result.unwrap().is_new_user is False

    def test_second_login__same_user_id(self):
        uow = FakeUnitOfWork()
        self._seed_user(uow, github_id=55002)
        first_user_id = next(iter(uow.users._store)).hex

        github = FakeGitHubOAuthAdapter.happy_path(github_id=55002)
        result = run(github, uow)
        assert result.unwrap().user.id.hex == first_user_id

    def test_second_login__only_one_user_in_store(self):
        uow = FakeUnitOfWork()
        self._seed_user(uow, github_id=55003)
        github = FakeGitHubOAuthAdapter.happy_path(github_id=55003)
        run(github, uow)
        assert len(uow.users._store) == 1

    def test_existing_email_user__found_by_email(self):
        """
        Simula usuario que existía antes de conectar GitHub.
        FakeUserRepository.find_by_github_id siempre devuelve Nothing(),
        así que el lookup cae al email — que sí existe.
        """
        uow = FakeUnitOfWork()
        # Primera autenticación — crea el usuario con email
        github_first = FakeGitHubOAuthAdapter.happy_path(
            github_id=55010, email="conocido@epn.edu.ec"
        )
        run(github_first, uow)

        # Segunda autenticación con mismo email pero DIFERENTE github_id
        # (simula que antes no tenía GitHub vinculado)
        github_second = FakeGitHubOAuthAdapter.happy_path(
            github_id=55011, email="conocido@epn.edu.ec"
        )
        result = run(github_second, uow)
        assert result.unwrap().is_new_user is False
        assert len(uow.users._store) == 1


# ===========================================================================
# 4. EMAIL AUSENTE EN GITHUB
# ===========================================================================

class TestMissingEmail:

    def test_no_email__returns_ok(self):
        result = run(FakeGitHubOAuthAdapter.no_email(), FakeUnitOfWork())
        assert isinstance(result, Ok)

    def test_no_email__uses_noreply_address(self):
        result = run(FakeGitHubOAuthAdapter.no_email(), FakeUnitOfWork())
        email = result.unwrap().user.email.value
        assert "noreply.github.com" in email

    def test_no_email__login_included_in_noreply(self):
        result = run(FakeGitHubOAuthAdapter.no_email(), FakeUnitOfWork())
        email = result.unwrap().user.email.value
        # FakeGitHubOAuthAdapter.no_email usa login="anonimo_dev"
        assert "anonimo_dev" in email


# ===========================================================================
# 5. SKILLS EXTRAÍDAS DE REPOS
# ===========================================================================

class TestSkillExtraction:

    def test_python_repos__python_skill_present(self):
        github = FakeGitHubOAuthAdapter.happy_path(repos=PYTHON_REPOS)
        result = run(github, FakeUnitOfWork())
        skill_names = {s.name for s in result.unwrap().user.skills}
        assert "python" in skill_names

    def test_python_repos__fastapi_skill_present(self):
        github = FakeGitHubOAuthAdapter.happy_path(repos=PYTHON_REPOS)
        result = run(github, FakeUnitOfWork())
        skill_names = {s.name for s in result.unwrap().user.skills}
        assert "fastapi" in skill_names

    def test_skills_weight_in_valid_range(self):
        github = FakeGitHubOAuthAdapter.happy_path(repos=PYTHON_REPOS)
        result = run(github, FakeUnitOfWork())
        for skill in result.unwrap().user.skills:
            assert 1 <= skill.weight <= 100

    def test_mixed_repos__typescript_skill_present(self):
        github = FakeGitHubOAuthAdapter.happy_path(repos=MIXED_REPOS)
        result = run(github, FakeUnitOfWork())
        skill_names = {s.name for s in result.unwrap().user.skills}
        assert "typescript" in skill_names

    def test_no_repos__skills_empty(self):
        result = run(FakeGitHubOAuthAdapter.no_repos(), FakeUnitOfWork())
        assert result.unwrap().user.skills == ()

    def test_skills_stored_in_repo(self):
        uow    = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter.happy_path(repos=PYTHON_REPOS)
        result = run(github, uow)
        user_id = result.unwrap().user.id
        assert user_id in uow.users._skill_store
        assert len(uow.users._skill_store[user_id]) > 0

    def test_framework_topics_have_framework_category(self):
        github = FakeGitHubOAuthAdapter.happy_path(repos=PYTHON_REPOS)
        result = run(github, FakeUnitOfWork())
        framework_skills = [
            s for s in result.unwrap().user.skills
            if s.name == "fastapi"
        ]
        assert framework_skills
        assert framework_skills[0].category == "framework"

    def test_language_skills_have_language_category(self):
        github = FakeGitHubOAuthAdapter.happy_path(repos=PYTHON_REPOS)
        result = run(github, FakeUnitOfWork())
        language_skills = [
            s for s in result.unwrap().user.skills
            if s.name == "python"
        ]
        assert language_skills
        assert language_skills[0].category == "language"


# ===========================================================================
# 6. SLUG — generación y colisiones
# ===========================================================================

class TestSlugGeneration:

    def test_slug_is_url_safe(self):
        github = FakeGitHubOAuthAdapter.happy_path(name="María José Ruiz")
        result = run(github, FakeUnitOfWork())
        slug = result.unwrap().user.slug.value
        assert slug.replace("-", "").isalnum()

    def test_slug_has_no_accents(self):
        github = FakeGitHubOAuthAdapter.happy_path(name="Ángel López")
        result = run(github, FakeUnitOfWork())
        slug = result.unwrap().user.slug.value
        for char in "áéíóúñü":
            assert char not in slug

    def test_slug_collision__second_user_gets_suffix(self):
        uow = FakeUnitOfWork()

        # Primer usuario con ese nombre
        github_a = FakeGitHubOAuthAdapter.happy_path(
            github_id=70001, email="a@epn.edu.ec", name="Carlos Vera"
        )
        result_a = run(github_a, uow)
        slug_a = result_a.unwrap().user.slug.value

        # Segundo usuario con mismo nombre
        github_b = FakeGitHubOAuthAdapter.happy_path(
            github_id=70002, email="b@epn.edu.ec", name="Carlos Vera"
        )
        result_b = run(github_b, uow)
        slug_b = result_b.unwrap().user.slug.value

        assert slug_a != slug_b
        assert slug_b.startswith("carlos")

    def test_three_users_same_name__all_unique_slugs(self):
        uow    = FakeUnitOfWork()
        slugs  = []
        emails = ["u1@epn.edu.ec", "u2@epn.edu.ec", "u3@epn.edu.ec"]

        for i, email in enumerate(emails, start=80001):
            github = FakeGitHubOAuthAdapter.happy_path(
                github_id=i, email=email, name="Luis Torres"
            )
            result = run(github, uow)
            slugs.append(result.unwrap().user.slug.value)

        assert len(set(slugs)) == 3


# ===========================================================================
# 7. ERRORES DEL FLUJO OAUTH
# ===========================================================================

class TestOAuthErrors:

    def test_invalid_code__returns_err(self):
        result = run(FakeGitHubOAuthAdapter.invalid_code(), FakeUnitOfWork())
        assert isinstance(result, Err)

    def test_invalid_code__error_is_code_exchange_error(self):
        result = run(FakeGitHubOAuthAdapter.invalid_code(), FakeUnitOfWork())
        assert isinstance(result.error, GitHubCodeExchangeError)

    def test_invalid_code__no_user_created(self):
        uow = FakeUnitOfWork()
        run(FakeGitHubOAuthAdapter.invalid_code(), uow)
        assert len(uow.users._store) == 0

    def test_invalid_code__no_profile_stored(self):
        uow = FakeUnitOfWork()
        run(FakeGitHubOAuthAdapter.invalid_code(), uow)
        assert len(uow.github_profiles._store) == 0

    def test_api_down__returns_err(self):
        result = run(FakeGitHubOAuthAdapter.api_down(), FakeUnitOfWork())
        assert isinstance(result, Err)

    def test_api_down__error_is_api_error(self):
        result = run(FakeGitHubOAuthAdapter.api_down(), FakeUnitOfWork())
        assert isinstance(result.error, GitHubApiError)

    def test_api_down__status_code_preserved(self):
        result = run(FakeGitHubOAuthAdapter.api_down(), FakeUnitOfWork())
        assert result.error.status_code == 503

    def test_api_down__no_user_created(self):
        uow = FakeUnitOfWork()
        run(FakeGitHubOAuthAdapter.api_down(), uow)
        assert len(uow.users._store) == 0

    def test_invalid_code__code_was_sent_to_github(self):
        """Verifica que el adaptador recibió el código antes de fallar."""
        github = FakeGitHubOAuthAdapter.invalid_code()
        run(github, FakeUnitOfWork())
        assert CODE.value in github.codes_seen

    def test_api_down__token_was_sent_to_github(self):
        """Verifica que se intentó fetch_user con el token antes de fallar."""
        github = FakeGitHubOAuthAdapter.api_down()
        run(github, FakeUnitOfWork())
        assert "ghp_fake_token" in github.tokens_seen


# ===========================================================================
# 8. ERRORES DE PERSISTENCIA
# ===========================================================================

class TestPersistenceErrors:

    def test_user_save_fails__returns_err(self):
        uow    = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter.happy_path()

        # Inyectamos fallo en save
        def failing_save(user):
            from shared.result import Err
            return Err(UserPersistenceError(detail="DB connection lost"))

        uow.users.save = failing_save

        result = run(github, uow)
        assert isinstance(result, Err)
        assert isinstance(result.error, UserPersistenceError)

    def test_profile_save_fails__returns_err(self):
        uow    = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter.happy_path()

        def failing_save(identity):
            from shared.result import Err
            return Err(GithubProfilePersistenceError(detail="unique constraint"))

        uow.github_profiles.save = failing_save

        result = run(github, uow)
        assert isinstance(result, Err)
        assert isinstance(result.error, GithubProfilePersistenceError)

    def test_skill_save_fails__login_still_succeeds(self):
        """
        Si save_skills falla, el login no se interrumpe (best-effort).
        El usuario recibe las skills en memoria aunque no se hayan persistido.
        """
        uow    = FakeUnitOfWork()
        github = FakeGitHubOAuthAdapter.happy_path(repos=PYTHON_REPOS)

        def failing_save_skills(user_id, skills):
            from shared.result import Err
            return Err(UserPersistenceError(detail="skills table locked"))

        uow.users.save_skills = failing_save_skills

        result = run(github, uow)
        assert isinstance(result, Ok)
        # Las skills siguen presentes en el User en memoria
        assert len(result.unwrap().user.skills) > 0


# ===========================================================================
# 9. INVARIANTES DEL CASO DE USO
# ===========================================================================

class TestUseCaseInvariants:

    def test_code_is_consumed_exactly_once(self):
        github = FakeGitHubOAuthAdapter.happy_path()
        run(github, FakeUnitOfWork())
        assert github.codes_seen.count(CODE.value) == 1

    def test_token_is_used_exactly_once(self):
        github = FakeGitHubOAuthAdapter.happy_path()
        run(github, FakeUnitOfWork())
        assert len(github.tokens_seen) == 1

    def test_user_entity_is_immutable_after_creation(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(), FakeUnitOfWork())
        user = result.unwrap().user
        with pytest.raises(Exception):
            user.display_name = "mutado"

    
    def test_output_is_immutable(self):
        result = run(FakeGitHubOAuthAdapter.happy_path(), FakeUnitOfWork())
        output = result.unwrap()
        with pytest.raises(Exception):
            output.is_new_user = False 

    def test_two_independent_executions_produce_different_user_ids(self):
        """Cada ejecución crea un usuario con UUID distinto."""
        uow_a = FakeUnitOfWork()
        uow_b = FakeUnitOfWork()

        github_a = FakeGitHubOAuthAdapter.happy_path(
            github_id=90001, email="a@epn.edu.ec"
        )
        github_b = FakeGitHubOAuthAdapter.happy_path(
            github_id=90002, email="b@epn.edu.ec"
        )

        id_a = run(github_a, uow_a).unwrap().user.id
        id_b = run(github_b, uow_b).unwrap().user.id
        assert id_a != id_b
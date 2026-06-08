"""
tests/auth/test_schemas.py
==========================
Tests de tipado y serialización de los schemas Pydantic del módulo auth.

Estrategia (TDD — auth-pydantic-typing):
  - Verificar anotaciones de campo (Literal, UserRole, EmailStr, HttpUrl).
  - Verificar validación en runtime (rechaza valores inválidos).
  - Verificar mapeo desde entidades de dominio via from_domain / from_output.
  - Verificar contrato JSON de la API (model_dump para respuestas HTTP).

Nomenclatura:
  test_<escenario>__<resultado_esperado>
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, get_args, get_origin

import pytest
from pydantic import EmailStr, HttpUrl, ValidationError

from auth.application.use_cases.github_login import GitHubLoginOutput
from auth.domain.entities import Skill, User, UserRole, create_user
from auth.domain.value_objects import Email, UserSlug
from auth.routes import schemas
from auth.routes.schemas import (
    APIErrorResponse,
    CurrentUserResponse,
    GitHubLoginResponse,
    RedirectURLResponse,
    SkillCategory,
    SkillOut,
    TokenType,
    UserOut,
)
from tests.auth.conftest import FAKE_EXPIRES_IN, FAKE_TOKEN_VALUE


# ===========================================================================
# 1. ANOTACIONES DE TIPO — contrato estático del módulo
# ===========================================================================

class TestFieldAnnotations:

    def test_skill_out__category_is_literal(self):
        annotation = SkillOut.model_fields["category"].annotation
        assert get_origin(annotation) is Literal
        assert set(get_args(annotation)) == {"language", "topic", "framework", "other"}

    def test_user_out__role_is_user_role(self):
        assert UserOut.model_fields["role"].annotation is UserRole

    def test_user_out__email_is_email_str(self):
        assert UserOut.model_fields["email"].annotation is EmailStr

    def test_github_login_response__token_type_is_literal_bearer(self):
        annotation = GitHubLoginResponse.model_fields["token_type"].annotation
        assert get_origin(annotation) is Literal
        assert get_args(annotation) == ("bearer",)

    def test_redirect_url_response__url_is_http_url(self):
        assert RedirectURLResponse.model_fields["url"].annotation is HttpUrl


# ===========================================================================
# 2. SkillOut — validación y mapeo
# ===========================================================================

class TestSkillOut:

    def test_valid_skill__accepted(self):
        skill = SkillOut(name="fastapi", category="framework", weight=50)
        assert skill.name == "fastapi"
        assert skill.category == "framework"
        assert skill.weight == 50

    def test_category_other__accepted(self):
        skill = SkillOut(name="misc", category="other", weight=10)
        assert skill.category == "other"

    def test_invalid_category__raises_validation_error(self):
        with pytest.raises(ValidationError):
            SkillOut(name="python", category="database", weight=50)  # type: ignore[arg-type]

    def test_weight_below_min__raises_validation_error(self):
        with pytest.raises(ValidationError):
            SkillOut(name="python", category="language", weight=0)

    def test_weight_above_max__raises_validation_error(self):
        with pytest.raises(ValidationError):
            SkillOut(name="python", category="language", weight=101)

    def test_from_domain__maps_all_fields(self, sample_skill: Skill):
        out = SkillOut.from_domain(sample_skill)
        assert out.name == sample_skill.name
        assert out.category == sample_skill.category
        assert out.weight == sample_skill.weight

    def test_from_domain__category_is_typed_literal(self, sample_skill: Skill):
        out = SkillOut.from_domain(sample_skill)
        assert out.category in ("language", "topic", "framework", "other")


# ===========================================================================
# 3. UserOut — validación y mapeo
# ===========================================================================

class TestUserOut:

    def test_valid_user__accepted(self):
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        out = UserOut(
            id=user_id,
            role=UserRole.student,
            email="dev@epn.edu.ec",
            display_name="Dev User",
            slug="dev-user",
            is_active=True,
            created_at=now,
        )
        assert out.role is UserRole.student

    def test_invalid_email__raises_validation_error(self):
        with pytest.raises(ValidationError):
            UserOut(
                id=uuid.uuid4(),
                role=UserRole.student,
                email="not-an-email",
                display_name="Dev User",
                slug="dev-user",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )

    def test_invalid_role__raises_validation_error(self):
        with pytest.raises(ValidationError):
            UserOut(
                id=uuid.uuid4(),
                role="superadmin",  # type: ignore[arg-type]
                email="dev@epn.edu.ec",
                display_name="Dev User",
                slug="dev-user",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )

    def test_from_domain__unwraps_value_objects(self, sample_user: User):
        out = UserOut.from_domain(sample_user)
        assert out.id == sample_user.id
        assert out.role is sample_user.role
        assert out.email == sample_user.email.value
        assert out.display_name == sample_user.display_name
        assert out.slug == sample_user.slug.value
        assert out.is_active == sample_user.is_active
        assert out.created_at == sample_user.created_at

    def test_from_domain__serializes_role_as_string(self, sample_user: User):
        dumped = UserOut.from_domain(sample_user).model_dump(mode="json")
        assert dumped["role"] == "student"
        assert isinstance(dumped["role"], str)


# ===========================================================================
# 4. GitHubLoginResponse — respuesta OAuth
# ===========================================================================

class TestGitHubLoginResponse:

    def test_default_token_type__is_bearer(self, sample_user: User):
        response = GitHubLoginResponse(
            access_token=FAKE_TOKEN_VALUE,
            expires_in=FAKE_EXPIRES_IN,
            is_new_user=True,
            user=UserOut.from_domain(sample_user),
            skills=[SkillOut.from_domain(s) for s in sample_user.skills],
        )
        assert response.token_type == "bearer"

    def test_invalid_token_type__raises_validation_error(self, sample_user: User):
        with pytest.raises(ValidationError):
            GitHubLoginResponse(
                access_token=FAKE_TOKEN_VALUE,
                token_type="basic",  # type: ignore[arg-type]
                expires_in=FAKE_EXPIRES_IN,
                is_new_user=True,
                user=UserOut.from_domain(sample_user),
                skills=[],
            )

    def test_from_output__maps_login_result(self, sample_login_output: GitHubLoginOutput):
        response = GitHubLoginResponse.from_output(sample_login_output)
        assert response.access_token == FAKE_TOKEN_VALUE
        assert response.expires_in == FAKE_EXPIRES_IN
        assert response.is_new_user is True
        assert response.user.email == sample_login_output.user.email.value
        assert len(response.skills) == len(sample_login_output.user.skills)

    def test_from_output__skills_are_skill_out_instances(
        self, sample_login_output: GitHubLoginOutput
    ):
        response = GitHubLoginResponse.from_output(sample_login_output)
        assert all(isinstance(s, SkillOut) for s in response.skills)


# ===========================================================================
# 5. CurrentUserResponse
# ===========================================================================

class TestCurrentUserResponse:

    def test_from_user__maps_user_and_skills(self, sample_user: User):
        response = CurrentUserResponse.from_user(sample_user)
        assert response.user.id == sample_user.id
        assert response.user.email == sample_user.email.value
        assert len(response.skills) == len(sample_user.skills)
        assert all(isinstance(s, SkillOut) for s in response.skills)


# ===========================================================================
# 6. RedirectURLResponse — HttpUrl
# ===========================================================================

class TestRedirectURLResponse:

    def test_valid_https_url__accepted(self):
        response = RedirectURLResponse(
            url="https://github.com/login/oauth/authorize?client_id=abc"
        )
        assert str(response.url).startswith("https://")

    def test_invalid_url__raises_validation_error(self):
        with pytest.raises(ValidationError):
            RedirectURLResponse(url="not-a-url")


# ===========================================================================
# 7. APIErrorResponse
# ===========================================================================

class TestAPIErrorResponse:

    def test_error_response__fields_required(self):
        err = APIErrorResponse(code="GITHUB_API_ERROR", message="Service unavailable")
        assert err.code == "GITHUB_API_ERROR"
        assert err.message == "Service unavailable"

    def test_error_response__missing_field_raises(self):
        with pytest.raises(ValidationError):
            APIErrorResponse(code="ONLY_CODE")  # type: ignore[call-arg]


# ===========================================================================
# 8. ALIAS DE TIPO Y EXPORTACIONES DEL MÓDULO
# ===========================================================================

class TestModuleExports:

    def test_skill_category_alias__matches_domain_categories(self):
        assert set(get_args(SkillCategory)) == {"language", "topic", "framework", "other"}

    def test_token_type_alias__is_bearer_only(self):
        assert get_args(TokenType) == ("bearer",)

    def test_all_exports__are_public(self):
        assert set(schemas.__all__) == {
            "SkillCategory",
            "TokenType",
            "SkillOut",
            "UserOut",
            "GitHubLoginResponse",
            "RedirectURLResponse",
            "APIErrorResponse",
            "CurrentUserResponse",
        }

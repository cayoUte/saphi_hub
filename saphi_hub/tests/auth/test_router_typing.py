"""
tests/auth/test_router_typing.py
================================
Tests de tipado estático del router HTTP (auth-pydantic-typing).
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

from auth.domain.entities import User
from auth.routes.router import JWTPayload


ROUTER_PATH = Path(__file__).resolve().parents[2] / "app" / "auth" / "routes" / "router.py"


class TestRouterSourceHygiene:

    def test_router__no_possibly_undefined_ignores(self):
        source = ROUTER_PATH.read_text(encoding="utf-8")
        assert "possibly-undefined" not in source


class TestJWTPayload:

    def test_jwt_payload__has_required_keys(self):
        hints = get_type_hints(JWTPayload)
        assert set(hints) == {"sub", "role", "exp", "iat"}

    def test_jwt_payload__sub_is_string(self):
        assert get_type_hints(JWTPayload)["sub"] is str


class TestRouterHelpers:

    def test_to_user_out__accepts_domain_user(self, sample_user: User):
        from auth.routes.router import _to_user_out

        hints = get_type_hints(_to_user_out)
        assert hints["user"] is User
        out = _to_user_out(sample_user)
        assert out.email == sample_user.email.value

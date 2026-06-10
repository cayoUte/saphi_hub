"""
auth/infrastructure/persistence/orm_models.py
=============================================
Modelos ORM de SQLAlchemy 2.0.

Regla cardinal: estos modelos NO son las entidades de dominio.
Son representaciones de tablas. El mapeo bidireccional ocurre en mappers.py.

Beneficio: el dominio nunca importa SQLAlchemy; la infra puede cambiar
(e.g., migrar a async o a otro ORM) sin tocar una línea de dominio.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import Enum as SAEnum, TIMESTAMP


# ---------------------------------------------------------------------------
# Base declarativa
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# UserORM
# ---------------------------------------------------------------------------

class UserORM(Base):
    __tablename__ = "users"

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role:         Mapped[str]       = mapped_column(SAEnum("student", "institution", "admin", "mentor", name="user_role"), nullable=False, default="student")
    email:        Mapped[str]       = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str]       = mapped_column(String, nullable=False)
    slug:         Mapped[str]       = mapped_column(String, nullable=False, unique=True)
    is_active:    Mapped[bool]      = mapped_column(Boolean, nullable=False, default=True)
    created_at:   Mapped[datetime]  = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]  = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relaciones (lazy="select" es el default; se carga solo cuando se accede)
    github_profile: Mapped[GithubProfileORM | None] = relationship(
        "GithubProfileORM",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    user_skills: Mapped[list[UserSkillORM]] = relationship(
        "UserSkillORM",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# GithubProfileORM
# ---------------------------------------------------------------------------

class GithubProfileORM(Base):
    __tablename__ = "github_profiles"

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    github_id:    Mapped[int]       = mapped_column(BigInteger, nullable=False, unique=True)
    github_login: Mapped[str]       = mapped_column(String, nullable=False)
    # access_token se persiste encriptado via EncryptedString TypeDecorator
    access_token: Mapped[str]       = mapped_column(Text, nullable=False)
    raw_repos:    Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    synced_at:    Mapped[datetime]  = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[UserORM] = relationship("UserORM", back_populates="github_profile")


# ---------------------------------------------------------------------------
# SkillORM
# ---------------------------------------------------------------------------

class SkillORM(Base):
    __tablename__ = "skills"

    id:       Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:     Mapped[str]       = mapped_column(String, nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String)

    user_skills: Mapped[list[UserSkillORM]] = relationship("UserSkillORM", back_populates="skill")


# ---------------------------------------------------------------------------
# UserSkillORM  (tabla puente users ↔ skills)
# ---------------------------------------------------------------------------

class UserSkillORM(Base):
    __tablename__ = "user_skills"
    __table_args__ = (
        CheckConstraint("weight BETWEEN 1 AND 100", name="chk_user_skill_weight"),
        UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),
    )

    user_id:  Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",  ondelete="CASCADE"),  primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"),  primary_key=True)
    source:   Mapped[str]       = mapped_column(String, nullable=False, default="github")
    weight:   Mapped[int]       = mapped_column(SmallInteger, nullable=False, default=1)

    user:  Mapped[UserORM]  = relationship("UserORM",  back_populates="user_skills")
    skill: Mapped[SkillORM] = relationship("SkillORM", back_populates="user_skills")


__all__: list[str] = [
    "Base",
    "UserORM",
    "GithubProfileORM",
    "SkillORM",
    "UserSkillORM",
]
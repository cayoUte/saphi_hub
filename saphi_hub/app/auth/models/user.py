import uuid
from sqlalchemy import Boolean, Column, Enum, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from shared.db.base import Base
import enum


class UserRole(str, enum.Enum):
    student     = "student"
    institution = "institution"
    admin       = "admin"
    mentor      = "mentor"


class User(Base):
    __tablename__ = "users"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role         = Column(Enum(UserRole), nullable=False, default=UserRole.student)
    email        = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    slug         = Column(String, unique=True, nullable=False)
    is_active    = Column(Boolean, nullable=False, default=True)
    created_at   = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))
    updated_at   = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()"))

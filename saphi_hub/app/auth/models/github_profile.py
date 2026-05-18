import uuid
from sqlalchemy import BigInteger, Column, ForeignKey, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.shared.db.base import Base


class GithubProfile(Base):
    __tablename__ = "github_profiles"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    github_id    = Column(BigInteger, unique=True, nullable=False)
    github_login = Column(String, nullable=False)
    access_token = Column(String, nullable=False)   # encriptar desde app antes de persistir
    raw_repos    = Column(JSONB)
    synced_at    = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))

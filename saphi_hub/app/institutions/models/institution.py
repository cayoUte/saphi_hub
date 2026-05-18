import uuid
from sqlalchemy import Column, Enum, ForeignKey, String, TIMESTAMP, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.shared.db.base import Base
import enum


class InstitutionStatus(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class Institution(Base):
    __tablename__ = "institutions"
    __table_args__ = (
        CheckConstraint("email_domain LIKE '%.edu.ec'", name="chk_email_domain_edu_ec"),
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    name          = Column(String, nullable=False)
    email_domain  = Column(String, nullable=False)
    country       = Column(String, nullable=False, default="Ecuador")
    status        = Column(Enum(InstitutionStatus), nullable=False, default=InstitutionStatus.pending)
    requested_at  = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))

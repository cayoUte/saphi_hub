import uuid
from sqlalchemy import Boolean, Column, ForeignKey, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.shared.db.base import Base


class InstitutionVerificationChecklist(Base):
    __tablename__ = "institution_verification_checklist"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id   = Column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    admin_user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    domain_verified  = Column(Boolean, nullable=False, default=False)
    legal_doc_ok     = Column(Boolean, nullable=False, default=False)
    contact_verified = Column(Boolean, nullable=False, default=False)
    created_at       = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))
    reviewed_at      = Column(TIMESTAMP(timezone=True))

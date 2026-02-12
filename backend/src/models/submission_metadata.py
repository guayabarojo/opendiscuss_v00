"""
SubmissionMetadata model for Input Collection Protocol.
Tracks metadata about submissions (persistent), while raw content is ephemeral.
"""

from sqlalchemy import Column, String, DateTime, Boolean, UUID as SQLUUID, Enum as SQLEnum
from sqlalchemy.sql import func
import uuid
import enum

from . import Base


class SubmissionModality(str, enum.Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"


class SubmissionMetadata(Base):
    __tablename__ = "submission_metadata"

    submission_id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    round_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modality = Column(SQLEnum(SubmissionModality), nullable=False)
    counted = Column(Boolean, nullable=False, default=False, index=True)

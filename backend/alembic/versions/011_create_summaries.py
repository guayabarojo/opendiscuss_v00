"""
Create summaries and correction_signals tables for Spec 003.

Revision ID: 011_create_summaries
Revises: 010_add_submission_indexes
Create Date: 2026-02-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# revision identifiers, used by Alembic.
revision = "011_create_summaries"
down_revision = "010_add_submission_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create summaries and correction_signals tables for Spec 003.

    Summaries table:
    - Stores LLM-generated summaries with approval status (FSM)
    - Tracks regeneration count (bounded retry: 0-3)
    - Records safety flags for content filtering
    - Indexes on (participant_id, round_id, status, approved_at)

    Correction_signals table:
    - Stores participant feedback after 2 rejections
    - Structured reason tags + optional freeform text
    - One-to-many with summaries
    """

    # Create summary status enum
    op.execute(
        """
        CREATE TYPE summarystatus AS ENUM (
            'pending_review',
            'approved',
            'rejected',
            'rejected_final',
            'disallowed_content',
            'approval_timeout',
            'superseded'
        )
        """
    )

    # Create reason tag enum
    op.execute(
        """
        CREATE TYPE reasontag AS ENUM (
            'wrong_crux',
            'too_vague',
            'misrepresents_me',
            'missed_constraint',
            'missed_solution',
            'other'
        )
        """
    )

    # Create summaries table
    op.create_table(
        "summaries",
        sa.Column("summary_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "submission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("submissions.submission_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "participant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("participants.participant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "round_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rounds.round_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary_text", sa.String(500), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending_review",
                "approved",
                "rejected",
                "rejected_final",
                "disallowed_content",
                "approval_timeout",
                "superseded",
                name="summarystatus",
            ),
            nullable=False,
            server_default="pending_review",
        ),
        sa.Column("regen_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safety_flags", ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for summaries table
    op.create_index(
        "ix_summaries_submission_id",
        "summaries",
        ["submission_id"],
    )
    op.create_index(
        "ix_summaries_participant_id",
        "summaries",
        ["participant_id"],
    )
    op.create_index(
        "ix_summaries_round_id",
        "summaries",
        ["round_id"],
    )
    op.create_index(
        "ix_summaries_status",
        "summaries",
        ["status"],
    )
    op.create_index(
        "ix_summaries_created_at",
        "summaries",
        ["created_at"],
    )
    op.create_index(
        "ix_summaries_approved_at",
        "summaries",
        ["approved_at"],
    )

    # Create composite index for last-approved-wins queries
    op.create_index(
        "ix_summaries_participant_round_approved",
        "summaries",
        ["participant_id", "round_id", "approved_at"],
    )

    # Create correction_signals table
    op.create_table(
        "correction_signals",
        sa.Column("signal_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "summary_id",
            UUID(as_uuid=True),
            sa.ForeignKey("summaries.summary_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reason_tag",
            sa.Enum(
                "wrong_crux",
                "too_vague",
                "misrepresents_me",
                "missed_constraint",
                "missed_solution",
                "other",
                name="reasontag",
            ),
            nullable=False,
        ),
        sa.Column("feedback_text", sa.String(240), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create index for correction_signals table
    op.create_index(
        "ix_correction_signals_summary_id",
        "correction_signals",
        ["summary_id"],
    )


def downgrade() -> None:
    """
    Drop summaries and correction_signals tables.
    """
    # Drop tables
    op.drop_table("correction_signals")
    op.drop_table("summaries")

    # Drop enums
    op.execute("DROP TYPE reasontag")
    op.execute("DROP TYPE summarystatus")

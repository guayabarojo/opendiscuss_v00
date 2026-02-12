"""add_question_generation_failed_status

Revision ID: 597c19d7db60
Revises: 008_add_question_indexes
Create Date: 2026-01-31 01:43:14.580698

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "597c19d7db60"
down_revision: Union[str, None] = "008_add_question_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add QUESTION_GENERATION_FAILED to round_status enum."""
    # Add new enum value to round_status
    op.execute("ALTER TYPE round_status ADD VALUE IF NOT EXISTS 'QUESTION_GENERATION_FAILED'")


def downgrade() -> None:
    """Remove QUESTION_GENERATION_FAILED from round_status enum."""
    # Note: PostgreSQL doesn't support removing enum values easily.
    # This downgrade would require recreating the enum type, which is complex.
    # For safety, we'll leave it as-is since having an extra enum value doesn't break anything.
    pass

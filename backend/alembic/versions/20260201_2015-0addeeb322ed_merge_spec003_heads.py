"""merge_spec003_heads

Revision ID: 0addeeb322ed
Revises: spec002_003, 011_create_summaries, 597c19d7db60
Create Date: 2026-02-01 20:15:54.980407

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0addeeb322ed"
down_revision: Union[str, None] = ("spec002_003", "011_create_summaries", "597c19d7db60")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass

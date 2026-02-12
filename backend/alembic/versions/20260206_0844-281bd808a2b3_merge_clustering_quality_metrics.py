"""merge clustering quality metrics

Revision ID: 281bd808a2b3
Revises: 016_add_clustering_quality_metrics, 0addeeb322ed
Create Date: 2026-02-06 08:44:10.750723

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "281bd808a2b3"
down_revision: Union[str, None] = ("016_add_clustering_quality_metrics", "0addeeb322ed")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass

"""create participants table

Revision ID: spec002_001
Revises:
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'spec002_001'
down_revision = None  # First migration
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('participants',
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

def downgrade():
    op.drop_table('participants')

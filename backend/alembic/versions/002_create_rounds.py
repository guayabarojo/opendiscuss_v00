"""create rounds table

Revision ID: spec002_002
Revises: spec002_001
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'spec002_002'
down_revision = 'spec002_001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('rounds',
        sa.Column('round_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('discussion_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('round_number', sa.Integer, nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
    )

def downgrade():
    op.drop_table('rounds')

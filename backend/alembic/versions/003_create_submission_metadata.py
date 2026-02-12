"""create submission_metadata table with EXCLUDE constraint

Revision ID: spec002_003
Revises: spec002_002
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'spec002_003'
down_revision = 'spec002_002'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('submission_metadata',
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('round_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('modality', sa.String(10), nullable=False),
        sa.Column('counted', sa.Boolean, nullable=False, server_default='false', index=True),
    )

    # EXCLUDE constraint: only one counted submission per (participant_id, round_id)
    op.execute("""
        ALTER TABLE submission_metadata
        ADD CONSTRAINT one_counted_submission_per_participant_round
        EXCLUDE USING btree (participant_id WITH =, round_id WITH =)
        WHERE (counted = true)
    """)

def downgrade():
    op.drop_table('submission_metadata')

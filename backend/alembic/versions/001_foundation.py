"""foundation

Revision ID: 001_foundation
Revises:
Create Date: 2026-01-29 14:00:00.000000

Foundation migration for OpenDiscuss Discussion Protocol.
Creates core infrastructure tables and indexes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_foundation'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create foundational schema for OpenDiscuss.

    Tables:
    - protocol_metadata: System state tracking
    - system_config: Configuration and settings tracking
    """

    # Create protocol_metadata table for tracking system state
    op.create_table(
        'protocol_metadata',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('value', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_protocol_metadata_key'),
        comment='System-wide protocol state and metadata tracking'
    )

    # Create index for common queries on protocol_metadata
    op.create_index(
        'ix_protocol_metadata_key',
        'protocol_metadata',
        ['key'],
        unique=True
    )

    # Create system_config table for settings and configuration tracking
    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('config_key', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('config_value', sa.JSON(), nullable=True),
        sa.Column('config_type', sa.String(50), nullable=False),  # 'string', 'integer', 'boolean', 'json'
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('config_key', name='uq_system_config_key'),
        comment='Application configuration and settings'
    )

    # Create index for active config queries
    op.create_index(
        'ix_system_config_active',
        'system_config',
        ['is_active', 'config_key']
    )

    # Create index for config type filtering
    op.create_index(
        'ix_system_config_type',
        'system_config',
        ['config_type']
    )

    # Insert initial protocol metadata
    op.execute(
        """
        INSERT INTO protocol_metadata (key, value, description)
        VALUES
            ('schema_version', '"001"', 'Current database schema version'),
            ('protocol_version', '"0.1.0"', 'OpenDiscuss protocol version'),
            ('initialized_at', 'to_json(CURRENT_TIMESTAMP)', 'System initialization timestamp')
        """
    )

    # Insert initial system configuration
    op.execute(
        """
        INSERT INTO system_config (config_key, config_value, config_type, description)
        VALUES
            ('timing_precision_ms', '100', 'integer', 'Maximum allowed timing drift in milliseconds'),
            ('max_submissions_per_round', '3', 'integer', 'Maximum submissions per participant per round'),
            ('submission_window_default_seconds', '300', 'integer', 'Default submission window duration (5 minutes)'),
            ('enable_approval_timeout', 'true', 'boolean', 'Enable automatic approval deadline timeout'),
            ('approval_timeout_minutes', '10', 'integer', 'Minutes before unapproved summaries timeout')
        """
    )


def downgrade() -> None:
    """
    Drop foundational schema tables.
    """
    # Drop indexes first
    op.drop_index('ix_system_config_type', table_name='system_config')
    op.drop_index('ix_system_config_active', table_name='system_config')
    op.drop_index('ix_protocol_metadata_key', table_name='protocol_metadata')

    # Drop tables
    op.drop_table('system_config')
    op.drop_table('protocol_metadata')

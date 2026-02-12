"""Add async timing mode support

Revision ID: 015_add_async_timing_mode
Revises: 014_add_sankey_graphs
Create Date: 2026-02-06

This migration adds async discussion mode support by adding timing configuration
fields to the discussions table.

New fields:
- timing_mode: SYNCHRONOUS (default) or ASYNCHRONOUS
- round_duration_hours: For async mode, soft deadline in hours
- min_submissions_for_advance: For async mode, auto-advance threshold
- auto_advance_enabled: For async mode, enable auto-close when conditions met

All existing discussions default to SYNCHRONOUS mode (backward compatible).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "015_add_async_timing_mode"
down_revision: Union[str, None] = "014_add_sankey_graphs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add timing mode fields to discussions table."""

    # Create enum type for timing mode
    timing_mode_enum = sa.Enum(
        'SYNCHRONOUS',
        'ASYNCHRONOUS',
        name='discussion_timing_mode'
    )
    timing_mode_enum.create(op.get_bind(), checkfirst=True)

    # Add timing_mode column with default SYNCHRONOUS
    op.add_column(
        'discussions',
        sa.Column(
            'timing_mode',
            sa.Enum('SYNCHRONOUS', 'ASYNCHRONOUS', name='discussion_timing_mode'),
            nullable=False,
            server_default='SYNCHRONOUS',
            comment='Discussion timing mode (SYNCHRONOUS or ASYNCHRONOUS)'
        )
    )

    # Add round_duration_hours column (nullable for backward compatibility)
    op.add_column(
        'discussions',
        sa.Column(
            'round_duration_hours',
            sa.Integer(),
            nullable=True,
            comment='For async mode: soft deadline in hours'
        )
    )

    # Add min_submissions_for_advance column (nullable)
    op.add_column(
        'discussions',
        sa.Column(
            'min_submissions_for_advance',
            sa.Integer(),
            nullable=True,
            comment='For async mode: auto-advance threshold'
        )
    )

    # Add auto_advance_enabled column with default False
    op.add_column(
        'discussions',
        sa.Column(
            'auto_advance_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='For async mode: enable auto-close when conditions met'
        )
    )


def downgrade() -> None:
    """Remove timing mode fields from discussions table."""

    # Drop columns
    op.drop_column('discussions', 'auto_advance_enabled')
    op.drop_column('discussions', 'min_submissions_for_advance')
    op.drop_column('discussions', 'round_duration_hours')
    op.drop_column('discussions', 'timing_mode')

    # Drop enum type
    sa.Enum(name='discussion_timing_mode').drop(op.get_bind(), checkfirst=True)

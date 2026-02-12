"""Add sankey_graphs table for Spec 005

Revision ID: 014_add_sankey_graphs
Revises: 013_create_spec004_clustering
Create Date: 2026-02-05

This migration creates the sankey_graphs table for storing constructed Sankey
diagrams as JSONB. The table provides persistence for SankeyGraph entities
from Spec 005 (Sankey Diagram Construction).

The sankey_graphs table stores:
- Complete Sankey graph data as JSONB (columns, nodes, edges, rounds)
- Discussion ID for unique identification and idempotency
- Creation timestamp for audit trail
- Optional metadata (construction_time_ms, algorithm_version, etc.)

Indexes:
- discussion_id (unique) - Primary lookup key and idempotency constraint
- created_at - For monitoring and debugging recent constructions
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "014_add_sankey_graphs"
down_revision: Union[str, None] = "013_create_spec004_clustering"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sankey_graphs table for Spec 005."""

    # ====================================================================
    # Create sankey_graphs table
    # ====================================================================
    # Purpose: Stores constructed Sankey diagrams as JSONB for fast retrieval
    # Dependencies: None (independent table, references discussion_id conceptually)
    # ====================================================================
    op.create_table(
        "sankey_graphs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Primary key (UUID)",
        ),
        sa.Column(
            "discussion_id",
            UUID(as_uuid=True),
            unique=True,
            nullable=False,
            comment="Discussion UUID from Spec 001 (unique constraint for idempotency)",
        ),
        sa.Column(
            "graph_data",
            JSONB,
            nullable=False,
            comment="Complete SankeyGraph as JSONB (columns, nodes, edges, rounds)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Timestamp when this graph was constructed",
        ),
        sa.Column(
            "metadata",
            JSONB,
            nullable=True,
            comment="Optional metadata (construction_time_ms, algorithm_version, etc.)",
        ),
    )

    # Create index on discussion_id for primary lookups
    # This is in addition to the unique constraint for faster queries
    op.create_index(
        "idx_sankey_discussion_id",
        "sankey_graphs",
        ["discussion_id"],
        unique=True,
    )

    # Create index on created_at for monitoring and debugging
    op.create_index(
        "idx_sankey_created_at",
        "sankey_graphs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop sankey_graphs table."""
    # Drop indexes first
    op.drop_index("idx_sankey_created_at", table_name="sankey_graphs")
    op.drop_index("idx_sankey_discussion_id", table_name="sankey_graphs")

    # Drop table
    op.drop_table("sankey_graphs")

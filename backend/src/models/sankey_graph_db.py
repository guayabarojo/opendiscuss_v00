"""
SankeyGraph Database Model - Stores constructed Sankey diagrams as JSONB

This SQLAlchemy model provides persistence for SankeyGraph entities in PostgreSQL.
The graph_data is stored as JSONB for fast retrieval without joins.

Table: sankey_graphs
Indexes: discussion_id (unique), created_at
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase

from ..database import Base


class SankeyGraphDB(Base):
    """
    Database model for persisting SankeyGraph entities.

    Attributes:
        id: Primary key (UUID)
        discussion_id: Discussion UUID (unique constraint)
        graph_data: Complete SankeyGraph as JSONB
        created_at: Timestamp when graph was constructed
        metadata: Optional metadata (construction_time_ms, etc.)

    Indexes:
        - discussion_id (unique) - Primary lookup key
        - created_at - For monitoring/debugging recent constructions
    """

    __tablename__ = "sankey_graphs"

    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
        doc="Primary key (UUID)"
    )

    discussion_id = Column(
        PGUUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
        doc="Discussion UUID from Spec 001 (unique constraint for idempotency)"
    )

    graph_data = Column(
        JSONB,
        nullable=False,
        doc="Complete SankeyGraph as JSONB (columns, nodes, edges, rounds)"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        doc="Timestamp when this graph was constructed"
    )

    graph_metadata = Column(
        JSONB,
        nullable=True,
        doc="Optional metadata (construction_time_ms, algorithm_version, etc.)"
    )

    def __repr__(self) -> str:
        return (
            f"<SankeyGraphDB(id={self.id}, discussion_id={self.discussion_id}, "
            f"created_at={self.created_at})>"
        )


# Indexes defined at module level for Alembic migration generation
Index("idx_sankey_discussion_id", SankeyGraphDB.discussion_id, unique=True)
Index("idx_sankey_created_at", SankeyGraphDB.created_at)

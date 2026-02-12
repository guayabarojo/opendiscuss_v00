"""
Embedding Entity Model - Spec 004 Clustering & Alignment

Stores semantic embedding vectors for approved summary texts.
Enables deterministic clustering and medoid recalculation.

Data Model Compliance:
- PERSISTED entity (embeddings stored for reproducibility)
- One-to-one with ApprovedSummary (each summary embedded once)
- Immutable after creation (determinism guarantee - FR-007, SC-007)
- 384-dimensional vectors from SBERT all-MiniLM-L6-v2 (FR-005, FR-008)

Constitutional Guarantees:
- Intent Fidelity: Only approved summaries are embedded (FR-001, FR-004)
- Semantic Accuracy: Deterministic embeddings enable reproducible clustering
- Temporal Transparency: Model versioning tracks embedding provenance (Assumption 2)

Performance Considerations:
- Normalized vectors for fast cosine similarity (dot product optimization)
- pgvector extension required for vector storage and indexing
- Cached to avoid recomputation when summary text unchanged
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import numpy as np
from typing import Optional

from src.database import Base


class Embedding(Base):
    """
    Semantic embedding vector for an approved summary.

    Lifecycle:
    - Created: When approved summary enters clustering pipeline
    - Read: During clustering (HDBSCAN input), medoid selection, alignment
    - Updated: Never (immutable - determinism guarantee)
    - Deleted: When summary is deleted (CASCADE)

    Validation Rules:
    - embedding_vector must be 384 dimensions (SBERT MiniLM output)
    - embedding_vector must be normalized (L2 norm = 1.0 for cosine similarity)
    - model_version must match current deployment version
    - Embedding is immutable after creation (same summary_id -> same vector)
    """

    __tablename__ = "embeddings"

    # Primary Key (Foreign Key to approved_summaries)
    summary_id = Column(
        UUID(as_uuid=True),
        ForeignKey("approved_summaries.summary_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Core Fields
    embedding_vector = Column(
        String,  # Stored as pgvector type in migration, but represented as String in SQLAlchemy
        nullable=False,
        comment="384-dimensional semantic embedding from SBERT all-MiniLM-L6-v2",
    )

    model_version = Column(
        String(50),
        nullable=False,
        default="all-MiniLM-L6-v2",
        comment="Model version for reproducibility and determinism tracking",
    )

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    approved_summary = relationship(
        "ApprovedSummary",
        back_populates="embedding",
        uselist=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Embedding(summary_id={self.summary_id}, "
            f"model_version={self.model_version}, "
            f"created_at={self.created_at})>"
        )

    @staticmethod
    def validate_vector_dimensions(vector: np.ndarray) -> bool:
        """
        Validate that embedding vector has correct dimensions.

        Args:
            vector: NumPy array representing the embedding

        Returns:
            bool: True if vector is 384-dimensional, False otherwise

        Validation Rule (FR-005, FR-008):
        - SBERT all-MiniLM-L6-v2 produces 384-dimensional vectors
        """
        return vector.shape == (384,)

    @staticmethod
    def validate_vector_normalized(vector: np.ndarray, atol: float = 1e-6) -> bool:
        """
        Validate that embedding vector is normalized (L2 norm = 1.0).

        Args:
            vector: NumPy array representing the embedding
            atol: Absolute tolerance for floating point comparison

        Returns:
            bool: True if L2 norm is approximately 1.0, False otherwise

        Validation Rule:
        - Normalized vectors enable fast cosine similarity via dot product
        - Optimization for clustering and alignment performance
        """
        norm = np.linalg.norm(vector)
        return abs(norm - 1.0) < atol

    @staticmethod
    def serialize_vector(vector: np.ndarray) -> str:
        """
        Serialize NumPy array to pgvector-compatible string format.

        Args:
            vector: 384-dimensional NumPy array

        Returns:
            str: pgvector format string (e.g., "[0.1, -0.2, ...]")

        Raises:
            ValueError: If vector dimensions are invalid
        """
        if not Embedding.validate_vector_dimensions(vector):
            raise ValueError(f"Vector must be 384-dimensional, got {vector.shape}")

        # Convert to list and format as pgvector string
        vector_list = vector.tolist()
        return "[" + ",".join(str(v) for v in vector_list) + "]"

    @staticmethod
    def deserialize_vector(vector_str: str) -> np.ndarray:
        """
        Deserialize pgvector string to NumPy array.

        Args:
            vector_str: pgvector format string

        Returns:
            np.ndarray: 384-dimensional NumPy array

        Raises:
            ValueError: If deserialized vector has invalid dimensions
        """
        # Remove brackets and split by comma
        vector_str = vector_str.strip("[]")
        values = [float(v.strip()) for v in vector_str.split(",")]
        vector = np.array(values, dtype=np.float32)

        if not Embedding.validate_vector_dimensions(vector):
            raise ValueError(f"Deserialized vector has invalid dimensions: {vector.shape}")

        return vector

    def get_vector_as_numpy(self) -> np.ndarray:
        """
        Get embedding vector as NumPy array.

        Returns:
            np.ndarray: 384-dimensional embedding vector

        Usage:
            embedding = db.query(Embedding).first()
            vector = embedding.get_vector_as_numpy()
            # Use for clustering, similarity computation, etc.
        """
        return Embedding.deserialize_vector(self.embedding_vector)

    def set_vector_from_numpy(self, vector: np.ndarray) -> None:
        """
        Set embedding vector from NumPy array.

        Args:
            vector: 384-dimensional NumPy array

        Raises:
            ValueError: If vector dimensions or normalization is invalid
            RuntimeError: If embedding already exists (immutability check)

        Immutability Guarantee (FR-007):
        - Embeddings cannot be modified after creation
        - Same summary_id always produces same vector (determinism)
        """
        if self.embedding_vector is not None:
            raise RuntimeError(
                "Embedding is immutable - cannot modify after creation. "
                "Determinism guarantee requires same summary_id -> same vector."
            )

        if not Embedding.validate_vector_dimensions(vector):
            raise ValueError(f"Vector must be 384-dimensional, got {vector.shape}")

        if not Embedding.validate_vector_normalized(vector):
            raise ValueError(
                f"Vector must be normalized (L2 norm = 1.0), got norm = {np.linalg.norm(vector)}"
            )

        self.embedding_vector = Embedding.serialize_vector(vector)

    @classmethod
    async def get_by_summary_id(
        cls, db_session, summary_id: uuid.UUID
    ) -> Optional["Embedding"]:
        """
        Retrieve embedding by summary_id.

        Args:
            db_session: AsyncSession for database operations
            summary_id: UUID of the approved summary

        Returns:
            Embedding if found, None otherwise

        Usage:
            embedding = await Embedding.get_by_summary_id(db, summary_id)
            if embedding:
                vector = embedding.get_vector_as_numpy()
        """
        from sqlalchemy import select

        result = await db_session.execute(
            select(cls).where(cls.summary_id == summary_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def create(
        cls,
        db_session,
        summary_id: uuid.UUID,
        embedding_vector: np.ndarray,
        model_version: str = "all-MiniLM-L6-v2",
    ) -> "Embedding":
        """
        Create and persist a new embedding.

        Args:
            db_session: AsyncSession for database operations
            summary_id: UUID of the approved summary
            embedding_vector: 384-dimensional normalized NumPy array
            model_version: Model version string (default: all-MiniLM-L6-v2)

        Returns:
            Embedding: The created embedding entity

        Raises:
            ValueError: If vector validation fails
            RuntimeError: If embedding already exists for this summary_id

        Usage:
            embedding = await Embedding.create(
                db,
                summary_id=summary.summary_id,
                embedding_vector=normalized_vector,
                model_version="all-MiniLM-L6-v2"
            )
        """
        # Check if embedding already exists (determinism guarantee)
        existing = await cls.get_by_summary_id(db_session, summary_id)
        if existing:
            raise RuntimeError(
                f"Embedding already exists for summary_id {summary_id}. "
                "Embeddings are immutable - cannot create duplicate."
            )

        # Validate vector
        if not cls.validate_vector_dimensions(embedding_vector):
            raise ValueError(f"Vector must be 384-dimensional, got {embedding_vector.shape}")

        if not cls.validate_vector_normalized(embedding_vector):
            raise ValueError(
                f"Vector must be normalized (L2 norm = 1.0), "
                f"got norm = {np.linalg.norm(embedding_vector)}"
            )

        # Create embedding
        embedding = cls(
            summary_id=summary_id,
            model_version=model_version,
        )
        embedding.set_vector_from_numpy(embedding_vector)

        db_session.add(embedding)
        await db_session.flush()  # Flush to get any database-generated values

        return embedding

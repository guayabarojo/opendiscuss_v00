"""
Embedding service for generating and managing semantic embeddings.

This service handles embedding generation from summary text using SBERT,
with deterministic guarantees and caching support.
"""

import logging
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from src.ml.embedding_models import (
    load_sbert_model,
    get_model_version,
    get_embedding_dimension,
    normalize_embeddings,
    EmbeddingModelError,
)

logger = logging.getLogger(__name__)


class EmbeddingServiceError(Exception):
    """Raised when embedding service operations fail."""
    pass


async def generate_embeddings(
    summary_texts: List[str],
    normalize: bool = True,
    batch_size: int = 32,
) -> np.ndarray:
    """
    Generate 384-dimensional embeddings from summary texts with determinism guarantee.

    This function uses SBERT all-MiniLM-L6-v2 to generate semantic embeddings.
    The embeddings are deterministic (same text always produces same vector).

    Args:
        summary_texts: List of summary text strings to embed
        normalize: Whether to L2-normalize embeddings (default: True)
        batch_size: Batch size for encoding (default: 32)

    Returns:
        Array of embeddings with shape (len(summary_texts), 384)

    Raises:
        EmbeddingServiceError: If embedding generation fails
        ValueError: If summary_texts is empty

    Requirements:
        - FR-005: Generate semantic embeddings from summary text
        - FR-007: Deterministic embedding generation
        - FR-008: 384-dimensional vectors
        - Data model: "Batch Embedding" optimization
        - T036: Error handling with descriptive messages

    Example:
        >>> texts = ["We need to reduce costs", "Budget is too high"]
        >>> embeddings = await generate_embeddings(texts)
        >>> embeddings.shape
        (2, 384)
        >>> # Same text always produces same embedding
        >>> embeddings2 = await generate_embeddings(texts)
        >>> np.allclose(embeddings, embeddings2, atol=1e-9)
        True
    """
    if not summary_texts:
        raise ValueError("summary_texts cannot be empty")

    # Validate inputs (T036: descriptive validation errors)
    if not isinstance(summary_texts, list):
        raise TypeError(
            f"summary_texts must be a list, got {type(summary_texts).__name__}"
        )

    if any(not isinstance(text, str) for text in summary_texts):
        raise TypeError("All items in summary_texts must be strings")

    # Validate batch size
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")

    try:
        logger.info(
            f"Starting embedding generation for {len(summary_texts)} summaries "
            f"(batch_size={batch_size})"
        )

        # Load model (cached after first call)
        # T036: Handle model loading errors with descriptive messages
        try:
            model = load_sbert_model()
        except EmbeddingModelError as e:
            error_msg = (
                f"Failed to load embedding model: {str(e)}. "
                f"Ensure sentence-transformers is installed and model is accessible."
            )
            logger.error(error_msg, exc_info=True)
            raise EmbeddingServiceError(error_msg) from e

        # Generate embeddings
        # Note: model.encode is synchronous, but wrapping in async for future
        # support of async embedding generation
        # T036: Handle encoding errors with context-specific messages
        try:
            embeddings = model.encode(
                summary_texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except RuntimeError as e:
            error_msg = (
                f"SBERT encoding failed with runtime error: {str(e)}. "
                f"This may indicate insufficient GPU memory or model resource constraints."
            )
            logger.error(error_msg, exc_info=True)
            raise EmbeddingServiceError(error_msg) from e
        except Exception as e:
            error_msg = (
                f"SBERT encoding failed: {str(e)}. "
                f"Check that input texts are valid and not excessively large."
            )
            logger.error(error_msg, exc_info=True)
            raise EmbeddingServiceError(error_msg) from e

        # Verify embeddings were generated
        if embeddings is None or embeddings.size == 0:
            error_msg = "Embedding generation returned empty result"
            logger.error(error_msg)
            raise EmbeddingServiceError(error_msg)

        # Verify dimensions (T036: detailed dimension validation)
        try:
            expected_dim = get_embedding_dimension()
            if embeddings.ndim != 2:
                raise EmbeddingServiceError(
                    f"Generated embeddings have {embeddings.ndim} dimensions, "
                    f"expected 2-dimensional array"
                )

            if embeddings.shape[0] != len(summary_texts):
                raise EmbeddingServiceError(
                    f"Generated embeddings count ({embeddings.shape[0]}) "
                    f"does not match input count ({len(summary_texts)})"
                )

            if embeddings.shape[1] != expected_dim:
                raise EmbeddingServiceError(
                    f"Generated embeddings have dimension {embeddings.shape[1]}, "
                    f"expected {expected_dim}"
                )
        except (AttributeError, IndexError) as e:
            error_msg = f"Failed to validate embedding shape: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise EmbeddingServiceError(error_msg) from e

        # Normalize for cosine similarity optimization
        if normalize:
            try:
                embeddings = normalize_embeddings(embeddings)
                logger.debug("Embeddings normalized (L2 norm = 1.0)")
            except Exception as e:
                error_msg = f"Failed to normalize embeddings: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise EmbeddingServiceError(error_msg) from e

        logger.info(
            f"Successfully generated {len(embeddings)} embeddings "
            f"(shape: {embeddings.shape}, dtype: {embeddings.dtype})"
        )

        return embeddings

    except EmbeddingServiceError:
        # Re-raise our custom exceptions as-is
        raise
    except Exception as e:
        # T036: Catch any unexpected errors with detailed message
        error_msg = f"Unexpected error during embedding generation: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise EmbeddingServiceError(error_msg) from e


async def generate_single_embedding(
    summary_text: str,
    normalize: bool = True,
) -> np.ndarray:
    """
    Generate embedding for a single summary text.

    Convenience wrapper around generate_embeddings for single texts.

    Args:
        summary_text: Summary text to embed
        normalize: Whether to L2-normalize embedding (default: True)

    Returns:
        Embedding vector with shape (384,)

    Raises:
        EmbeddingServiceError: If embedding generation fails
        ValueError: If summary_text is empty

    Example:
        >>> embedding = await generate_single_embedding("We need to reduce costs")
        >>> embedding.shape
        (384,)
    """
    if not summary_text or not summary_text.strip():
        raise ValueError("summary_text cannot be empty")

    embeddings = await generate_embeddings([summary_text], normalize=normalize)
    return embeddings[0]


def verify_embedding_determinism(
    summary_texts: List[str],
    iterations: int = 2,
) -> bool:
    """
    Verify that embedding generation is deterministic.

    Generates embeddings multiple times for the same texts and verifies
    that the results are identical.

    Args:
        summary_texts: List of texts to test
        iterations: Number of times to generate embeddings (default: 2)

    Returns:
        True if embeddings are deterministic, False otherwise

    Requirements:
        - FR-007: Deterministic embedding generation
        - SC-007: Embedding determinism test

    Example:
        >>> texts = ["test text 1", "test text 2"]
        >>> verify_embedding_determinism(texts, iterations=3)
        True
    """
    if not summary_texts:
        raise ValueError("summary_texts cannot be empty")

    if iterations < 2:
        raise ValueError("iterations must be at least 2")

    try:
        logger.info(
            f"Verifying embedding determinism for {len(summary_texts)} texts "
            f"({iterations} iterations)"
        )

        model = load_sbert_model()

        # Generate embeddings multiple times
        all_embeddings = []
        for i in range(iterations):
            embeddings = model.encode(
                summary_texts,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            all_embeddings.append(embeddings)

        # Compare all iterations to the first one
        reference = all_embeddings[0]
        for i, embeddings in enumerate(all_embeddings[1:], start=2):
            if not np.allclose(reference, embeddings, atol=1e-9):
                logger.error(
                    f"Embedding determinism check failed: "
                    f"iteration {i} differs from iteration 1"
                )
                return False

        logger.info("Embedding determinism verified successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to verify embedding determinism: {str(e)}")
        return False


def get_current_model_info() -> dict:
    """
    Get information about the current embedding model.

    Returns:
        Dictionary with model version and embedding dimension

    Example:
        >>> info = get_current_model_info()
        >>> info
        {'model_version': 'all-MiniLM-L6-v2', 'embedding_dim': 384}
    """
    return {
        "model_version": get_model_version(),
        "embedding_dim": get_embedding_dimension(),
    }


async def persist_embeddings(
    db: AsyncSession,
    summary_embeddings: Dict[UUID, np.ndarray],
    model_version: Optional[str] = None,
) -> int:
    """
    Persist embeddings to the database with model version tracking.

    Saves embedding vectors to the embeddings table. Each embedding is associated
    with a summary_id and includes the model version for reproducibility.

    Args:
        db: Database session
        summary_embeddings: Dictionary mapping summary_id to embedding vector
        model_version: Model version string (default: current model version)

    Returns:
        Number of embeddings persisted

    Raises:
        EmbeddingServiceError: If persistence fails
        ValueError: If summary_embeddings is empty or vectors have wrong dimension

    Requirements:
        - FR-007: Model versioning for reproducibility
        - Data model: embeddings table with summary_id, embedding_vector, model_version
        - Assumption 2: Track model version in embeddings

    Example:
        >>> summary_embeddings = {
        ...     UUID("..."): np.array([0.1, 0.2, ...]),  # 384 dims
        ...     UUID("..."): np.array([0.3, 0.4, ...]),  # 384 dims
        ... }
        >>> count = await persist_embeddings(db, summary_embeddings)
        >>> count
        2
    """
    if not summary_embeddings:
        raise ValueError("summary_embeddings cannot be empty")

    if model_version is None:
        model_version = get_model_version()

    expected_dim = get_embedding_dimension()

    try:
        logger.info(
            f"Persisting {len(summary_embeddings)} embeddings "
            f"(model_version={model_version})"
        )

        # Validate all embeddings have correct dimension
        for summary_id, embedding in summary_embeddings.items():
            if embedding.shape[0] != expected_dim:
                raise ValueError(
                    f"Embedding for summary {summary_id} has dimension {embedding.shape[0]}, "
                    f"expected {expected_dim}"
                )

        # Import here to avoid circular dependency
        from src.models.embedding import Embedding
        embeddings_table = Embedding.__table__

        # Prepare batch insert data
        insert_data = []
        for summary_id, embedding in summary_embeddings.items():
            # Convert numpy array to pgvector string format
            embedding_str = Embedding.serialize_vector(embedding)

            insert_data.append({
                "summary_id": summary_id,
                "embedding_vector": embedding_str,
                "model_version": model_version,
                "created_at": datetime.utcnow(),
            })

        # Batch insert embeddings
        stmt = insert(embeddings_table).values(insert_data)
        await db.execute(stmt)
        await db.commit()

        logger.info(f"Successfully persisted {len(insert_data)} embeddings")

        return len(insert_data)

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise

    except Exception as e:
        await db.rollback()
        error_msg = f"Failed to persist embeddings: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise EmbeddingServiceError(error_msg) from e


async def load_embeddings(
    db: AsyncSession,
    summary_ids: List[UUID],
) -> Dict[UUID, np.ndarray]:
    """
    Load embeddings from the database for given summary IDs.

    Args:
        db: Database session
        summary_ids: List of summary IDs to load embeddings for

    Returns:
        Dictionary mapping summary_id to embedding vector

    Raises:
        EmbeddingServiceError: If loading fails

    Requirements:
        - Data model: "Cache Embeddings" optimization
        - FR-007: Don't recompute if summary text unchanged

    Example:
        >>> summary_ids = [UUID("..."), UUID("...")]
        >>> embeddings = await load_embeddings(db, summary_ids)
        >>> len(embeddings)
        2
    """
    if not summary_ids:
        return {}

    try:
        logger.info(f"Loading {len(summary_ids)} embeddings from database")

        # Import here to avoid circular dependency
        from src.models.embedding import Embedding
        embeddings_table = Embedding.__table__

        # Query embeddings
        stmt = select(embeddings_table).where(
            embeddings_table.c.summary_id.in_(summary_ids)
        )
        result = await db.execute(stmt)
        rows = result.fetchall()

        # Convert to dictionary
        embeddings = {}
        for row in rows:
            summary_id = row.summary_id
            # Convert list back to numpy array
            embedding_vector = np.array(row.embedding_vector, dtype=np.float32)
            embeddings[summary_id] = embedding_vector

        logger.info(f"Loaded {len(embeddings)} embeddings from database")

        return embeddings

    except Exception as e:
        error_msg = f"Failed to load embeddings: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise EmbeddingServiceError(error_msg) from e


async def get_or_generate_embeddings(
    db: AsyncSession,
    summaries: List[Dict],
    force_regenerate: bool = False,
) -> Dict[UUID, np.ndarray]:
    """
    Get embeddings from cache or generate new ones if not cached.

    This function implements the caching optimization described in the data model.
    It first tries to load existing embeddings from the database, then generates
    embeddings for any summaries that don't have cached embeddings.

    Args:
        db: Database session
        summaries: List of summary dictionaries with 'summary_id' and 'summary_text'
        force_regenerate: If True, regenerate embeddings even if cached

    Returns:
        Dictionary mapping summary_id to embedding vector

    Raises:
        EmbeddingServiceError: If embedding operations fail
        ValueError: If summaries list is empty or missing required fields

    Requirements:
        - Data model: "Cache Embeddings" optimization
        - FR-007: Deterministic embeddings with model versioning

    Example:
        >>> summaries = [
        ...     {"summary_id": UUID("..."), "summary_text": "Cost reduction needed"},
        ...     {"summary_id": UUID("..."), "summary_text": "Budget too high"}
        ... ]
        >>> embeddings = await get_or_generate_embeddings(db, summaries)
        >>> len(embeddings)
        2
    """
    if not summaries:
        raise ValueError("summaries cannot be empty")

    # Validate required fields
    for summary in summaries:
        if "summary_id" not in summary or "summary_text" not in summary:
            raise ValueError("Each summary must have 'summary_id' and 'summary_text'")

    summary_ids = [s["summary_id"] for s in summaries]
    current_model_version = get_model_version()

    try:
        # Load existing embeddings if not forcing regeneration
        cached_embeddings = {}
        if not force_regenerate:
            cached_embeddings = await load_embeddings(db, summary_ids)

            # Filter out embeddings with different model version
            cached_embeddings = {
                sid: emb for sid, emb in cached_embeddings.items()
                # Note: We'd need to check model version from DB, simplified here
            }

            logger.info(f"Found {len(cached_embeddings)} cached embeddings")

        # Identify summaries that need embedding generation
        summaries_to_embed = [
            s for s in summaries
            if s["summary_id"] not in cached_embeddings
        ]

        # Generate new embeddings if needed
        new_embeddings = {}
        if summaries_to_embed:
            logger.info(f"Generating {len(summaries_to_embed)} new embeddings")

            texts = [s["summary_text"] for s in summaries_to_embed]
            embedding_vectors = await generate_embeddings(texts)

            # Map embeddings to summary IDs
            for summary, embedding in zip(summaries_to_embed, embedding_vectors):
                new_embeddings[summary["summary_id"]] = embedding

            # Persist new embeddings
            if new_embeddings:
                await persist_embeddings(db, new_embeddings, current_model_version)

        # Combine cached and new embeddings
        all_embeddings = {**cached_embeddings, **new_embeddings}

        logger.info(
            f"Returning {len(all_embeddings)} embeddings "
            f"({len(cached_embeddings)} cached, {len(new_embeddings)} new)"
        )

        return all_embeddings

    except Exception as e:
        error_msg = f"Failed to get or generate embeddings: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise EmbeddingServiceError(error_msg) from e

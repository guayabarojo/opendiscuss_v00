"""
Embedding model loader for semantic clustering.

This module handles loading and managing the SBERT all-MiniLM-L6-v2 model
for deterministic embedding generation (FR-007).
"""

import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

# Lazy import to avoid loading sentence-transformers unless needed
_model_instance: Optional["SentenceTransformer"] = None
MODEL_VERSION = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class EmbeddingModelError(Exception):
    """Raised when embedding model operations fail."""
    pass


def load_sbert_model(model_name: str = MODEL_VERSION) -> "SentenceTransformer":
    """
    Load SBERT all-MiniLM-L6-v2 model with deterministic configuration.

    This function loads the sentence-transformers model and configures it
    for deterministic embedding generation. The model is cached after first load.

    Args:
        model_name: Model identifier (default: "all-MiniLM-L6-v2")

    Returns:
        Loaded SentenceTransformer model instance

    Raises:
        EmbeddingModelError: If model loading fails

    Requirements:
        - FR-007: Deterministic embedding generation
        - FR-008: 384-dimensional vectors (MiniLM output)

    Example:
        >>> model = load_sbert_model()
        >>> embeddings = model.encode(["sample text"])
        >>> embeddings.shape
        (1, 384)
    """
    global _model_instance

    if _model_instance is not None:
        logger.debug(f"Returning cached model: {model_name}")
        return _model_instance

    try:
        logger.info(f"Loading SBERT model: {model_name}")

        # Import here to avoid loading sentence-transformers at module import time
        from sentence_transformers import SentenceTransformer

        # Load model with deterministic configuration
        # Note: sentence-transformers uses PyTorch underneath which respects
        # the random seed set in the environment
        model = SentenceTransformer(model_name)

        # Verify model output dimensions
        test_embedding = model.encode(["test"], show_progress_bar=False)
        if test_embedding.shape[1] != EMBEDDING_DIM:
            raise EmbeddingModelError(
                f"Model {model_name} produces {test_embedding.shape[1]}-dim vectors, "
                f"expected {EMBEDDING_DIM}"
            )

        # Cache the model instance
        _model_instance = model

        logger.info(
            f"Successfully loaded model {model_name} "
            f"(output dimension: {EMBEDDING_DIM})"
        )

        return model

    except ImportError as e:
        error_msg = (
            "sentence-transformers library not installed. "
            "Install with: pip install sentence-transformers>=2.2.0"
        )
        logger.error(error_msg)
        raise EmbeddingModelError(error_msg) from e

    except Exception as e:
        error_msg = f"Failed to load SBERT model '{model_name}': {str(e)}"
        logger.error(error_msg)
        raise EmbeddingModelError(error_msg) from e


def get_model_version() -> str:
    """
    Get the current embedding model version.

    Returns:
        Model version string for tracking embeddings

    Requirements:
        - FR-007: Model versioning for reproducibility
        - Assumption 2: Track model version in embeddings table
    """
    return MODEL_VERSION


def get_embedding_dimension() -> int:
    """
    Get the embedding vector dimension for the current model.

    Returns:
        Embedding dimension (384 for all-MiniLM-L6-v2)

    Requirements:
        - FR-008: 384-dimensional vectors
    """
    return EMBEDDING_DIM


def unload_model() -> None:
    """
    Unload the cached model instance to free memory.

    Useful for testing or when the model is no longer needed.
    """
    global _model_instance
    if _model_instance is not None:
        logger.info("Unloading cached SBERT model")
        _model_instance = None


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """
    Normalize embedding vectors for cosine similarity optimization.

    L2-normalization allows cosine similarity to be computed as a simple
    dot product, significantly improving performance.

    Args:
        embeddings: Array of shape (n_samples, embedding_dim)

    Returns:
        Normalized embeddings (L2 norm = 1.0 for each vector)

    Requirements:
        - Data model optimization: "Normalize Vectors" section

    Example:
        >>> embeddings = np.array([[3.0, 4.0]])
        >>> normalized = normalize_embeddings(embeddings)
        >>> np.linalg.norm(normalized[0])
        1.0
    """
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    # Avoid division by zero
    norms = np.where(norms == 0, 1, norms)
    return embeddings / norms

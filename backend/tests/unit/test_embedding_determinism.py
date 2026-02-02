"""
T068: Embedding Determinism Test

Verifies that embedding generation is deterministic (SC-007):
- Same text always produces identical vectors across multiple runs
- No floating-point variance due to randomness
- Model versioning maintained

Requirements:
- SC-007: Embedding reproducibility - identical embeddings for same text
- FR-007: Deterministic embedding generation
"""

import pytest
import numpy as np
from uuid import uuid4

from src.services.embedding_service import generate_embeddings, verify_embedding_determinism
from src.ml.embedding_models import (
    load_sbert_model,
    get_model_version,
    get_embedding_dimension,
    unload_model,
)


class TestEmbeddingDeterminism:
    """Test suite for embedding determinism (SC-007)."""

    @pytest.mark.asyncio
    async def test_identical_embeddings_across_runs(self):
        """
        T068.1: Generate embeddings 10 times with same text.

        Verify identical vectors (bitwise) across all runs.
        This tests SC-007 requirement.
        """
        test_texts = [
            "We need to reduce costs by 20%",
            "Speed improvements are critical",
            "Fairness in distribution matters",
        ]

        # Generate embeddings 10 times
        embeddings_runs = []
        for i in range(10):
            embeddings = await generate_embeddings(test_texts)
            embeddings_runs.append(embeddings)
            assert embeddings.shape == (3, 384), f"Run {i}: Wrong embedding shape"

        # Verify all runs produce identical embeddings
        reference = embeddings_runs[0]
        for i in range(1, 10):
            current = embeddings_runs[i]
            # Use exact comparison (numpy's allclose with very tight tolerance)
            assert np.allclose(
                reference, current, atol=1e-9, rtol=1e-9
            ), f"Run {i} differs from reference - determinism violated"

    @pytest.mark.asyncio
    async def test_vector_dimension(self):
        """
        T068.2: Verify embedding dimension is 384.

        Tests FR-008 requirement for 384-dimensional vectors.
        """
        test_texts = ["sample text", "another sample", "third text"]
        embeddings = await generate_embeddings(test_texts)

        assert embeddings.shape[0] == 3, "Should have 3 embeddings"
        assert embeddings.shape[1] == 384, "Should be 384-dimensional"
        assert get_embedding_dimension() == 384, "get_embedding_dimension should return 384"

    @pytest.mark.asyncio
    async def test_single_text_reproducibility(self):
        """
        T068.3: Single text determinism across runs.

        Generate same text 20 times, verify identical embeddings.
        """
        text = "We need to reduce costs by 20%"

        embeddings_list = []
        for i in range(20):
            embeddings = await generate_embeddings([text])
            embeddings_list.append(embeddings[0])

        # All embeddings should be identical
        reference = embeddings_list[0]
        for i in range(1, 20):
            current = embeddings_list[i]
            assert np.allclose(
                reference, current, atol=1e-9, rtol=1e-9
            ), f"Run {i} differs - determinism violated for single text"

    @pytest.mark.asyncio
    async def test_batch_vs_individual_consistency(self):
        """
        T068.4: Batch processing vs individual text.

        Generate texts in batch and individually, verify identical results.
        """
        texts = [
            "We need to reduce costs by 20%",
            "Speed improvements are critical",
            "Fairness in distribution matters",
        ]

        # Generate as batch
        batch_embeddings = await generate_embeddings(texts)

        # Generate individually
        individual_embeddings = []
        for text in texts:
            emb = await generate_embeddings([text])
            individual_embeddings.append(emb[0])
        individual_embeddings = np.array(individual_embeddings)

        # Should be identical
        assert np.allclose(
            batch_embeddings, individual_embeddings, atol=1e-9, rtol=1e-9
        ), "Batch and individual processing produce different embeddings"

    @pytest.mark.asyncio
    async def test_normalized_embeddings_determinism(self):
        """
        T068.5: Normalized embeddings are deterministic.

        Test that L2-normalized embeddings maintain determinism.
        """
        test_texts = ["sample", "text", "for", "testing"]

        embeddings1 = await generate_embeddings(test_texts, normalize=True)
        embeddings2 = await generate_embeddings(test_texts, normalize=True)

        assert np.allclose(
            embeddings1, embeddings2, atol=1e-9, rtol=1e-9
        ), "Normalized embeddings are not deterministic"

        # Verify L2 norm is 1.0 for each embedding
        norms = np.linalg.norm(embeddings1, axis=1)
        assert np.allclose(
            norms, 1.0, atol=1e-6
        ), "Normalized embeddings should have L2 norm = 1.0"

    def test_model_version_consistency(self):
        """
        T068.6: Model version is consistent.

        Tests that model version tracking works for reproducibility.
        """
        model_version = get_model_version()
        assert model_version == "all-MiniLM-L6-v2", f"Unexpected model version: {model_version}"

        # Should be consistent across calls
        version2 = get_model_version()
        assert version2 == model_version, "Model version changed between calls"

    def test_model_caching(self):
        """
        T068.7: Model is cached for performance.

        Verify that loading model twice returns same instance.
        """
        try:
            unload_model()
            model1 = load_sbert_model()
            model2 = load_sbert_model()

            # Should be same instance (cached)
            assert model1 is model2, "Model should be cached"
        finally:
            unload_model()

    @pytest.mark.asyncio
    async def test_embedding_value_ranges(self):
        """
        T068.8: Embeddings have reasonable value ranges.

        Verify embeddings are not filled with NaNs or Infs.
        """
        test_texts = ["sample " * 50, "another " * 50, "third " * 50]
        embeddings = await generate_embeddings(test_texts)

        # Check for NaNs and Infs
        assert not np.isnan(embeddings).any(), "Embeddings contain NaNs"
        assert not np.isinf(embeddings).any(), "Embeddings contain Infs"

        # Check values are in reasonable range (after normalization)
        assert np.all(embeddings >= -2.0) and np.all(
            embeddings <= 2.0
        ), "Embeddings contain unreasonable values"

    @pytest.mark.asyncio
    async def test_empty_text_handling(self):
        """
        T068.9: Verify error handling for empty input.

        Empty text list should raise ValueError.
        """
        with pytest.raises(ValueError):
            await generate_embeddings([])

    @pytest.mark.asyncio
    async def test_verify_embedding_determinism_function(self):
        """
        T068.10: Test verify_embedding_determinism utility function.

        Uses dedicated verification function to check determinism.
        """
        test_texts = [
            "We need to reduce costs by 20%",
            "Speed improvements are critical",
        ]

        # This should complete without raising if determinism is maintained
        try:
            is_deterministic = verify_embedding_determinism(test_texts, num_runs=5)
            assert is_deterministic, "verify_embedding_determinism returned False"
        except NotImplementedError:
            # If function doesn't exist yet, skip
            pytest.skip("verify_embedding_determinism not implemented")


class TestEmbeddingEdgeCases:
    """Test edge cases for embedding generation."""

    @pytest.mark.asyncio
    async def test_very_long_text(self):
        """Handle very long text (>10k characters)."""
        long_text = "word " * 2000  # ~10k characters
        embeddings = await generate_embeddings([long_text])

        assert embeddings.shape == (1, 384), "Should handle long text"
        assert not np.isnan(embeddings).any(), "Long text should not produce NaNs"

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Handle text with special characters."""
        special_texts = [
            "Cost reduction: 20% → 30%",
            "Émojis: 😊 speed ⚡",
            "Unicode: 你好 мир",
            "Symbols: !@#$%^&*()",
        ]

        embeddings = await generate_embeddings(special_texts)
        assert embeddings.shape == (4, 384), "Should handle special characters"
        assert not np.isnan(embeddings).any(), "No NaNs for special characters"

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        """Handle whitespace-only text."""
        whitespace_texts = ["   ", "\t\t", "\n\n"]

        embeddings = await generate_embeddings(whitespace_texts)
        assert embeddings.shape == (3, 384), "Should handle whitespace"
        # These should produce different embeddings (not identical to other whitespace)
        assert not np.allclose(embeddings[0], embeddings[1]), "Different whitespace should differ"

    @pytest.mark.asyncio
    async def test_numerical_stability(self):
        """
        T068 Extended: Verify numerical stability.

        Test that embeddings don't suffer from numerical underflow/overflow.
        """
        # Generate same text multiple times
        repeated_text = ["sample text"] * 100

        embeddings = await generate_embeddings(repeated_text)

        # All should be identical (determinism)
        reference = embeddings[0]
        for i in range(1, 100):
            assert np.allclose(embeddings[i], reference, atol=1e-9, rtol=1e-9), (
                f"Embedding {i} differs from reference - numerical instability"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

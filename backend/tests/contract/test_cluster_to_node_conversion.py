"""
Contract test: Cluster to SankeyNode Conversion (Spec 004 → Spec 005)

Validates T028: Verify that Spec 004 cluster data correctly maps to Spec 005 SankeyNode entities.

This test ensures the node_builder service properly converts cluster entities into
SankeyNode entities for Sankey diagram construction.

Constitutional Coverage:
- Semantic Accuracy: All clusters preserved as nodes (no filtering)
- Intent Fidelity: Medoid summary text used as node labels (actual participant text)
- Temporal Transparency: user_pct computed per-round (no cross-round normalization)
"""

import pytest
import numpy as np
from uuid import uuid4, UUID
from datetime import datetime, timezone

from src.models.cluster import Cluster
from src.models.sankey_node import SankeyNode
from src.services.node_builder import create_node_from_cluster


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_cluster_regular():
    """
    Create a mock regular cluster (user_count > 1).

    Represents a typical semantic grouping with multiple participants.
    """
    cluster_id = uuid4()

    # Create mock cluster with necessary attributes
    cluster = type('Cluster', (), {
        'id': cluster_id,
        'cluster_id': cluster_id,
        'user_count': 12,
        'user_pct': 0.24,
        'round_id': uuid4(),
        'label_summary_id': uuid4(),
        'centroid_vector': '[0.1, 0.2, 0.3]',  # Simplified for testing
        'display_group_id': uuid4(),
        'created_at': datetime.now(timezone.utc),
        'members': [type('Member', (), {'user_id': uuid4()})() for _ in range(12)]
    })()

    return cluster


@pytest.fixture
def mock_cluster_singleton():
    """
    Create a mock singleton cluster (user_count = 1).

    Represents an outlier that was converted to a singleton cluster.
    Constitutional guarantee: Singleton clusters must be preserved.
    """
    cluster_id = uuid4()

    cluster = type('Cluster', (), {
        'id': cluster_id,
        'cluster_id': cluster_id,
        'user_count': 1,
        'user_pct': 0.02,
        'round_id': uuid4(),
        'label_summary_id': uuid4(),
        'centroid_vector': '[0.5, 0.6, 0.7]',
        'display_group_id': None,  # Singleton may not have alignment
        'created_at': datetime.now(timezone.utc),
        'members': [type('Member', (), {'user_id': uuid4()})()]
    })()

    return cluster


@pytest.fixture
def mock_cluster_majority():
    """
    Create a mock majority cluster (user_count > 50% of total).

    Represents a dominant viewpoint in the round.
    """
    cluster_id = uuid4()

    cluster = type('Cluster', (), {
        'id': cluster_id,
        'cluster_id': cluster_id,
        'user_count': 30,
        'user_pct': 0.60,
        'round_id': uuid4(),
        'label_summary_id': uuid4(),
        'centroid_vector': '[0.8, 0.9, 1.0]',
        'display_group_id': uuid4(),
        'created_at': datetime.now(timezone.utc),
        'members': [type('Member', (), {'user_id': uuid4()})() for _ in range(30)]
    })()

    return cluster


@pytest.fixture
def sample_medoid_summary():
    """Sample medoid summary text (actual participant text)."""
    return "We should prioritize climate action and renewable energy investments."


# ============================================================================
# Core Conversion Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.contract
async def test_cluster_id_identity_mapping(mock_cluster_regular, sample_medoid_summary):
    """
    Test that cluster_id maps directly to node.cluster_id (identity mapping).

    Contract Requirement:
    - node.cluster_id == cluster.cluster_id
    - node.node_id == cluster.cluster_id (for traceability)
    - No transformation or normalization applied

    Validates: FR-014 (Node creation from cluster data)
    """
    total_participants = 50

    node = await create_node_from_cluster(
        cluster=mock_cluster_regular,
        total_round_participants=total_participants,
        medoid_summary=sample_medoid_summary,
        display_group_id=mock_cluster_regular.display_group_id
    )

    # Verify identity mapping
    assert node.cluster_id == mock_cluster_regular.id, \
        "cluster_id must map directly to node.cluster_id"
    assert node.node_id == mock_cluster_regular.id, \
        "node_id should equal cluster_id for traceability"

    # Verify type correctness
    assert isinstance(node.cluster_id, UUID), \
        "cluster_id must be a UUID"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_medoid_summary_to_label(mock_cluster_regular, sample_medoid_summary):
    """
    Test that medoid_summary_text maps to node.label_summary.

    Contract Requirement:
    - node.label_summary == cluster.label_summary.summary_text
    - Uses actual participant text (Intent Fidelity - Principle II)
    - No LLM generation or transformation applied

    Validates: Intent Fidelity constitutional guarantee
    """
    total_participants = 50

    node = await create_node_from_cluster(
        cluster=mock_cluster_regular,
        total_round_participants=total_participants,
        medoid_summary=sample_medoid_summary,
        display_group_id=mock_cluster_regular.display_group_id
    )

    # Verify label is actual medoid text
    assert node.label_summary == sample_medoid_summary, \
        "label_summary must be actual medoid summary text (Intent Fidelity)"

    # Verify no truncation or transformation
    assert len(node.label_summary) > 0, \
        "label_summary cannot be empty"
    assert node.label_summary.strip() == sample_medoid_summary.strip(), \
        "label_summary must preserve original text exactly"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_member_count_to_user_count(mock_cluster_regular, sample_medoid_summary):
    """
    Test that cluster member_count maps to node.user_count.

    Contract Requirement:
    - node.user_count == len(cluster.members)
    - Represents number of participants in this cluster
    - Must be >= 1 (even for singleton clusters)

    Validates: FR-016 (Every participant assigned to exactly one cluster)
    """
    total_participants = 50

    node = await create_node_from_cluster(
        cluster=mock_cluster_regular,
        total_round_participants=total_participants,
        medoid_summary=sample_medoid_summary,
        display_group_id=mock_cluster_regular.display_group_id
    )

    # Verify user_count mapping
    assert node.user_count == len(mock_cluster_regular.members), \
        "user_count must equal cluster member count"
    assert node.user_count == 12, \
        "user_count should match fixture value"

    # Verify constraint
    assert node.user_count >= 1, \
        "user_count must be at least 1 (singleton clusters allowed)"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_user_pct_computation(mock_cluster_regular, sample_medoid_summary):
    """
    Test that user_pct is computed correctly: user_count / total_participants.

    Contract Requirement:
    - user_pct = user_count / total_round_participants
    - Computed per-round (Temporal Transparency - Principle IV)
    - Must be in range (0.0, 1.0]

    Validates: FR-015 (Percentage computation per round)
    """
    total_participants = 50
    expected_pct = 12 / 50  # 0.24

    node = await create_node_from_cluster(
        cluster=mock_cluster_regular,
        total_round_participants=total_participants,
        medoid_summary=sample_medoid_summary,
        display_group_id=mock_cluster_regular.display_group_id
    )

    # Verify user_pct computation
    assert node.user_pct == expected_pct, \
        f"user_pct must equal user_count / total_participants (got {node.user_pct}, expected {expected_pct})"
    assert node.user_pct == 0.24, \
        "user_pct should be 12/50 = 0.24"

    # Verify range constraints
    assert 0.0 < node.user_pct <= 1.0, \
        f"user_pct must be in range (0.0, 1.0], got {node.user_pct}"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_display_group_id_optional(mock_cluster_regular, sample_medoid_summary):
    """
    Test that display_group_id is correctly mapped (optional field).

    Contract Requirement:
    - node.display_group_id == cluster.display_group_id
    - Optional field (can be None for unaligned clusters)
    - Used for visual continuity across rounds (Spec 004 alignment)

    Validates: FR-037, FR-038 (Alignment is presentation-only)
    """
    total_participants = 50

    # Test with display_group_id present
    node_with_group = await create_node_from_cluster(
        cluster=mock_cluster_regular,
        total_round_participants=total_participants,
        medoid_summary=sample_medoid_summary,
        display_group_id=mock_cluster_regular.display_group_id
    )

    assert node_with_group.display_group_id == mock_cluster_regular.display_group_id, \
        "display_group_id must be mapped when provided"
    assert isinstance(node_with_group.display_group_id, UUID), \
        "display_group_id must be a UUID when present"

    # Test with display_group_id absent
    node_without_group = await create_node_from_cluster(
        cluster=mock_cluster_regular,
        total_round_participants=total_participants,
        medoid_summary=sample_medoid_summary,
        display_group_id=None
    )

    assert node_without_group.display_group_id is None, \
        "display_group_id can be None for unaligned clusters"


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.contract
async def test_singleton_cluster_conversion(mock_cluster_singleton):
    """
    Test conversion of singleton cluster (user_count = 1).

    Constitutional Requirement (Semantic Accuracy - Principle III):
    - Singleton clusters MUST be preserved (no minimum size constraint)
    - user_pct computed correctly even for 1 participant
    - No forced merging or hiding of minority viewpoints

    Validates: FR-012, FR-014, FR-015 (Singleton preservation)
    """
    total_participants = 50
    medoid_summary = "Unique minority perspective that must be preserved."

    node = await create_node_from_cluster(
        cluster=mock_cluster_singleton,
        total_round_participants=total_participants,
        medoid_summary=medoid_summary,
        display_group_id=mock_cluster_singleton.display_group_id
    )

    # Verify singleton properties
    assert node.user_count == 1, \
        "Singleton cluster must have user_count = 1"
    assert node.is_singleton(), \
        "is_singleton() must return True for user_count = 1"

    # Verify percentage computation for singleton
    expected_pct = 1 / 50  # 0.02
    assert node.user_pct == expected_pct, \
        f"Singleton user_pct must be 1/total_participants (got {node.user_pct}, expected {expected_pct})"
    assert node.user_pct == 0.02, \
        "Singleton user_pct should be 1/50 = 0.02"

    # Verify label preserved
    assert node.label_summary == medoid_summary, \
        "Singleton cluster label must be preserved"

    # Constitutional guarantee: No hiding or merging
    assert node.user_count >= 1, \
        "Singleton clusters must be visible (constitutional guarantee)"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_majority_cluster_conversion(mock_cluster_majority):
    """
    Test conversion of majority cluster (user_count > 50% of total).

    Contract Requirement:
    - Majority clusters handled same as regular clusters
    - No special treatment or capping of user_pct
    - Percentage reflects actual participation distribution

    Validates: FR-015 (Accurate percentage representation)
    """
    total_participants = 50
    medoid_summary = "Majority viewpoint representing consensus."

    node = await create_node_from_cluster(
        cluster=mock_cluster_majority,
        total_round_participants=total_participants,
        medoid_summary=medoid_summary,
        display_group_id=mock_cluster_majority.display_group_id
    )

    # Verify majority properties
    assert node.user_count == 30, \
        "Majority cluster user_count must be preserved"
    assert node.user_count > (total_participants / 2), \
        "Majority cluster has > 50% of participants"

    # Verify percentage computation for majority
    expected_pct = 30 / 50  # 0.60
    assert node.user_pct == expected_pct, \
        f"Majority user_pct must be user_count/total_participants (got {node.user_pct}, expected {expected_pct})"
    assert node.user_pct == 0.60, \
        "Majority user_pct should be 30/50 = 0.60"

    # Verify no special treatment
    assert node.user_pct <= 1.0, \
        "user_pct cannot exceed 1.0 even for majority"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_user_pct_precision():
    """
    Test that user_pct computation maintains floating-point precision.

    Contract Requirement:
    - user_pct computed with full floating-point precision
    - No rounding or truncation before storage
    - Sum of user_pct across round should equal 1.0 ± 0.0001

    Validates: SC-005 (Percentage sum validation)
    """
    # Create clusters with fractional percentages
    test_cases = [
        (1, 3, 1/3),    # 0.333...
        (1, 7, 1/7),    # 0.142857...
        (2, 9, 2/9),    # 0.222...
        (5, 13, 5/13),  # 0.384615...
    ]

    for user_count, total_participants, expected_pct in test_cases:
        # Create mock cluster
        cluster_id = uuid4()
        cluster = type('Cluster', (), {
            'id': cluster_id,
            'cluster_id': cluster_id,
            'user_count': user_count,
            'members': [type('Member', (), {'user_id': uuid4()})() for _ in range(user_count)],
            'display_group_id': None,
        })()

        node = await create_node_from_cluster(
            cluster=cluster,
            total_round_participants=total_participants,
            medoid_summary="Test summary",
            display_group_id=None
        )

        # Verify precision maintained
        assert abs(node.user_pct - expected_pct) < 1e-10, \
            f"user_pct precision lost: got {node.user_pct}, expected {expected_pct}"


# ============================================================================
# Validation Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.contract
async def test_invalid_cluster_raises_error(sample_medoid_summary):
    """
    Test that invalid cluster data raises appropriate errors.

    Contract Requirement:
    - cluster cannot be None
    - total_round_participants must be > 0
    - cluster must have at least 1 member

    Validates: Input validation in node_builder
    """
    total_participants = 50

    # Test None cluster
    with pytest.raises((ValueError, AttributeError)):
        await create_node_from_cluster(
            cluster=None,
            total_round_participants=total_participants,
            medoid_summary=sample_medoid_summary,
            display_group_id=None
        )

    # Test zero total_participants
    cluster_id = uuid4()
    mock_cluster = type('Cluster', (), {
        'id': cluster_id,
        'cluster_id': cluster_id,
        'user_count': 5,
        'members': [type('Member', (), {'user_id': uuid4()})() for _ in range(5)],
    })()

    with pytest.raises(ValueError, match="total_round_participants must be > 0"):
        await create_node_from_cluster(
            cluster=mock_cluster,
            total_round_participants=0,
            medoid_summary=sample_medoid_summary,
            display_group_id=None
        )

    # Test negative total_participants
    with pytest.raises(ValueError, match="total_round_participants must be > 0"):
        await create_node_from_cluster(
            cluster=mock_cluster,
            total_round_participants=-10,
            medoid_summary=sample_medoid_summary,
            display_group_id=None
        )


@pytest.mark.asyncio
@pytest.mark.contract
async def test_empty_cluster_raises_error(sample_medoid_summary):
    """
    Test that cluster with zero members raises error.

    Contract Requirement:
    - Every cluster must have at least 1 member
    - user_count must be >= 1

    Validates: FR-016 (Participant assignment validation)
    """
    total_participants = 50
    cluster_id = uuid4()

    # Create cluster with no members
    empty_cluster = type('Cluster', (), {
        'id': cluster_id,
        'cluster_id': cluster_id,
        'user_count': 0,
        'members': [],  # Empty members list
    })()

    with pytest.raises(ValueError, match="has no members"):
        await create_node_from_cluster(
            cluster=empty_cluster,
            total_round_participants=total_participants,
            medoid_summary=sample_medoid_summary,
            display_group_id=None
        )


@pytest.mark.asyncio
@pytest.mark.contract
async def test_pydantic_validation_passes(mock_cluster_regular, sample_medoid_summary):
    """
    Test that created SankeyNode passes Pydantic validation.

    Contract Requirement:
    - All fields must match SankeyNode schema
    - Type validation must pass
    - Constraint validation must pass (user_count >= 1, 0 < user_pct <= 1.0)

    Validates: SankeyNode model contract
    """
    total_participants = 50

    node = await create_node_from_cluster(
        cluster=mock_cluster_regular,
        total_round_participants=total_participants,
        medoid_summary=sample_medoid_summary,
        display_group_id=mock_cluster_regular.display_group_id
    )

    # Verify Pydantic model validation
    assert isinstance(node, SankeyNode), \
        "Result must be a SankeyNode instance"

    # Verify all required fields present
    assert node.node_id is not None, "node_id is required"
    assert node.cluster_id is not None, "cluster_id is required"
    assert node.label_summary is not None, "label_summary is required"
    assert node.user_count is not None, "user_count is required"
    assert node.user_pct is not None, "user_pct is required"

    # Verify field types
    assert isinstance(node.node_id, UUID), "node_id must be UUID"
    assert isinstance(node.cluster_id, UUID), "cluster_id must be UUID"
    assert isinstance(node.label_summary, str), "label_summary must be str"
    assert isinstance(node.user_count, int), "user_count must be int"
    assert isinstance(node.user_pct, float), "user_pct must be float"

    # Verify constraints
    assert node.user_count >= 1, "user_count must be >= 1"
    assert 0.0 < node.user_pct <= 1.0, "user_pct must be in (0.0, 1.0]"
    assert len(node.label_summary.strip()) > 0, "label_summary cannot be empty"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_node_serialization(mock_cluster_regular, sample_medoid_summary):
    """
    Test that SankeyNode can be serialized to JSON.

    Contract Requirement:
    - SankeyNode must be JSON-serializable for API responses
    - All UUIDs must serialize to strings
    - Deserialization must reconstruct identical node

    Validates: SankeyNode contract for API layer
    """
    total_participants = 50

    node = await create_node_from_cluster(
        cluster=mock_cluster_regular,
        total_round_participants=total_participants,
        medoid_summary=sample_medoid_summary,
        display_group_id=mock_cluster_regular.display_group_id
    )

    # Serialize to JSON
    node_dict = node.model_dump()
    assert isinstance(node_dict, dict), "model_dump() must return dict"

    node_json = node.model_dump_json()
    assert isinstance(node_json, str), "model_dump_json() must return str"

    # Deserialize and verify
    reconstructed = SankeyNode(**node_dict)
    assert reconstructed.node_id == node.node_id, "Deserialization must preserve node_id"
    assert reconstructed.cluster_id == node.cluster_id, "Deserialization must preserve cluster_id"
    assert reconstructed.label_summary == node.label_summary, "Deserialization must preserve label_summary"
    assert reconstructed.user_count == node.user_count, "Deserialization must preserve user_count"
    assert reconstructed.user_pct == node.user_pct, "Deserialization must preserve user_pct"
    assert reconstructed.display_group_id == node.display_group_id, "Deserialization must preserve display_group_id"


# ============================================================================
# Constitutional Guarantee Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.contract
async def test_semantic_accuracy_all_clusters_preserved():
    """
    Test that ALL clusters are converted to nodes (100% coverage).

    Constitutional Requirement (Semantic Accuracy - Principle III):
    - Every cluster must become a node
    - No filtering or hiding of clusters
    - No minimum size constraint (singletons preserved)

    Validates: Semantic Accuracy constitutional guarantee
    """
    # Create diverse set of clusters
    total_participants = 100
    clusters = [
        # Majority cluster
        (50, "Majority consensus viewpoint"),
        # Regular clusters
        (20, "Alternative perspective A"),
        (15, "Alternative perspective B"),
        (10, "Minority viewpoint"),
        # Small clusters
        (3, "Small cluster"),
        (1, "Singleton outlier A"),
        (1, "Singleton outlier B"),
    ]

    nodes = []
    for user_count, summary in clusters:
        cluster_id = uuid4()
        mock_cluster = type('Cluster', (), {
            'id': cluster_id,
            'cluster_id': cluster_id,
            'user_count': user_count,
            'members': [type('Member', (), {'user_id': uuid4()})() for _ in range(user_count)],
            'display_group_id': uuid4() if user_count > 1 else None,
        })()

        node = await create_node_from_cluster(
            cluster=mock_cluster,
            total_round_participants=total_participants,
            medoid_summary=summary,
            display_group_id=mock_cluster.display_group_id
        )
        nodes.append(node)

    # Verify all clusters converted
    assert len(nodes) == len(clusters), \
        f"All {len(clusters)} clusters must be converted to nodes (got {len(nodes)})"

    # Verify 100% participant coverage
    total_users = sum(node.user_count for node in nodes)
    assert total_users == total_participants, \
        f"Total user_count across nodes must equal total_participants (got {total_users}, expected {total_participants})"

    # Verify percentage sum = 1.0
    total_pct = sum(node.user_pct for node in nodes)
    assert abs(total_pct - 1.0) < 0.0001, \
        f"Total user_pct must sum to 1.0 ± 0.0001 (got {total_pct})"

    # Verify singletons preserved
    singleton_nodes = [n for n in nodes if n.is_singleton()]
    assert len(singleton_nodes) == 2, \
        "Both singleton clusters must be preserved (constitutional guarantee)"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_intent_fidelity_actual_participant_text():
    """
    Test that node labels use actual participant text (no LLM generation).

    Constitutional Requirement (Intent Fidelity - Principle II):
    - Labels must be actual medoid summary text
    - No LLM generation or transformation
    - Preserves participant voice

    Validates: Intent Fidelity constitutional guarantee
    """
    # Test with various medoid summary texts
    test_summaries = [
        "I strongly believe we need immediate climate action.",
        "Economic growth should be our top priority right now.",
        "We must balance environmental and economic concerns carefully.",
        "Unique perspective: solar panels on every building by 2030.",
    ]

    total_participants = 50

    for medoid_summary in test_summaries:
        cluster_id = uuid4()
        mock_cluster = type('Cluster', (), {
            'id': cluster_id,
            'cluster_id': cluster_id,
            'user_count': 10,
            'members': [type('Member', (), {'user_id': uuid4()})() for _ in range(10)],
            'display_group_id': uuid4(),
        })()

        node = await create_node_from_cluster(
            cluster=mock_cluster,
            total_round_participants=total_participants,
            medoid_summary=medoid_summary,
            display_group_id=mock_cluster.display_group_id
        )

        # Verify exact text preservation
        assert node.label_summary == medoid_summary, \
            f"Node label must be exact medoid text (Intent Fidelity)"

        # Verify no transformation applied
        assert node.label_summary.strip() == medoid_summary.strip(), \
            "No whitespace transformation allowed"
        assert len(node.label_summary) == len(medoid_summary), \
            "No truncation or expansion allowed"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_temporal_transparency_per_round_percentage():
    """
    Test that user_pct is computed per-round (no cross-round normalization).

    Constitutional Requirement (Temporal Transparency - Principle IV):
    - Percentages computed within each round independently
    - No normalization across rounds
    - Each round's percentages sum to 1.0

    Validates: Temporal Transparency constitutional guarantee
    """
    # Simulate two rounds with different participant counts
    round1_participants = 50
    round2_participants = 30  # Different total

    # Round 1: Create nodes with percentages
    round1_clusters = [(25, "Viewpoint A"), (15, "Viewpoint B"), (10, "Viewpoint C")]
    round1_nodes = []

    for user_count, summary in round1_clusters:
        cluster_id = uuid4()
        mock_cluster = type('Cluster', (), {
            'id': cluster_id,
            'cluster_id': cluster_id,
            'user_count': user_count,
            'members': [type('Member', (), {'user_id': uuid4()})() for _ in range(user_count)],
            'display_group_id': uuid4(),
        })()

        node = await create_node_from_cluster(
            cluster=mock_cluster,
            total_round_participants=round1_participants,
            medoid_summary=summary,
            display_group_id=mock_cluster.display_group_id
        )
        round1_nodes.append(node)

    # Round 2: Create nodes with different total
    round2_clusters = [(20, "Viewpoint X"), (10, "Viewpoint Y")]
    round2_nodes = []

    for user_count, summary in round2_clusters:
        cluster_id = uuid4()
        mock_cluster = type('Cluster', (), {
            'id': cluster_id,
            'cluster_id': cluster_id,
            'user_count': user_count,
            'members': [type('Member', (), {'user_id': uuid4()})() for _ in range(user_count)],
            'display_group_id': uuid4(),
        })()

        node = await create_node_from_cluster(
            cluster=mock_cluster,
            total_round_participants=round2_participants,
            medoid_summary=summary,
            display_group_id=mock_cluster.display_group_id
        )
        round2_nodes.append(node)

    # Verify Round 1 percentages sum to 1.0
    round1_total_pct = sum(n.user_pct for n in round1_nodes)
    assert abs(round1_total_pct - 1.0) < 0.0001, \
        f"Round 1 percentages must sum to 1.0 (got {round1_total_pct})"

    # Verify Round 2 percentages sum to 1.0 (independent of Round 1)
    round2_total_pct = sum(n.user_pct for n in round2_nodes)
    assert abs(round2_total_pct - 1.0) < 0.0001, \
        f"Round 2 percentages must sum to 1.0 (got {round2_total_pct})"

    # Verify same user_count has different user_pct in different rounds
    # (10 users in round1 = 10/50 = 0.20, 10 users in round2 = 10/30 = 0.333...)
    round1_10users = round1_nodes[2]  # 10 users
    round2_10users = round2_nodes[1]  # 10 users

    assert round1_10users.user_count == round2_10users.user_count == 10, \
        "Both nodes have 10 users"
    assert round1_10users.user_pct != round2_10users.user_pct, \
        "Same user_count must have different user_pct in rounds with different totals (Temporal Transparency)"
    assert round1_10users.user_pct == 0.20, \
        "Round 1: 10/50 = 0.20"
    assert abs(round2_10users.user_pct - (10/30)) < 0.0001, \
        "Round 2: 10/30 = 0.333..."

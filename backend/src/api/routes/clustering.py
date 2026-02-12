"""
Clustering API endpoints for Semantic Clustering Protocol (Spec 004).

Implements T029-T033:
- T029: POST /api/v1/clusters/trigger endpoint
- T030: Input validation for approved summaries
- T031: Idempotency check
- T032: GET /api/v1/clusters endpoint
- T033: GET /api/v1/clusters/{cluster_id} endpoint
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from uuid import UUID
from typing import List, Optional
from datetime import datetime
import time
import logging
import uuid

from pydantic import BaseModel, Field

from src.database import get_db
from src.models.approved_summary import ApprovedSummary
from src.models.cluster import Cluster
from src.models.round import Round

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clusters", tags=["clustering"])


# ============================================================================
# Request/Response Schemas
# ============================================================================

class ClusteringRequest(BaseModel):
    """Request model for POST /clusters/trigger."""
    round_id: UUID = Field(..., description="Round to cluster")
    force_recluster: bool = Field(
        default=False,
        description="Force reclustering if already computed"
    )

    model_config = {"from_attributes": True}


class ClusteringResponse(BaseModel):
    """Response model for POST /clusters/trigger."""
    job_id: UUID = Field(..., description="Async job identifier")
    round_id: UUID
    status: str = Field(..., description="PROCESSING | COMPLETED | FAILED")
    estimated_completion_ms: int = Field(..., description="Estimated time to completion")
    message: str

    model_config = {"from_attributes": True}


class ClusterMemberResponse(BaseModel):
    """Member summary in a cluster."""
    summary_id: UUID
    user_id: UUID
    summary_text: str

    model_config = {"from_attributes": True}


class ClusterResponse(BaseModel):
    """Cluster (thought space) response."""
    cluster_id: UUID
    user_count: int = Field(..., description="Number of participants in cluster")
    user_pct: float = Field(..., description="Percentage of total participants (0-1)")
    label_summary: str = Field(..., description="Medoid summary text")
    label_summary_id: Optional[UUID] = Field(None, description="Summary ID of medoid (if available)")
    display_group_id: Optional[UUID] = Field(
        None,
        description="Visual grouping ID (from alignment, null if not aligned)"
    )
    centroid_vector: Optional[List[float]] = Field(
        None,
        description="384-dimensional centroid vector"
    )

    model_config = {"from_attributes": True}


class ClusterListResponse(BaseModel):
    """List of clusters for a round."""
    round_id: UUID
    cluster_count: int = Field(..., description="Number of thought spaces")
    total_participants: int = Field(..., description="Total participants in round")
    percentage_sum: float = Field(..., description="Sum of user_pct (should be 1.0)")
    clusters: List[ClusterResponse]

    model_config = {"from_attributes": True}


class ClusterDetailResponse(BaseModel):
    """Detailed cluster information including members."""
    cluster_id: UUID
    round_id: UUID
    user_count: int
    user_pct: float
    label_summary: str
    label_summary_id: Optional[UUID] = None
    centroid_vector: Optional[List[float]] = None
    display_group_id: Optional[UUID] = None
    members: List[ClusterMemberResponse]

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    details: Optional[dict] = None

    model_config = {"from_attributes": True}


# ============================================================================
# T029: POST /api/v1/clusters/trigger endpoint
# ============================================================================

@router.post(
    "/trigger",
    response_model=ClusteringResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        409: {"model": ErrorResponse, "description": "Clustering already exists"},
    }
)
async def trigger_clustering(
    request: ClusteringRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger clustering for a round (T029).

    Initiates clustering workflow for approved summaries in a round.

    Workflow:
    1. Fetch approved summaries from Spec 3
    2. Generate SBERT embeddings (all-MiniLM-L6-v2)
    3. Run HDBSCAN clustering (variable K, min_cluster_size=2)
    4. Convert outliers to singleton clusters
    5. Compute centroids and select medoid labels
    6. Persist clusters to database

    Performance: Completes in < 5 seconds for 100 participants (SC-001)

    Args:
        request: Clustering request with round_id and force_recluster flag
        db: Database session

    Returns:
        ClusteringResponse with job details

    Raises:
        HTTPException 400: No approved summaries in round
        HTTPException 409: Clustering already exists (unless force_recluster=true)
    """
    start_time = time.time()

    logger.info(
        f"Clustering trigger request received for round_id={request.round_id}, "
        f"force_recluster={request.force_recluster}"
    )

    # T030: Input validation - Check if round exists
    round_result = await db.execute(
        select(Round).where(Round.round_id == request.round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "ROUND_NOT_FOUND",
                "message": f"Round {request.round_id} not found"
            }
        )

    # T030: Input validation - Check for approved summaries
    approved_count_result = await db.execute(
        select(func.count(ApprovedSummary.summary_id))
        .where(ApprovedSummary.round_id == request.round_id)
    )
    approved_count = approved_count_result.scalar()

    if approved_count == 0:
        logger.warning(f"No approved summaries found for round_id={request.round_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "NO_APPROVED_SUMMARIES",
                "message": "Round has no approved summaries. Clustering cannot proceed.",
                "details": {
                    "round_id": str(request.round_id),
                    "approved_count": 0
                }
            }
        )

    # T031: Idempotency check - Check if clustering already exists
    existing_clusters_result = await db.execute(
        select(func.count(Cluster.cluster_id))
        .where(Cluster.round_id == request.round_id)
    )
    existing_cluster_count = existing_clusters_result.scalar()

    if existing_cluster_count > 0 and not request.force_recluster:
        logger.warning(
            f"Clustering already exists for round_id={request.round_id} "
            f"with {existing_cluster_count} clusters"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "CLUSTERING_EXISTS",
                "message": "Clustering already computed for this round. Use force_recluster=true to override.",
                "details": {
                    "round_id": str(request.round_id),
                    "cluster_count": existing_cluster_count
                }
            }
        )

    # If force_recluster=true and clusters exist, delete existing clusters
    if existing_cluster_count > 0 and request.force_recluster:
        logger.info(
            f"Force reclustering: Deleting {existing_cluster_count} existing clusters "
            f"for round_id={request.round_id}"
        )
        await db.execute(
            text("DELETE FROM clusters WHERE round_id = :round_id")
            .bindparams(round_id=request.round_id)
        )
        await db.commit()

    # Generate job_id for async tracking
    job_id = uuid.uuid4()

    try:
        # Execute full clustering workflow (T019-T037)
        await execute_full_clustering_workflow(
            round_id=request.round_id,
            db=db
        )

        estimated_completion_ms = int(approved_count * 50)  # ~50ms per summary estimate

        logger.info(
            f"Clustering completed for round_id={request.round_id}, "
            f"job_id={job_id}, "
            f"approved_summaries={approved_count}"
        )

        return ClusteringResponse(
            job_id=job_id,
            round_id=request.round_id,
            status="COMPLETED",
            estimated_completion_ms=0,
            message=f"Clustering completed for {approved_count} approved summaries"
        )

    except Exception as e:
        logger.error(
            f"Clustering failed for round_id={request.round_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "CLUSTERING_FAILED",
                "message": f"Clustering workflow failed: {str(e)}",
                "details": {
                    "round_id": str(request.round_id),
                    "job_id": str(job_id)
                }
            }
        )


# ============================================================================
# T032: GET /api/v1/clusters endpoint
# ============================================================================

@router.get(
    "",
    response_model=ClusterListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Round not found or not yet clustered"}
    }
)
async def get_clusters(
    round_id: UUID = Query(..., description="Round to fetch clusters for"),
    include_members: bool = Query(
        default=False,
        description="Include member details (default false)"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get thought spaces for a round (T032).

    Returns all thought spaces (clusters) for a specified round.

    Output Guarantees (per spec):
    - 100% participant coverage (SC-003)
    - User percentages sum to 1.0 ± 0.0001 (SC-005)
    - Medoid labels from actual participant language (FR-024)
    - Centroids included for Sankey flow calculation (FR-028)

    Args:
        round_id: Round to fetch clusters for
        include_members: Include member details (default false)
        db: Database session

    Returns:
        ClusterListResponse with all clusters for the round

    Raises:
        HTTPException 404: Round not found or not yet clustered
    """
    logger.info(f"GET clusters request for round_id={round_id}")

    # Check if round exists
    round_result = await db.execute(
        select(Round).where(Round.round_id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "ROUND_NOT_FOUND",
                "message": f"Round {round_id} not found"
            }
        )

    # Fetch clusters for round
    clusters_result = await db.execute(
        select(Cluster)
        .where(Cluster.round_id == round_id)
        .order_by(Cluster.user_count.desc())  # Order by size
    )
    clusters = clusters_result.scalars().all()

    if not clusters:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_CLUSTERED",
                "message": f"Round {round_id} has not been clustered yet",
                "details": {
                    "round_id": str(round_id)
                }
            }
        )

    # Calculate total participants and percentage sum
    total_participants = sum(c.user_count for c in clusters)
    percentage_sum = sum(c.user_pct for c in clusters)

    # Build response
    cluster_responses = []
    for cluster in clusters:
        # Get label summary text
        label_text = cluster.label_summary.summary_text if cluster.label_summary else None

        # Parse centroid_vector from JSON
        centroid_vector = None
        if cluster.centroid_vector:
            import json
            if isinstance(cluster.centroid_vector, str):
                centroid_vector = json.loads(cluster.centroid_vector)
            else:
                centroid_vector = cluster.centroid_vector

        # Get label_summary_id if it exists
        label_summary_id = None
        if hasattr(cluster, 'label_summary_id'):
            label_summary_id = cluster.label_summary_id

        cluster_responses.append(
            ClusterResponse(
                cluster_id=cluster.cluster_id,
                user_count=cluster.user_count,
                user_pct=cluster.user_pct,
                label_summary=label_text or "",
                label_summary_id=label_summary_id,
                display_group_id=cluster.display_group_id,
                centroid_vector=centroid_vector
            )
        )

    logger.info(
        f"Returning {len(clusters)} clusters for round_id={round_id}, "
        f"total_participants={total_participants}, "
        f"percentage_sum={percentage_sum:.4f}"
    )

    return ClusterListResponse(
        round_id=round_id,
        cluster_count=len(clusters),
        total_participants=total_participants,
        percentage_sum=percentage_sum,
        clusters=cluster_responses
    )


# ============================================================================
# T033: GET /api/v1/clusters/{cluster_id} endpoint
# ============================================================================

@router.get(
    "/{cluster_id}",
    response_model=ClusterDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Cluster not found"}
    }
)
async def get_cluster(
    cluster_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get specific thought space details (T033).

    Returns detailed information about a specific thought space including
    all member summaries and user IDs.

    Args:
        cluster_id: UUID of the cluster to fetch
        db: Database session

    Returns:
        ClusterDetailResponse with cluster details and all members

    Raises:
        HTTPException 404: Cluster not found
    """
    logger.info(f"GET cluster request for cluster_id={cluster_id}")

    # Fetch cluster
    cluster_result = await db.execute(
        select(Cluster).where(Cluster.cluster_id == cluster_id)
    )
    cluster = cluster_result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "CLUSTER_NOT_FOUND",
                "message": f"Cluster {cluster_id} not found"
            }
        )

    # Get label summary text
    label_text = cluster.label_summary.summary_text if cluster.label_summary else None

    # Fetch all member summaries
    members_result = await db.execute(
        select(ApprovedSummary)
        .where(ApprovedSummary.cluster_id == cluster_id)
        .order_by(ApprovedSummary.approved_at)
    )
    member_summaries = members_result.scalars().all()

    # Build member responses
    member_responses = []
    for member in member_summaries:
        member_responses.append(
            ClusterMemberResponse(
                summary_id=member.summary_id,
                user_id=member.participant_id,  # Using participant_id as user_id
                summary_text=member.summary_text
            )
        )

    # Parse centroid_vector from JSON
    centroid_vector = None
    if cluster.centroid_vector:
        import json
        if isinstance(cluster.centroid_vector, str):
            centroid_vector = json.loads(cluster.centroid_vector)
        else:
            centroid_vector = cluster.centroid_vector

    # Get label_summary_id if it exists
    label_summary_id = None
    if hasattr(cluster, 'label_summary_id'):
        label_summary_id = cluster.label_summary_id

    logger.info(
        f"Returning cluster details for cluster_id={cluster_id}, "
        f"members={len(member_responses)}"
    )

    return ClusterDetailResponse(
        cluster_id=cluster.cluster_id,
        round_id=cluster.round_id,
        user_count=cluster.user_count,
        user_pct=cluster.user_pct,
        label_summary=label_text or "",
        label_summary_id=label_summary_id,
        centroid_vector=centroid_vector,
        display_group_id=cluster.display_group_id,
        members=member_responses
    )


# ============================================================================
# Full Clustering Workflow (T019-T037)
# ============================================================================

async def execute_full_clustering_workflow(
    round_id: UUID,
    db: AsyncSession
) -> None:
    """
    Execute complete clustering workflow from approved summaries to persisted clusters.

    Implements T029: Complete clustering workflow with all steps:
    1. Fetch approved summaries (T030 validation)
    2. Generate embeddings (T019-T021)
    3. Run HDBSCAN clustering (T022-T023)
    4. Handle outliers as singletons (T024)
    5. Compute centroids (T025-T026)
    6. Calculate cluster statistics (T027)
    7. Select medoid labels (T065)
    8. Persist clusters (T028)
    9. Publish clustering.completed event (T034)

    Args:
        round_id: UUID of the round to cluster
        db: Database session

    Raises:
        RuntimeError: If any step fails
    """
    import numpy as np
    from src.services.embedding_service import get_or_generate_embeddings
    from src.services.clustering_service import (
        cluster_embeddings,
        calculate_cluster_stats,
        persist_clusters,
    )
    from src.services.outlier_handler import convert_outliers_to_singletons
    from src.services.centroid_service import compute_centroids
    from src.services.medoid_labeling import compute_medoid
    from src.services.event_service import get_clustering_event_service
    import time

    workflow_start = time.time()

    logger.info(f"[WORKFLOW_START] round_id={round_id}")

    # Step 1: Fetch approved summaries (T030)
    summaries_result = await db.execute(
        select(ApprovedSummary).where(ApprovedSummary.round_id == round_id)
    )
    summaries = summaries_result.scalars().all()

    if not summaries:
        raise RuntimeError(f"No approved summaries found for round {round_id}")

    summary_data = [
        {
            "summary_id": s.summary_id,
            "summary_text": s.summary_text,
            "participant_id": s.participant_id
        }
        for s in summaries
    ]
    summary_ids = [s.summary_id for s in summaries]

    logger.info(f"[STEP:FETCH] Found {len(summaries)} approved summaries")

    # Step 2: Generate embeddings (T019-T021)
    embeddings_dict = await get_or_generate_embeddings(db, summary_data)

    # Convert to numpy array for clustering
    embeddings_array = np.array([embeddings_dict[sid] for sid in summary_ids])

    logger.info(f"[STEP:EMBEDDINGS] Generated {len(embeddings_dict)} embeddings")

    # Step 3: Run HDBSCAN clustering with Miller's Law adaptive parameters
    from src.ml.clustering_algorithms import compute_adaptive_parameters
    from src.config import settings

    # Compute adaptive parameters if enabled
    if settings.clustering_adaptive_enabled:
        adaptive_params = compute_adaptive_parameters(len(summary_ids))
        min_cluster_size = adaptive_params['min_cluster_size']
        logger.info(f"[MILLER'S_LAW] Using adaptive min_cluster_size={min_cluster_size} for {len(summary_ids)} participants")
    else:
        min_cluster_size = 2

    cluster_assignments = await cluster_embeddings(
        embeddings=embeddings_array,
        summary_ids=summary_ids,
        min_cluster_size=min_cluster_size
    )

    logger.info(f"[STEP:CLUSTERING] Clustered {len(cluster_assignments)} summaries into {len(set(cluster_assignments.values()))} initial clusters")

    # Step 4: Compute centroids BEFORE outlier handling (needed for smart reassignment)
    centroids = compute_centroids(cluster_assignments, embeddings_dict)
    logger.info(f"[STEP:CENTROIDS] Computed {len(centroids)} centroids")

    # Step 5: Handle outliers with smart noise reassignment (Miller's Law)
    # Convert cluster_assignments to numpy array for outlier handling
    cluster_labels = np.array([cluster_assignments[sid] for sid in summary_ids])

    if settings.clustering_adaptive_enabled:
        # Use smart noise reassignment
        cluster_labels_updated, singleton_count = convert_outliers_to_singletons(
            cluster_labels=cluster_labels,
            embeddings=embeddings_dict,
            centroids=centroids,
            summary_ids=summary_ids,
            similarity_threshold=settings.clustering_noise_reassignment_threshold,
            use_smart_reassignment=True
        )
        logger.info(f"[MILLER'S_LAW] Smart noise reassignment: {singleton_count} distinct voice singletons")
    else:
        # Fall back to simple singleton conversion
        cluster_labels_updated, singleton_count = convert_outliers_to_singletons(cluster_labels)
        logger.info(f"[STEP:OUTLIERS] Converted {singleton_count} outliers to singletons")

    # Update cluster_assignments with singleton conversions
    for i, sid in enumerate(summary_ids):
        cluster_assignments[sid] = int(cluster_labels_updated[i])

    # Step 6: Recompute centroids after outlier handling
    centroids = compute_centroids(cluster_assignments, embeddings_dict)
    logger.info(f"[STEP:CENTROIDS_UPDATED] Recomputed {len(centroids)} centroids after outlier handling")

    # Step 6.5: Calculate initial cluster statistics for merge step
    cluster_stats = await calculate_cluster_stats(cluster_assignments, db)
    logger.info(f"[STEP:STATS_INITIAL] Calculated statistics for {len(cluster_stats)} clusters before merge")

    # Step 7: Merge near-duplicate clusters (Miller's Law)
    from src.services.clustering_service import merge_near_duplicate_clusters

    if settings.clustering_adaptive_enabled and len(centroids) > 1:
        pre_merge_count = len(centroids)
        cluster_assignments, centroids, cluster_stats = merge_near_duplicate_clusters(
            cluster_assignments=cluster_assignments,
            centroids=centroids,
            cluster_stats=cluster_stats,
            similarity_threshold=settings.clustering_merge_threshold
        )
        post_merge_count = len(centroids)
        logger.info(f"[MILLER'S_LAW] Centroid merge: {pre_merge_count} -> {post_merge_count} clusters (threshold={settings.clustering_merge_threshold})")
    else:
        logger.info(f"[STEP:MERGE_SKIPPED] Skipped centroid merge (adaptive={settings.clustering_adaptive_enabled}, clusters={len(centroids)})")

    # Step 8: Recalculate cluster statistics after merge
    cluster_stats = await calculate_cluster_stats(cluster_assignments, db)
    logger.info(f"[STEP:STATS_FINAL] Final statistics for {len(cluster_stats)} clusters after merge")

    # Step 9: Select medoid labels (T065)
    label_summaries = {}
    for cluster_label in centroids.keys():
        # Get member embeddings for this cluster
        member_embeddings = [
            (sid, embeddings_dict[sid])
            for sid, label in cluster_assignments.items()
            if label == cluster_label
        ]

        # Generate fake cluster_id for medoid computation (will be replaced during persistence)
        temp_cluster_id = uuid.uuid4()

        # Compute medoid
        medoid_id = compute_medoid(
            cluster_id=temp_cluster_id,
            centroid_vector=centroids[cluster_label],
            member_embeddings=member_embeddings
        )

        label_summaries[cluster_label] = medoid_id

    logger.info(f"[STEP:MEDOIDS] Selected {len(label_summaries)} medoid labels")

    # Step 10: Persist clusters (T028)
    cluster_id_map = await persist_clusters(
        round_id=round_id,
        cluster_assignments=cluster_assignments,
        cluster_stats=cluster_stats,
        centroids=centroids,
        label_summaries=label_summaries,
        db=db
    )

    logger.info(f"[STEP:PERSIST] Persisted {len(cluster_id_map)} clusters (Miller's Law: 7±2 target)")

    # Calculate minority cluster count (T041: clusters with 1-2 participants)
    minority_cluster_count = sum(
        1 for user_count, _ in cluster_stats.values()
        if user_count <= 2
    )
    logger.info(f"[STEP:METRICS] minority_cluster_count={minority_cluster_count}")

    # Step 9: Publish clustering.completed event (T034, T041)
    workflow_duration_ms = (time.time() - workflow_start) * 1000

    try:
        event_service = await get_clustering_event_service()
        await event_service.publish_clustering_completed(
            round_id=round_id,
            cluster_count=len(cluster_id_map),
            total_participants=len(summaries),
            singleton_count=singleton_count,
            processing_time_ms=workflow_duration_ms,
            cluster_ids=list(cluster_id_map.values()),
            minority_cluster_count=minority_cluster_count  # T041
        )
        logger.info(f"[STEP:EVENT] Published clustering.completed event")
    except Exception as e:
        logger.warning(f"[STEP:EVENT] Failed to publish event: {e}")
        # Don't fail the workflow if event publishing fails

    logger.info(
        f"[WORKFLOW_COMPLETE] round_id={round_id} "
        f"duration_ms={workflow_duration_ms:.2f} "
        f"clusters={len(cluster_id_map)} "
        f"participants={len(summaries)}"
    )


# ============================================================================
# Clustering Inspector API (Phase 2: Developer Tools)
# ============================================================================

class InspectorRow(BaseModel):
    """Single row in clustering inspector table."""
    participant_number: int = Field(description="Anonymous participant number (1-N)")
    original_submission: Optional[str] = Field(
        None,
        description="Original submission text (may be deleted per TTL)"
    )
    summary_text: str
    cluster_id: Optional[UUID]
    cluster_label: Optional[str] = Field(None, description="Medoid summary text")
    similarity_to_centroid: Optional[float] = Field(
        None,
        description="Cosine similarity to cluster centroid [0-1]"
    )
    is_singleton: bool

    model_config = {"from_attributes": True}


class ClusterQualityMetricResponse(BaseModel):
    """Quality metrics for clustering result."""
    silhouette_score: Optional[float] = Field(
        None,
        description="Silhouette score: [-1, 1], higher is better"
    )
    davies_bouldin_index: Optional[float] = Field(
        None,
        description="Davies-Bouldin index: [0, ∞], lower is better"
    )
    near_duplicate_count: int = Field(
        description="Count of cluster pairs with >0.8 similarity"
    )
    singleton_count: int = Field(description="Number of single-member clusters")
    avg_cluster_size: float

    model_config = {"from_attributes": True}


class NearDuplicatePair(BaseModel):
    """Pair of near-duplicate clusters."""
    cluster_id_1: UUID
    cluster_id_2: UUID
    similarity: float
    label_1: str
    label_2: str

    model_config = {"from_attributes": True}


class ClusterInspectorResponse(BaseModel):
    """Complete clustering inspector data for a round."""
    round_id: UUID
    round_number: int
    question_text: str
    total_participants: int
    cluster_count: int
    rows: List[InspectorRow]
    quality_metrics: Optional[ClusterQualityMetricResponse]
    near_duplicate_pairs: List[NearDuplicatePair]

    model_config = {"from_attributes": True}


@router.get(
    "/inspector/discussions/{discussion_id}/rounds",
    tags=["developer-tools"]
)
async def get_discussion_rounds(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all rounds for a discussion (for inspector round selector).

    Helper endpoint for clustering inspector to populate round dropdown.
    """
    from src.models.discussion import Discussion

    # Verify discussion exists
    discussion_result = await db.execute(
        select(Discussion).where(Discussion.discussion_id == discussion_id)
    )
    discussion = discussion_result.scalar_one_or_none()

    if not discussion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DISCUSSION_NOT_FOUND", "message": f"Discussion {discussion_id} not found"}
        )

    # Fetch all rounds
    rounds_result = await db.execute(
        select(Round)
        .where(Round.discussion_id == discussion_id)
        .order_by(Round.round_num)
    )
    rounds = rounds_result.scalars().all()

    return {
        "discussion_id": discussion_id,
        "rounds": [
            {
                "round_id": str(r.round_id),
                "round_number": r.round_num,
                "question_text": r.question_text
            }
            for r in rounds
        ]
    }


@router.get(
    "/inspector/rounds/{round_id}",
    response_model=ClusterInspectorResponse,
    tags=["developer-tools"],
    responses={
        404: {"model": ErrorResponse, "description": "Round not found"},
    }
)
async def get_clustering_inspector_data(
    round_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive clustering data for developer inspection.

    Developer tool for validating clustering quality and debugging issues.
    Shows all participants with their original text (if available), summaries,
    cluster assignments, and similarity scores.

    WARNING: This endpoint exposes participant data and should only be accessible
    in development mode or to authorized administrators.

    Args:
        round_id: Round to inspect
        db: Database session

    Returns:
        ClusterInspectorResponse with all inspection data

    Raises:
        HTTPException 404: Round not found
    """
    logger.info(f"[INSPECTOR] Fetching clustering inspector data for round_id={round_id}")

    # Fetch round info
    round_result = await db.execute(
        select(Round).where(Round.round_id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "ROUND_NOT_FOUND",
                "message": f"Round {round_id} not found"
            }
        )

    # Fetch approved summaries with cluster assignments
    from src.models.approved_summary import ApprovedSummary
    from src.models.submission import Submission
    from src.models.cluster_quality_metrics import ClusterQualityMetric

    summaries_result = await db.execute(
        select(ApprovedSummary)
        .where(ApprovedSummary.round_id == round_id)
        .order_by(ApprovedSummary.approved_at)
    )
    summaries = summaries_result.scalars().all()

    if not summaries:
        logger.warning(f"[INSPECTOR] No summaries found for round_id={round_id}")
        return ClusterInspectorResponse(
            round_id=round_id,
            round_number=round_obj.round_number,
            question_text=round_obj.question_text,
            total_participants=0,
            cluster_count=0,
            rows=[],
            quality_metrics=None,
            near_duplicate_pairs=[]
        )

    # Fetch clusters for this round
    clusters_result = await db.execute(
        select(Cluster)
        .where(Cluster.round_id == round_id)
    )
    clusters = {c.cluster_id: c for c in clusters_result.scalars().all()}

    # Fetch embeddings for similarity computation
    from src.models.embedding import Embedding
    import numpy as np
    from numpy.linalg import norm

    embeddings_result = await db.execute(
        select(Embedding)
        .where(Embedding.summary_id.in_([s.summary_id for s in summaries]))
    )
    embeddings_map = {e.summary_id: e.embedding_vector for e in embeddings_result.scalars().all()}

    # Build inspector rows with anonymous participant numbers
    rows = []
    participant_map = {}  # Map participant_id to anonymous number
    next_number = 1

    for summary in summaries:
        # Assign anonymous participant number
        if summary.participant_id not in participant_map:
            participant_map[summary.participant_id] = next_number
            next_number += 1

        # Try to get original submission
        submission_result = await db.execute(
            select(Submission)
            .where(
                Submission.participant_id == summary.participant_id,
                Submission.round_id == round_id
            )
            .order_by(Submission.submitted_at.desc())
        )
        submission = submission_result.scalar_one_or_none()
        original_text = submission.submission_text if submission else None

        # Get cluster info
        cluster = clusters.get(summary.cluster_id) if summary.cluster_id else None
        cluster_label = cluster.label_summary if cluster else None
        is_singleton = cluster.user_count == 1 if cluster else False

        # Compute similarity to centroid
        similarity_to_centroid = None
        if cluster and cluster.centroid_vector and summary.summary_id in embeddings_map:
            centroid = np.array(cluster.centroid_vector, dtype=np.float32)
            embedding = np.array(embeddings_map[summary.summary_id], dtype=np.float32)

            # Cosine similarity (vectors are already normalized)
            similarity_to_centroid = float(np.dot(centroid, embedding))

        rows.append(InspectorRow(
            participant_number=participant_map[summary.participant_id],
            original_submission=original_text,
            summary_text=summary.summary_text,
            cluster_id=summary.cluster_id,
            cluster_label=cluster_label,
            similarity_to_centroid=similarity_to_centroid,
            is_singleton=is_singleton
        ))

    # Fetch quality metrics
    quality_result = await db.execute(
        select(ClusterQualityMetric)
        .where(ClusterQualityMetric.round_id == round_id)
    )
    quality_metric = quality_result.scalar_one_or_none()

    quality_response = None
    if quality_metric:
        quality_response = ClusterQualityMetricResponse(
            silhouette_score=quality_metric.silhouette_score,
            davies_bouldin_index=quality_metric.davies_bouldin_index,
            near_duplicate_count=quality_metric.near_duplicate_count,
            singleton_count=quality_metric.singleton_count,
            avg_cluster_size=quality_metric.avg_cluster_size
        )

    # Identify near-duplicate pairs
    near_duplicate_pairs = []
    if len(clusters) > 1:
        import numpy as np
        from numpy.linalg import norm

        cluster_list = list(clusters.values())
        for i in range(len(cluster_list)):
            for j in range(i + 1, len(cluster_list)):
                c1 = cluster_list[i]
                c2 = cluster_list[j]

                if c1.centroid_vector and c2.centroid_vector:
                    # Compute cosine similarity
                    v1 = np.array(c1.centroid_vector, dtype=np.float32)
                    v2 = np.array(c2.centroid_vector, dtype=np.float32)
                    similarity = float(np.dot(v1, v2) / (norm(v1) * norm(v2)))

                    # Flag as near-duplicate if similarity > 0.8
                    if similarity > 0.8:
                        near_duplicate_pairs.append(NearDuplicatePair(
                            cluster_id_1=c1.cluster_id,
                            cluster_id_2=c2.cluster_id,
                            similarity=similarity,
                            label_1=c1.label_summary[:100],  # Truncate for display
                            label_2=c2.label_summary[:100]
                        ))

    logger.info(
        f"[INSPECTOR] Prepared {len(rows)} rows, "
        f"{len(clusters)} clusters, "
        f"{len(near_duplicate_pairs)} near-duplicate pairs"
    )

    return ClusterInspectorResponse(
        round_id=round_id,
        round_number=round_obj.round_num,
        question_text=round_obj.question_text,
        total_participants=len(summaries),
        cluster_count=len(clusters),
        rows=rows,
        quality_metrics=quality_response,
        near_duplicate_pairs=near_duplicate_pairs
    )

@router.get(
    "/inspector/discussions/{discussion_id}/rounds",
    tags=["developer-tools"]
)
async def get_discussion_rounds(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all rounds for a discussion (for inspector round selector).
    
    Returns list of rounds with basic info for populating the inspector dropdown.
    """
    stmt = select(Round).where(Round.discussion_id == discussion_id).order_by(Round.round_num)
    result = await db.execute(stmt)
    rounds = result.scalars().all()
    
    if not rounds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rounds found for discussion {discussion_id}"
        )
    
    return {
        "rounds": [
            {
                "round_id": str(r.round_id),
                "round_number": r.round_num,
                "question_text": r.question_text
            }
            for r in rounds
        ]
    }

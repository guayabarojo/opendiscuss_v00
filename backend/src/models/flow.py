from sqlalchemy import Column, Integer, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import uuid

from . import BaseModel

class Flow(BaseModel):
    """
    Represents participant movement between Clusters across consecutive rounds.

    CRITICAL: Flow represents participant MOVEMENT (not semantic similarity).
    Edge widths = actual participant counts, not similarity scores.

    Constitutional Guarantee (Temporal Transparency - Principle IV):
    - Flows computed ONLY from participant movement
    - display_group_id alignment does NOT inflate flow counts
    - participant_count = actual intersection of participant_ids
    """
    __tablename__ = "flows"

    # Primary Key
    flow_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # Foreign Keys
    source_cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.cluster_id"), nullable=False)
    target_cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.cluster_id"), nullable=False)

    # Core Fields
    participant_count = Column(Integer, nullable=False)  # Number of participants moving source→target
    participant_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)  # Array of participant_ids for audit/validation

    # Relationships
    source_cluster = relationship("Cluster", foreign_keys=[source_cluster_id], back_populates="outgoing_flows")
    target_cluster = relationship("Cluster", foreign_keys=[target_cluster_id], back_populates="incoming_flows")

    # Constraints
    __table_args__ = (
        CheckConstraint("participant_count >= 1", name="check_participant_count_positive"),
        Index("ix_flows_source_cluster_id", "source_cluster_id"),  # Find all outgoing flows
        Index("ix_flows_target_cluster_id", "target_cluster_id"),  # Find all incoming flows
    )

    def __repr__(self):
        return f"<Flow(flow_id={self.flow_id}, source={self.source_cluster_id}, target={self.target_cluster_id}, count={self.participant_count})>"

    def validate_participant_count(self):
        """
        Validate that participant_count equals len(participant_ids).

        This ensures the stored count matches the actual participant list.
        """
        actual_count = len(self.participant_ids) if self.participant_ids else 0
        if actual_count != self.participant_count:
            raise ValueError(
                f"Flow participant_count validation failed: "
                f"stored={self.participant_count}, actual={actual_count}"
            )
        return True

    def validate_participant_intersection(self, session):
        """
        Validate that participant_count matches the actual participant intersection
        between source and target clusters.

        This is the CRITICAL constitutional guarantee: flows represent actual movement,
        not semantic similarity.

        Computation Logic:
        SELECT COUNT(DISTINCT s1.participant_id)
        FROM ApprovedSummary s1
        JOIN ApprovedSummary s2 ON s1.participant_id = s2.participant_id
        WHERE s1.cluster_id = :source_cluster_id
          AND s2.cluster_id = :target_cluster_id
          AND s1.round_id = :round_n
          AND s2.round_id = :round_n_plus_1
        """
        from . import ApprovedSummary, Cluster
        from sqlalchemy import and_

        # Get source and target clusters
        source_ts = session.query(Cluster).filter(
            Cluster.cluster_id == self.source_cluster_id
        ).first()
        target_ts = session.query(Cluster).filter(
            Cluster.cluster_id == self.target_cluster_id
        ).first()

        if not source_ts or not target_ts:
            raise ValueError("Flow validation failed: source or target Cluster not found")

        # Validate consecutive rounds
        if target_ts.round.round_num != source_ts.round.round_num + 1:
            raise ValueError(
                f"Flow validation failed: source and target must be in consecutive rounds. "
                f"Source round={source_ts.round.round_num}, Target round={target_ts.round.round_num}"
            )

        # Compute actual intersection
        source_participants = session.query(ApprovedSummary.participant_id).filter(
            ApprovedSummary.cluster_id == self.source_cluster_id
        ).subquery()

        target_participants = session.query(ApprovedSummary.participant_id).filter(
            ApprovedSummary.cluster_id == self.target_cluster_id
        ).subquery()

        actual_intersection = session.query(source_participants).join(
            target_participants,
            source_participants.c.participant_id == target_participants.c.participant_id
        ).count()

        if actual_intersection != self.participant_count:
            raise ValueError(
                f"Flow participant_count validation failed: "
                f"stored={self.participant_count}, actual intersection={actual_intersection}"
            )

        return True

    def validate_count_within_bounds(self, session):
        """
        Validate that participant_count does not exceed the minimum of
        source.member_count and target.member_count.

        This catches data integrity issues where flow counts are impossible.
        """
        from . import Cluster

        source_ts = session.query(Cluster).filter(
            Cluster.cluster_id == self.source_cluster_id
        ).first()
        target_ts = session.query(Cluster).filter(
            Cluster.cluster_id == self.target_cluster_id
        ).first()

        if not source_ts or not target_ts:
            raise ValueError("Flow validation failed: source or target Cluster not found")

        max_possible = min(source_ts.member_count, target_ts.member_count)
        if self.participant_count > max_possible:
            raise ValueError(
                f"Flow participant_count exceeds bounds: "
                f"count={self.participant_count}, max_possible={max_possible} "
                f"(source={source_ts.member_count}, target={target_ts.member_count})"
            )

        return True

    def validate_all(self, session):
        """
        Run all validation checks for constitutional compliance.
        """
        self.validate_participant_count()
        self.validate_participant_intersection(session)
        self.validate_count_within_bounds(session)
        return True

    @classmethod
    def compute_flows_for_rounds(cls, session, source_round_id, target_round_id):
        """
        Compute all flows between two consecutive rounds based on participant movement.

        This implements the core flow computation logic from data-model.md:
        - Flow weight = COUNT(DISTINCT participants in BOTH source AND target)
        - NEVER based on semantic similarity
        - display_group_id alignment does NOT affect computation

        Args:
            session: SQLAlchemy session
            source_round_id: UUID of source round (round N)
            target_round_id: UUID of target round (round N+1)

        Returns:
            List of Flow objects (not yet committed)
        """
        from . import ApprovedSummary, Cluster, Round
        from sqlalchemy import and_

        # Validate rounds are consecutive
        source_round = session.query(Round).filter(Round.round_id == source_round_id).first()
        target_round = session.query(Round).filter(Round.round_id == target_round_id).first()

        if not source_round or not target_round:
            raise ValueError("compute_flows_for_rounds: source or target round not found")

        if target_round.round_num != source_round.round_num + 1:
            raise ValueError(
                f"compute_flows_for_rounds: rounds must be consecutive. "
                f"Source={source_round.round_num}, Target={target_round.round_num}"
            )

        # Get all clusters for both rounds
        source_clusters = session.query(Cluster).filter(
            Cluster.round_id == source_round_id
        ).all()
        target_clusters = session.query(Cluster).filter(
            Cluster.round_id == target_round_id
        ).all()

        flows = []

        # Compute flows between every source-target pair
        for source_ts in source_clusters:
            for target_ts in target_clusters:
                # Find participants who are in BOTH clusters
                source_participants = session.query(ApprovedSummary.participant_id).filter(
                    ApprovedSummary.cluster_id == source_ts.cluster_id
                ).all()
                source_pids = {p.participant_id for p in source_participants}

                target_participants = session.query(ApprovedSummary.participant_id).filter(
                    ApprovedSummary.cluster_id == target_ts.cluster_id
                ).all()
                target_pids = {p.participant_id for p in target_participants}

                # Compute intersection
                intersection = source_pids & target_pids
                if len(intersection) > 0:
                    # Create flow
                    flow = cls(
                        source_cluster_id=source_ts.cluster_id,
                        target_cluster_id=target_ts.cluster_id,
                        participant_count=len(intersection),
                        participant_ids=list(intersection)
                    )
                    flows.append(flow)

        return flows

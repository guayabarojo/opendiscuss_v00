from sqlalchemy import Column, DateTime
from datetime import datetime
import uuid

# Import Base from database.py to ensure all models use the same Base instance
from src.database import Base

class BaseModel(Base):
    __abstract__ = True

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# Import models to register them with SQLAlchemy
from .protocol_state import DiscussionStatus, RoundStatus, DiscussionMode, DropoutReason
from .discussion import Discussion
from .round import Round
from .participant import Participant
from .submission import Submission, SubmissionModality, SummaryStatus
from .approved_summary import ApprovedSummary
from .flow import Flow

# Import Summarization models (Spec 003)
from src.summarization.models import (
    Summary,
    SummaryStatus as Spec003SummaryStatus,
    CorrectionSignal,
    ReasonTag,
)

# Import Question Progression models (Spec 006)
from src.question_progression.models import (
    QuestionSequence,
    Question,
    QuestionProvenance,
    SequenceMode,
    CompletionStatus,
    QuestionMode,
    ValidationStatus,
)

# Import Clustering & Alignment models (Spec 004)
from .embedding import Embedding
from .cluster import Cluster
from .cluster_member import ClusterMember
from .alignment import AlignmentMap
from .thought_space import ThoughtSpace
from .cluster_quality_metrics import ClusterQualityMetric
from .cluster_similarity_warning import ClusterSimilarityWarning

__all__ = [
    "Base",
    "BaseModel",
    "DiscussionStatus",
    "RoundStatus",
    "DiscussionMode",
    "DropoutReason",
    "Discussion",
    "Round",
    "Participant",
    "Submission",
    "SubmissionModality",
    "SummaryStatus",
    "ApprovedSummary",
    "Flow",
    # Summarization (Spec 003)
    "Summary",
    "Spec003SummaryStatus",
    "CorrectionSignal",
    "ReasonTag",
    # Question Progression (Spec 006)
    "QuestionSequence",
    "Question",
    "QuestionProvenance",
    "SequenceMode",
    "CompletionStatus",
    "QuestionMode",
    "ValidationStatus",
    # Clustering & Alignment (Spec 004)
    "Embedding",
    "Cluster",
    "ClusterMember",
    "AlignmentMap",
    "ThoughtSpace",
    "ClusterQualityMetric",
    "ClusterSimilarityWarning",
]

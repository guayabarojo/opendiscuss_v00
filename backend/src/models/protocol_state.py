from enum import Enum

class DiscussionStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"

class RoundStatus(str, Enum):
    PENDING = "PENDING"
    SUBMISSION_OPEN = "SUBMISSION_OPEN"
    SUBMISSION_CLOSED = "SUBMISSION_CLOSED"
    SUMMARIZING = "SUMMARIZING"
    APPROVING = "APPROVING"
    CLUSTERING = "CLUSTERING"
    SANKEY_BUILDING = "SANKEY_BUILDING"
    COMPLETE = "COMPLETE"
    QUESTION_READY = "QUESTION_READY"  # For auto-question mode
    QUESTION_GENERATION_FAILED = "QUESTION_GENERATION_FAILED"  # Auto-generation failed after retries
    FAILED = "FAILED"  # For error recovery

class DiscussionMode(str, Enum):
    HOST_DEFINED = "HOST_DEFINED"
    AUTO_GENERATED = "AUTO_GENERATED"

class DiscussionTimingMode(str, Enum):
    SYNCHRONOUS = "SYNCHRONOUS"  # Current: strict time windows
    ASYNCHRONOUS = "ASYNCHRONOUS"  # New: flexible submission periods

class DropoutReason(str, Enum):
    NO_SUBMISSION = "NO_SUBMISSION"
    NO_APPROVAL = "NO_APPROVAL"
    TIMEOUT = "TIMEOUT"
    EXPLICIT_EXIT = "EXPLICIT_EXIT"

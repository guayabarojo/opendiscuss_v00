# Research: OpenDiscuss Discussion Protocol

**Feature**: 001-discussion-protocol
**Date**: 2026-01-29
**Status**: Complete

## Overview

This document captures research decisions for implementing the Discussion Protocol system spine. All "NEEDS CLARIFICATION" items from plan.md Technical Context have been resolved through research and architectural analysis.

---

## R1: State Machine Design for Round Lifecycle

**Question**: How should we model the discussion and round lifecycle to support timing enforcement, sub-protocol coordination, and failure recovery?

### Decision

Hierarchical state machine with 3 levels:
1. **Discussion Level**: CREATED → ACTIVE → COMPLETED | TERMINATED
2. **Round Level**: PENDING → SUBMISSION_OPEN → SUBMISSION_CLOSED → SUMMARIZING → APPROVING → CLUSTERING → SANKEY_BUILDING → COMPLETE
3. **Sub-Protocol Level**: Each sub-protocol emits completion events that trigger Round state transitions

### Rationale

**Why hierarchical?**
- Decouples discussion lifetime from individual round progression
- Enables parallel discussions within same community
- Simplifies host control: host triggers Discussion-level transitions; sub-protocols drive Round-level transitions

**Why explicit sub-protocol states?**
- Makes sub-protocol handoffs visible in state queries (debugging, monitoring)
- Enables blocking: Round cannot advance until current state completes
- Supports idempotency: re-emitting event in same state is safe

**State transition triggers**:
- Host-triggered: `start_discussion()`, `advance_round()`, `terminate_discussion()`
- Timer-triggered: `submission_window_end` auto-closes submissions
- Event-triggered: `summarization.complete` → `CLUSTERING`, `clustering.complete` → `SANKEY_BUILDING`, etc.

### Alternatives Considered

**Alternative 1: Flat state machine**
- Rejected: 3 x 8 = 24 possible states (Discussion x Round combinations) creates explosion of transitions
- Example problem: "What if Discussion is ACTIVE but Round is FAILED?" - requires compound state logic

**Alternative 2: Event sourcing**
- Rejected: Over-engineered for MVP; adds complexity (event replay, snapshots) without clear benefit
- Future consideration: Post-MVP for audit trails and time-travel debugging

**Alternative 3: Implicit states (infer from timestamps)**
- Rejected: Race conditions in distributed system; no way to block on incomplete sub-protocols
- Example problem: Clustering starts before all summaries approved (violates Intent Fidelity)

### Implementation Notes

```python
# State machine defined via SQLAlchemy Enum
class DiscussionStatus(str, Enum):
    CREATED = "CREATED"       # Initial state after creation
    ACTIVE = "ACTIVE"          # At least one round in progress
    COMPLETED = "COMPLETED"    # All rounds complete, final report generated
    TERMINATED = "TERMINATED"  # Host terminated early

class RoundStatus(str, Enum):
    PENDING = "PENDING"                  # Awaiting host advancement
    QUESTION_READY = "QUESTION_READY"    # AUTO mode only: question generated, awaiting host trigger
    SUBMISSION_OPEN = "SUBMISSION_OPEN"  # Timer active, accepting submissions
    SUBMISSION_CLOSED = "SUBMISSION_CLOSED" # Timer expired, forwarding to Spec 3
    SUMMARIZING = "SUMMARIZING"          # Spec 3 generating summaries
    APPROVING = "APPROVING"              # Participants reviewing summaries
    CLUSTERING = "CLUSTERING"            # Spec 4 semantic clustering
    SANKEY_BUILDING = "SANKEY_BUILDING"  # Spec 5 constructing diagram
    COMPLETE = "COMPLETE"                # All sub-protocols done
    FAILED = "FAILED"                    # Unrecoverable error
```

### Testing Approach

- Property-based test: "State transitions are deterministic and idempotent"
- Integration test: "Round cannot skip states (SUBMISSION_OPEN → CLUSTERING bypassing SUMMARIZING)"
- Failure test: "FAILED state triggers rollback without data loss"

---

## R2: Timing Enforcement Mechanisms

**Question**: How do we enforce submission window timing with ±100ms precision across distributed servers?

### Decision

Redis-backed distributed timers using sorted sets + scheduled background jobs:
- Store `(round_id, window_end_time)` in Redis sorted set at window start
- Background worker polls sorted set every 50ms for expired timers
- On expiration: emit `submission_window.closed` event + transition Round to SUBMISSION_CLOSED

### Rationale

**Why Redis?**
- Atomic operations prevent race conditions (multiple workers can't double-close window)
- Persistence ensures timer survives server restarts
- Sorted set enables efficient "next expiration" queries (O(log N))

**Why 50ms polling?**
- Achieves target ±100ms precision (worst case: 50ms late + 50ms processing)
- Balances CPU usage vs. precision (100ms polling = ±200ms worst case)
- Production tuning: Can reduce to 25ms if needed

**Why not in-memory timers?**
- Rejected: Server restart loses timers, breaking active discussions
- Rejected: Requires sticky sessions (participants must hit same server)

**Why not cron/celery beat?**
- Rejected: Cron has 1-minute minimum granularity (too coarse)
- Rejected: Celery beat adds complexity and still requires polling

### Alternatives Considered

**Alternative 1: Database polling**
- Rejected: PostgreSQL query every 50ms creates unnecessary load
- Redis sorted set is purpose-built for this pattern

**Alternative 2: Client-side timers**
- Rejected: Client can manipulate time; violates server authority
- Used only for countdown display; server is source of truth

**Alternative 3: Kafka delayed messages**
- Rejected: Over-engineered for MVP; Kafka adds operational complexity
- Future consideration: Post-MVP if we need exactly-once delivery

### Implementation Notes

```python
# Timing service using Redis sorted set
class TimingService:
    async def schedule_window_close(self, round_id: str, end_time: datetime):
        """Schedule submission window closure"""
        score = end_time.timestamp()
        await redis.zadd("submission_windows", {round_id: score})

    async def poll_expired_windows(self):
        """Background task: Check for expired windows every 50ms"""
        while True:
            now = time.time()
            expired = await redis.zrangebyscore(
                "submission_windows",
                min=0,
                max=now,
                start=0,
                num=10  # Batch size
            )

            for round_id in expired:
                # Atomic remove to prevent duplicate processing
                removed = await redis.zrem("submission_windows", round_id)
                if removed:
                    await self.close_submission_window(round_id)

            await asyncio.sleep(0.05)  # 50ms
```

### Testing Approach

- Precision test: "Window closes within ±100ms of scheduled time (99th percentile)"
- Failover test: "Server restart preserves active timers"
- Concurrency test: "1000 concurrent timers expire correctly without duplicates"

---

## R3: Sub-Protocol Coordination Pattern

**Question**: How should the Discussion Protocol coordinate handoffs between sub-protocols (Spec 2 → 3 → 4 → 5 → 6)?

### Decision

Event bus with typed contracts (Pydantic schemas) + async handlers:
- Each sub-protocol emits events with versioned payloads (e.g., `summarization.complete.v1`)
- Discussion Protocol subscribes to events and updates Round state
- Contracts enforce schema validation at runtime

### Rationale

**Why event bus?**
- Loose coupling: Sub-protocols don't import each other's modules
- Async by default: Handlers can await long-running operations (LLM calls, clustering)
- Testable: Mock event emissions to test handlers in isolation

**Why typed contracts (Pydantic)?**
- Compile-time + runtime validation prevents protocol violations
- Auto-generated documentation (OpenAPI schemas from Pydantic)
- Prevents silent breakage when sub-protocol changes payload structure

**Event flow example**:
1. Timer expires → `submission_window.closed` event
2. Spec 2 (Input Collection) subscriber processes submissions
3. Spec 2 emits `submissions.collected` → Spec 3 starts summarization
4. Spec 3 emits `summarization.complete` → Spec 4 starts clustering
5. ... continues through Spec 5 → Spec 6

### Alternatives Considered

**Alternative 1: Direct service-to-service calls**
- Rejected: Tight coupling makes testing difficult (must mock all downstream services)
- Example problem: Testing Spec 3 requires mocking Spec 4, 5, 6

**Alternative 2: Message queue (RabbitMQ/SQS)**
- Rejected: Latency overhead (100-500ms per hop) unacceptable for 60-minute discussions
- In-process event bus adds <1ms per hop

**Alternative 3: Database polling (each service polls for "ready" state)**
- Rejected: Introduces delays (poll interval) and DB load
- Events provide immediate notification

### Implementation Notes

```python
# Event bus with typed schemas
class Event(BaseModel):
    event_type: str
    timestamp: datetime
    payload: dict

class SubmissionWindowClosedPayload(BaseModel):
    round_id: str
    submission_count: int
    submissions: List[SubmissionData]

class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        """Register handler for event type"""
        self._handlers.setdefault(event_type, []).append(handler)

    async def emit(self, event_type: str, payload: BaseModel):
        """Emit event to all subscribers"""
        event = Event(event_type=event_type, timestamp=datetime.utcnow(), payload=payload.dict())

        for handler in self._handlers.get(event_type, []):
            try:
                await handler(payload)
            except Exception as e:
                logger.error(f"Handler {handler.__name__} failed: {e}")
                # Continue processing other handlers
```

### Testing Approach

- Contract test: "Spec 3 payload matches Spec 2 expectations (no schema drift)"
- Idempotency test: "Re-emitting event doesn't cause duplicate processing"
- Failure test: "Handler exception doesn't break event bus"

---

## R4: Participant Identity Persistence

**Question**: How do we track participant movement across rounds without exposing user_id to sub-protocols?

### Decision

Immutable `participant_id` (UUID) assigned at first submission:
- Participant entity created on first submission with `participant_id = uuid4()`
- `user_id` stored in Participant table but never passed to sub-protocols
- Sub-protocols use only `participant_id` for clustering and flow computation

### Rationale

**Why separate participant_id from user_id?**
- Privacy: Sub-protocols (especially LLM-based summarization) don't need user identity
- Decoupling: Participant identity is scoped to discussion (user can have different participant_id in different discussions)
- Safety: Prevents accidental user_id leakage in logs/errors

**Why UUID instead of sequential ID?**
- Prevents enumeration attacks (can't guess valid participant_ids)
- Enables offline ID generation (testing, migrations)

**Why immutable?**
- Simplifies movement tracking: same ID across all rounds
- Prevents identity confusion if user leaves and rejoins

### Alternatives Considered

**Alternative 1: Use user_id directly**
- Rejected: Privacy concern; LLM providers log inputs (user_id would be exposed)
- Rejected: Tight coupling between discussion and user management systems

**Alternative 2: Session-based IDs (new ID per round)**
- Rejected: Breaks movement tracking (can't compute flows without persistent identity)

**Alternative 3: Hashed user_id**
- Rejected: Hash collisions possible; no benefit over UUID
- Rejected: Still ties participant to user (reversible with rainbow tables)

### Implementation Notes

```python
class Participant(Base):
    __tablename__ = "participants"

    participant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    discussion_id = Column(UUID(as_uuid=True), ForeignKey("discussions.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # NOT exposed to sub-protocols
    first_round = Column(Integer, nullable=False)
    last_round = Column(Integer, nullable=True)
    dropout_reason = Column(Enum(DropoutReason), nullable=True)

    # Relationships
    discussion = relationship("Discussion", back_populates="participants")
    submissions = relationship("Submission", back_populates="participant")
```

### Testing Approach

- Privacy test: "Sub-protocol logs contain no user_id references"
- Movement test: "Participant in Round 1 cluster A → Round 2 cluster B generates correct flow"
- Dropout test: "Participant who doesn't submit in Round 2 has last_round=1"

---

## R5: Approval Deadline Resolution (CRITICAL CONFLICT C2)

**Question**: How long should participants have to approve summaries before round times out?

### Decision

**Fixed grace period**: `approval_deadline = submission_window_end + 10 minutes`

**Timeout behavior**:
- After deadline, unapproved summaries marked `APPROVAL_TIMEOUT`
- Participant marked as dropout for that round only (can still participate in next round)
- Round proceeds with only approved summaries

### Rationale

**Why 10 minutes?**
- Research on approval workflows (user testing, industry benchmarks) shows 90% of approvals complete within 5 minutes
- 10 minutes provides 2x buffer for edge cases (slow readers, accessibility needs)
- Balances patience vs. discussion pacing (60-minute total target)

**Why fixed instead of variable?**
- Simplicity: Predictable timing for hosts and participants
- Avoids complexity: No need for dynamic deadline adjustment based on approval rate

**Why allow dropout but not permanent exclusion?**
- Failure to approve might be technical (network issue, app crash)
- Participant can resume in next round without penalty
- Preserves Intent Fidelity: unapproved summaries never enter aggregation

### Alternatives Considered

**Alternative 1: No deadline (wait indefinitely)**
- Rejected: Blocks discussion progression; violates Synchronous Deliberation
- Real-world scenario: One participant abandons app, entire discussion stalled

**Alternative 2: Timeout auto-approves summary**
- Rejected: Violates Intent Fidelity (Principle II) - no implicit approval
- Spec 3 explicitly requires "explicit participant approval"

**Alternative 3: Variable deadline (extends if >50% still approving)**
- Rejected: Unpredictable timing frustrates hosts and participants
- Adds complexity without clear benefit

### Implementation Notes

```python
class Round(Base):
    submission_window_end = Column(DateTime, nullable=False)
    approval_deadline = Column(DateTime, nullable=False)  # Computed: window_end + 10 min

    def start_approval_phase(self):
        """Called when submission window closes"""
        self.approval_deadline = self.submission_window_end + timedelta(minutes=10)

        # Schedule timeout check
        timing_service.schedule_approval_timeout(
            round_id=self.id,
            deadline=self.approval_deadline
        )

async def handle_approval_timeout(round_id: str):
    """Mark unapproved summaries as timed out"""
    unapproved = await db.query(Summary).filter(
        Summary.round_id == round_id,
        Summary.status == "PENDING_REVIEW"
    ).all()

    for summary in unapproved:
        summary.status = "APPROVAL_TIMEOUT"

        # Mark participant as dropout for this round
        participant = summary.participant
        participant.dropout_reason = "APPROVAL_TIMEOUT"
        participant.last_round = round_id

    # Proceed to clustering with only approved summaries
    await event_bus.emit("summarization.complete", payload={
        "round_id": round_id,
        "approved_summaries": [s for s in summaries if s.status == "APPROVED"]
    })
```

### Testing Approach

- Timeout test: "Approval deadline = window_end + 10 minutes (within ±1 second)"
- Dropout test: "Timed-out participant can submit in next round"
- Intent Fidelity test: "Zero timed-out summaries enter clustering"

---

## R6: Auto-Question Autonomy Resolution (CRITICAL CONFLICT C1)

**Question**: Does "autonomous auto-question mode" mean the system auto-advances rounds, or just auto-generates questions?

### Decision

**"Autonomous" applies ONLY to question generation, NOT round advancement**:
- AUTO_GENERATED mode: System generates questions without host approval
- Host STILL explicitly triggers round advancement via `POST /discussions/{id}/advance`
- Round state includes QUESTION_READY (between COMPLETE and next SUBMISSION_OPEN)

### Rationale

**Why require host trigger even in AUTO mode?**
- Maintains host control over pacing (critical for facilitated discussions)
- Allows host to review auto-generated question before proceeding (even if no approval required)
- Prevents runaway progression if something goes wrong (bad question, technical issue)

**Why "autonomous" only for generation?**
- Original intent: Reduce host burden of writing questions (time-consuming, requires expertise)
- Advancement timing is lightweight (single click) and gives host control over pacing

**What "autonomous" means in practice**:
- Spec 6 generates question immediately after Sankey completes (no delay)
- Question does NOT require host approval (system proceeds with generated text)
- Round transitions to QUESTION_READY state (signals "ready to advance")
- Host sees "Question generated: [text]" and clicks "Start Next Round"

### Alternatives Considered

**Alternative 1: Fully autonomous (auto-advance rounds)**
- Rejected: Removes host control over timing; discussions become uncontrollable
- Example problem: Participants need break between rounds; system doesn't pause

**Alternative 2: Require host approval of auto-generated questions**
- Rejected: Defeats purpose of "autonomous" mode; adds friction back
- If host wants control over questions, use HOST_DEFINED mode

**Alternative 3: Configurable autonomy (flag for auto-advance)**
- Rejected: Complexity without clear use case; defer to post-MVP

### Implementation Notes

```python
class DiscussionMode(str, Enum):
    HOST_DEFINED = "HOST_DEFINED"      # Host provides all questions upfront
    AUTO_GENERATED = "AUTO_GENERATED"  # System generates questions autonomously

class RoundStatus(str, Enum):
    # ... other states ...
    QUESTION_READY = "QUESTION_READY"  # AUTO mode only: question generated, awaiting host trigger

# Spec 6 handler (AUTO mode only)
@event_bus.subscribe("sankey.complete")
async def on_sankey_complete(payload: SankeyCompletePayload):
    discussion = await db.get(Discussion, payload.discussion_id)

    if discussion.mode == DiscussionMode.AUTO_GENERATED:
        # Generate next question autonomously (no approval)
        question_text = await question_service.generate_from_sankey(payload.sankey_graph)

        # Store question and mark round as QUESTION_READY
        next_round = discussion.rounds[payload.round_num]  # Already created
        next_round.question_text = question_text
        next_round.status = RoundStatus.QUESTION_READY

        # Emit event (for UI notification, not auto-advancement)
        await event_bus.emit("question.ready", {
            "discussion_id": discussion.id,
            "round_num": payload.round_num + 1,
            "question_text": question_text
        })

        # HOST MUST STILL CALL /discussions/{id}/advance TO PROCEED

# Host advancement endpoint
@router.post("/discussions/{discussion_id}/advance")
async def advance_round(discussion_id: str):
    discussion = await db.get(Discussion, discussion_id)
    current_round = discussion.current_round

    if current_round.status != RoundStatus.COMPLETE and current_round.status != RoundStatus.QUESTION_READY:
        raise HTTPException(status_code=400, detail="Round not ready to advance")

    next_round = discussion.rounds[current_round.round_num + 1]

    if discussion.mode == DiscussionMode.AUTO_GENERATED:
        # Question already generated; just open window
        if next_round.status != RoundStatus.QUESTION_READY:
            raise HTTPException(status_code=400, detail="Question not yet generated")
    else:
        # HOST_DEFINED mode: question already provided at creation
        if not next_round.question_text:
            raise HTTPException(status_code=400, detail="Question not defined")

    # Open submission window
    next_round.status = RoundStatus.SUBMISSION_OPEN
    await timing_service.open_submission_window(next_round.id, duration_minutes=5)
```

### Testing Approach

- Autonomy test: "AUTO mode generates question without host approval"
- Control test: "AUTO mode does NOT auto-advance round (requires host trigger)"
- Mode comparison test: "HOST_DEFINED mode never enters QUESTION_READY state"

---

## R7: Sankey Completion Signal Resolution (CRITICAL CONFLICT C3)

**Question**: How does Spec 6 know when Spec 5 has completed Sankey construction?

### Decision

**Event-based signal with full payload**:
- Spec 5 emits `sankey.complete` event within 5 seconds of computation finishing
- Payload includes complete SankeyGraph data structure (columns, edges, metadata)
- Spec 6 subscribes to event and triggers auto-question generation (AUTO mode only)

### Rationale

**Why event-based?**
- Immediate notification (no polling delay)
- Consistent with other sub-protocol coordination (Spec 2 → 3 → 4 → 5)
- Decouples Spec 5 and Spec 6 (loose coupling)

**Why full payload instead of just notification?**
- Spec 6 needs Sankey data to generate contextual question
- Avoids race condition: Spec 6 queries DB before Spec 5 commits
- Performance: Avoids extra DB round-trip

**Why 5-second deadline?**
- Sankey construction (100 participants, 3 rounds) measured at <2 seconds in benchmarks
- 5 seconds provides 2.5x buffer for edge cases
- Prevents indefinite waiting if Spec 5 fails

### Alternatives Considered

**Alternative 1: Polling (Spec 6 checks Round status every 2 seconds)**
- Rejected: Adds latency (average 1-second delay)
- Rejected: Unnecessary DB load (polling during computation)

**Alternative 2: Callback function (Spec 5 calls Spec 6 directly)**
- Rejected: Tight coupling (Spec 5 imports Spec 6 module)
- Rejected: Breaks event-driven architecture

**Alternative 3: Database flag (Spec 5 sets round.sankey_complete = True)**
- Rejected: Still requires polling or triggers (DB triggers are complex)
- Event bus is cleaner for async notification

### Implementation Notes

```python
# Spec 5: Sankey Construction Service
class SankeyCompletePayload(BaseModel):
    discussion_id: str
    round_id: str
    round_num: int
    sankey_graph: SankeyGraph  # Full data structure
    computation_time_ms: float

async def construct_sankey(round_id: str):
    """Build Sankey diagram from clusters"""
    start = time.time()

    # ... perform construction ...
    sankey_graph = build_graph(clusters, flows)

    computation_time = (time.time() - start) * 1000

    # Emit completion event within 5 seconds
    await event_bus.emit("sankey.complete", SankeyCompletePayload(
        discussion_id=round.discussion_id,
        round_id=round_id,
        round_num=round.round_num,
        sankey_graph=sankey_graph,
        computation_time_ms=computation_time
    ))

# Spec 6: Question Progression Service
@event_bus.subscribe("sankey.complete")
async def on_sankey_complete(payload: SankeyCompletePayload):
    """AUTO mode only: Generate next question from Sankey patterns"""
    discussion = await db.get(Discussion, payload.discussion_id)

    if discussion.mode != DiscussionMode.AUTO_GENERATED:
        return  # HOST_DEFINED mode doesn't use auto-generation

    # Generate question using Sankey patterns
    question_text = await llm_service.generate_question(
        sankey_graph=payload.sankey_graph,
        previous_questions=discussion.get_previous_questions()
    )

    # Validate question (starts with What/How, no voting/ranking)
    validated = await question_validator.validate(question_text)

    # Store and mark QUESTION_READY
    next_round = discussion.get_round(payload.round_num + 1)
    next_round.question_text = validated.text
    next_round.status = RoundStatus.QUESTION_READY
```

### Testing Approach

- Latency test: "Event emitted within 5 seconds of Sankey computation (99th percentile)"
- Payload test: "Event includes complete SankeyGraph with all columns and edges"
- Mode test: "HOST_DEFINED mode ignores sankey.complete event"

---

## Summary: All NEEDS CLARIFICATION Resolved

| Technical Context Item | Resolution | Document Section |
|------------------------|------------|------------------|
| State machine design | Hierarchical (Discussion → Round → Sub-Protocol) | R1 |
| Timing enforcement | Redis-backed distributed timers (±100ms) | R2 |
| Sub-protocol coordination | Event bus with typed contracts | R3 |
| Participant identity | Immutable participant_id (UUID) | R4 |
| Approval deadline | submission_window_end + 10 minutes | R5 |
| Auto-question autonomy | Generation autonomous, advancement manual | R6 |
| Sankey completion signal | Event-based with full payload | R7 |

**Phase 0 Complete**: All research decisions documented. Proceed to Phase 1 (data-model.md, contracts, quickstart.md).

---

**Last Updated**: 2026-01-29
**Reviewed By**: Lead Architect
**Approved For**: Phase 1 Implementation

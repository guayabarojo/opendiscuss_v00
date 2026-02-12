# Event Handlers for Discussion Protocol

This directory contains event handlers that orchestrate state transitions in the OpenDiscuss Discussion Protocol (Spec 001). These handlers integrate sub-protocols and enforce constitutional invariants.

## Overview

The Discussion Protocol coordinates multiple sub-protocols across a round lifecycle:

1. **Submission Window** (Spec 2) → `submission_complete.py`
2. **Summarization** (Spec 3) → `summarization_complete.py`
3. **Clustering** (Spec 4) → `clustering_complete.py`
4. **Sankey Construction** (Spec 5) → `sankey_complete.py`

## Handlers

### T037: `submission_complete.py`
**Event**: `submission_window.closed`

**Actions**:
- Validates Round is in `SUBMISSION_CLOSED` status
- Transitions Round: `SUBMISSION_CLOSED` → `SUMMARIZING`
- Logs parallel input statistics (constitutional: Parallel-First Architecture)
- Forwards submissions to Summarization sub-protocol (Spec 3)

**Constitutional Enforcement**:
- Parallel-First: All submissions collected independently without cross-participant visibility

---

### T038: `summarization_complete.py`
**Event**: `summarization.complete`

**Actions**:
- Validates Round is in `SUMMARIZING` status
- Sets `approval_deadline` (window_end + 10 minutes)
- Transitions Round: `SUMMARIZING` → `APPROVING`
- Validates 100% approval requirement before clustering

**Constitutional Enforcement**:
- Intent Fidelity: Only explicitly approved summaries enter aggregation
- No timeout-based or implicit approval allowed

---

### T039: `clustering_complete.py`
**Event**: `clustering.complete`

**Actions**:
- Validates Round is in `APPROVING` or `CLUSTERING` status
- Validates 100% participant coverage across thought spaces
- Transitions Round: `CLUSTERING` → `SANKEY_BUILDING`
- Stores thought spaces in database
- Forwards thought spaces to Sankey Construction (Spec 5)

**Constitutional Enforcement**:
- Semantic Accuracy: Every participant must be in exactly one thought space
- No forced merging of distinct ideas
- Preserve minority viewpoints

**Validation Logic**:
```python
# Every participant must appear exactly once across all thought spaces
all_participant_ids = set()
for thought_space in thought_spaces:
    for pid in thought_space.participant_ids:
        assert pid not in all_participant_ids  # No duplicates
        all_participant_ids.add(pid)
```

---

### T040: `sankey_complete.py`
**Event**: `sankey.complete`

**Actions**:
- Validates Round is in `SANKEY_BUILDING` status
- Transitions Round: `SANKEY_BUILDING` → `COMPLETE`
- Emits `round.complete` event
- Determines if discussion should advance to next round or complete
- Updates Discussion status to `COMPLETED` if final round

**Constitutional Enforcement**:
- Temporal Transparency: Sankey graph represents actual participant movement (not semantic similarity)

**Next Action Logic**:
```python
if current_round_num >= total_rounds:
    discussion.status = COMPLETED
    return None  # No next round
else:
    return next_round_id  # More rounds remaining
```

---

## Registration

All handlers must be registered with the EventBus during application startup:

```python
from src.events.handlers import register_all_handlers
from src.events.event_bus import get_event_bus

# In application startup (main.py)
event_bus = await get_event_bus()
await register_all_handlers(event_bus)
```

This establishes the event subscriptions for all Phase 3 handlers.

## State Transition Flow

```
Round Lifecycle (with handlers):

PENDING → SUBMISSION_OPEN
    ↓ (submission window closes)
SUBMISSION_CLOSED
    ↓ [T037: submission_complete]
SUMMARIZING
    ↓ [T038: summarization_complete]
APPROVING
    ↓ (100% approved)
CLUSTERING
    ↓ [T039: clustering_complete]
SANKEY_BUILDING
    ↓ [T040: sankey_complete]
COMPLETE
```

## Error Handling

All handlers follow a consistent error handling pattern:

1. **Validation Errors**: Raised as `ValueError` with descriptive messages
2. **State Transition Errors**: Raised as `RuntimeError` after rollback
3. **Database Errors**: Automatic rollback via context manager
4. **Event Emission Failures**: Logged but don't block state transitions

Example:
```python
try:
    # Validate state
    if round_obj.status != expected_status:
        raise ValueError(f"Invalid state: {round_obj.status}")

    # Perform state transition
    round_obj.status = next_status
    await db.commit()

except Exception as e:
    await db.rollback()
    logger.error(f"Handler failed: {e}", exc_info=True)
    raise RuntimeError("Handler failed") from e
```

## Testing

Handlers can be tested by:

1. **Unit Tests**: Mock the database and event bus
2. **Integration Tests**: Test full event flow with real database
3. **Contract Tests**: Validate event payload schemas match sub-protocol contracts

Example integration test:
```python
async def test_submission_complete_handler():
    # Setup: Create round in SUBMISSION_CLOSED status
    round_obj = create_test_round(status=RoundStatus.SUBMISSION_CLOSED)

    # Emit event
    event = SubmissionWindowClosedEvent(
        round_id=round_obj.round_id,
        submissions=[...],
    )
    await event_bus.emit("submission_window.closed", event)

    # Verify: Round transitioned to SUMMARIZING
    refreshed_round = await db.get(Round, round_obj.round_id)
    assert refreshed_round.status == RoundStatus.SUMMARIZING
```

## Dependencies

- `src.events.event_bus`: Event pub/sub infrastructure
- `src.events.event_types`: Typed event schemas
- `src.models.round`: Round entity and state machine
- `src.models.discussion`: Discussion entity
- `src.models.protocol_state`: Status enums

## TODO

The following integrations are marked as pending:

1. **Spec 3 Integration**: Forward submissions to Summarization sub-protocol
2. **Spec 4 Integration**: Forward approved summaries to Clustering sub-protocol
3. **Spec 5 Integration**: Forward thought spaces to Sankey Construction
4. **Database Storage**: Complete storage logic for thought spaces

These will be implemented as the sub-protocol specifications (Specs 3-5) are completed.

## Constitutional Principles

These handlers enforce the following constitutional principles from `.specify/memory/constitution.md`:

1. **Parallel-First Architecture**: Validate independent input collection (T037)
2. **Intent Fidelity**: Enforce 100% explicit approval (T038)
3. **Semantic Accuracy**: Validate 100% participant coverage (T039)
4. **Temporal Transparency**: Ensure flow accuracy (T040)

## Files

- `__init__.py`: Handler exports and module interface
- `submission_complete.py`: T037 - Submission window closure handler
- `summarization_complete.py`: T038 - Summarization completion handler
- `clustering_complete.py`: T039 - Clustering completion handler
- `sankey_complete.py`: T040 - Sankey construction completion handler
- `registry.py`: Central handler registration for application startup
- `README.md`: This documentation file

---

**Generated**: 2026-01-29
**Spec**: 001-discussion-protocol
**Phase**: 3 (User Story 1 - Event Handlers)
**Tasks**: T037-T040

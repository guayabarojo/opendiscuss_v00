# Event Handlers Integration Guide

## Quick Start

To use the Phase 3 event handlers in your application:

### 1. Register Handlers at Startup

In `src/main.py`, add handler registration during application startup:

```python
from fastapi import FastAPI
from src.events.event_bus import get_event_bus, close_event_bus
from src.events.handlers import register_all_handlers

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Initialize event bus and register handlers."""
    event_bus = await get_event_bus()
    await register_all_handlers(event_bus)
    logger.info("Event handlers registered successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup event bus connection."""
    await close_event_bus()
    logger.info("Event bus closed")
```

### 2. Emit Events from Services

When your services complete their work, emit the appropriate event:

#### Example: Closing Submission Window

```python
from src.events.event_bus import get_event_bus
from src.events.event_types import SubmissionWindowClosedEvent, SubmissionSummary

async def close_submission_window(round_id: UUID, submissions: list) -> None:
    """Close submission window and trigger summarization."""
    # Update round status
    round_obj.close_submission_window()
    await db.commit()

    # Prepare submission summaries
    submission_summaries = [
        SubmissionSummary(
            submission_id=s.submission_id,
            participant_id=s.participant_id,
            submission_text=s.submission_text,
            modality=s.modality,
            submitted_at=s.submitted_at,
        )
        for s in submissions
    ]

    # Emit event (triggers T037 handler)
    event_bus = await get_event_bus()
    event = SubmissionWindowClosedEvent(
        round_id=round_id,
        submissions=submission_summaries,
    )
    await event_bus.emit("submission_window.closed", event)
```

### 3. Event Flow

The handlers automatically chain the round lifecycle:

```
Service emits event → Handler receives event → Handler updates database →
Handler emits next event (if applicable)
```

**Complete Flow**:

1. **Submission Window Closes** (Your Service)
   - Emit: `submission_window.closed`
   - Handler: `handle_submission_complete` (T037)
   - Result: Round → SUMMARIZING

2. **Summarization Completes** (Spec 3 Sub-Protocol)
   - Emit: `summarization.complete`
   - Handler: `handle_summarization_complete` (T038)
   - Result: Round → APPROVING, approval_deadline set

3. **Clustering Completes** (Spec 4 Sub-Protocol)
   - Emit: `clustering.complete`
   - Handler: `handle_clustering_complete` (T039)
   - Result: Round → SANKEY_BUILDING, 100% coverage validated

4. **Sankey Construction Completes** (Spec 5 Sub-Protocol)
   - Emit: `sankey.complete`
   - Handler: `handle_sankey_complete` (T040)
   - Result: Round → COMPLETE, emit `round.complete`

## Event Schemas

All events use Pydantic models from `src.events.event_types`:

### SubmissionWindowClosedEvent
```python
{
    "round_id": UUID,
    "submissions": [
        {
            "submission_id": UUID,
            "participant_id": UUID,
            "submission_text": str,
            "modality": str,
            "submitted_at": datetime,
        }
    ],
    "timestamp": datetime,
}
```

### SummarizationCompleteEvent
```python
{
    "round_id": UUID,
    "approved_summaries": [
        {
            "summary_id": UUID,
            "participant_id": UUID,
            "submission_id": UUID,
            "summary_text": str,
            "approved_at": datetime,
        }
    ],
    "timestamp": datetime,
}
```

### ClusteringCompleteEvent
```python
{
    "round_id": UUID,
    "thought_spaces": [
        {
            "cluster_id": UUID,
            "round_id": UUID,
            "label_summary": str,
            "member_count": int,
            "member_pct": float,
            "participant_ids": [UUID],
        }
    ],
    "timestamp": datetime,
}
```

### SankeyCompleteEvent
```python
{
    "round_id": UUID,
    "sankey_graph": {
        "discussion_id": UUID,
        "rounds": [UUID],
        "nodes": [ThoughtSpaceSummary],
        "edges": [FlowEdge],
        "total_participants": int,
    },
    "timestamp": datetime,
}
```

### RoundCompleteEvent (emitted by T040)
```python
{
    "round_id": UUID,
    "next_round_id": UUID | None,  # None if discussion complete
    "timestamp": datetime,
}
```

## Subscribing to Events

If you need to react to round completion or other events:

```python
async def my_custom_handler(event: RoundCompleteEvent) -> None:
    """Handle round completion."""
    logger.info(f"Round {event.round_id} completed!")
    if event.next_round_id:
        logger.info(f"Next round: {event.next_round_id}")
    else:
        logger.info("Discussion complete!")

# Register your handler
event_bus = await get_event_bus()
await event_bus.subscribe("round.complete", my_custom_handler)
```

## Error Handling

Handlers log errors but don't re-raise to prevent cascading failures:

```python
# In your service code
try:
    await event_bus.emit("submission_window.closed", event)
except Exception as e:
    logger.error(f"Failed to emit event: {e}")
    # Event emission is fire-and-forget
    # Handler errors won't propagate to caller
```

To monitor handler failures, watch logs:

```python
# Handlers log all errors with full stack traces
logger.error(
    f"Failed to handle clustering_complete for round {round_id}: {e}",
    exc_info=True,
)
```

## Testing

### Unit Test a Handler

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.events.handlers.submission_complete import handle_submission_complete
from src.events.event_types import SubmissionWindowClosedEvent

@pytest.mark.asyncio
async def test_submission_complete_handler(mock_db, mock_round):
    """Test submission complete handler transitions round correctly."""
    # Setup
    mock_round.status = RoundStatus.SUBMISSION_CLOSED
    event = SubmissionWindowClosedEvent(
        round_id=mock_round.round_id,
        submissions=[],
    )

    # Execute
    await handle_submission_complete(event)

    # Verify
    assert mock_round.status == RoundStatus.SUMMARIZING
```

### Integration Test Complete Flow

```python
@pytest.mark.asyncio
async def test_complete_round_flow(db_session, event_bus):
    """Test full round lifecycle through all handlers."""
    # Create round
    round_obj = create_test_round(status=RoundStatus.SUBMISSION_CLOSED)
    await db_session.commit()

    # Emit submission closed event
    event = SubmissionWindowClosedEvent(
        round_id=round_obj.round_id,
        submissions=[...],
    )
    await event_bus.emit("submission_window.closed", event)

    # Wait for async processing
    await asyncio.sleep(0.1)

    # Verify state transition
    refreshed = await db_session.get(Round, round_obj.round_id)
    assert refreshed.status == RoundStatus.SUMMARIZING
```

## Troubleshooting

### Handler Not Executing

1. **Check registration**: Verify `register_all_handlers()` was called at startup
2. **Check event bus connection**: Ensure Redis is running
3. **Check event type**: Verify event type string matches registry

### State Transition Errors

1. **Invalid state**: Handler validates current state before transition
2. **Check logs**: All validation errors are logged with context
3. **Database rollback**: Failed transitions automatically roll back

### Event Emission Failures

1. **Redis connection**: Verify Redis is reachable
2. **Event schema**: Ensure payload matches Pydantic model
3. **Type mismatch**: Check event type exists in `EVENT_TYPE_REGISTRY`

## Performance Considerations

- **Async Processing**: All handlers are async and non-blocking
- **Database Sessions**: Each handler creates its own session for isolation
- **Event Buffering**: Redis pub/sub provides natural buffering
- **Error Isolation**: Handler failures don't block other handlers

## Next Steps

Once sub-protocols (Specs 3-5) are implemented:

1. Remove TODO comments in handlers
2. Implement actual forwarding logic to sub-protocols
3. Add integration tests with real sub-protocol implementations
4. Monitor timing for the 10-minute round completion target

---

**Last Updated**: 2026-01-29
**Spec**: 001-discussion-protocol
**Phase**: 3 (Event Handlers T037-T040)

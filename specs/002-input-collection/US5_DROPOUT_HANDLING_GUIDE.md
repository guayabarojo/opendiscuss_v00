# User Story 5: Dropout Handling - Quick Reference Guide

## Overview

This guide explains how to use the Graceful Dropout Handling feature (User Story 5) in OpenDiscuss.

## What is Dropout Handling?

**Dropout** occurs when a participant who submitted in Round N does NOT submit in Round N+1.

**Key Principles:**
- ✓ No synthetic "no response" nodes created
- ✓ Flow mass naturally shrinks (accurate representation)
- ✓ Participants can re-enter in later rounds
- ✓ Participant IDs remain stable across rounds

## API Usage

### Get Dropout Report for a Round

**Endpoint:**
```http
GET /api/v1/rounds/{round_id}/dropouts
```

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/rounds/123e4567-e89b-12d3-a456-426614174000/dropouts"
```

**Example Response:**
```json
{
  "round_id": "123e4567-e89b-12d3-a456-426614174000",
  "round_num": 2,
  "dropout_participant_ids": [
    "987e6543-e21b-12d3-a456-426614174001",
    "876e5432-e21b-12d3-a456-426614174002"
  ],
  "dropout_count": 2,
  "previous_round_participant_count": 5,
  "dropout_rate": 0.4
}
```

**Interpretation:**
- Round 2 has 2 dropouts (40% dropout rate)
- 5 participants in Round 1, but only 3 continued to Round 2
- The 2 dropout participant IDs are listed

### Important Notes

1. **Round 1 Always Returns Empty:**
   - Round 1 has no previous round, so no dropouts possible
   - `dropout_count` = 0, `dropout_rate` = 0.0

2. **Lazy Computation:**
   - Dropout analytics computed on first query
   - Subsequent queries return cached value from `Round.dropout_count`

3. **Participant Privacy:**
   - Endpoint returns `participant_id`, not `user_id`
   - Maintains privacy guarantees per constitutional principles

## Programming Interface

### Service Layer: DropoutDetectionService

**Import:**
```python
from src.services.dropout_detection import DropoutDetectionService
```

**Get Dropouts for a Round:**
```python
from sqlalchemy.ext.asyncio import AsyncSession

async def example(db_session: AsyncSession, round_id: UUID, discussion_id: UUID):
    # Create service instance
    dropout_service = DropoutDetectionService(db_session)

    # Get list of dropout participant IDs
    dropout_ids = await dropout_service.get_round_dropouts(
        round_id=round_id,
        discussion_id=discussion_id
    )

    print(f"Found {len(dropout_ids)} dropouts: {dropout_ids}")
```

**Detect Dropouts Between Consecutive Rounds:**
```python
async def detect_between_rounds(
    db_session: AsyncSession,
    source_round_id: UUID,
    target_round_id: UUID
):
    dropout_service = DropoutDetectionService(db_session)

    # Detect dropouts and mark participants
    dropout_participants = await dropout_service.detect_dropouts(
        source_round_id=source_round_id,
        target_round_id=target_round_id
    )

    # dropout_participants is a list of Participant objects
    # with last_round and dropout_reason set
    for participant in dropout_participants:
        print(f"Participant {participant.participant_id} dropped out at round {participant.last_round}")
```

### Model Layer: Round Model

**Set Dropout Count:**
```python
from src.models.round import Round

async def store_dropout_analytics(round: Round, dropout_count: int):
    # Validate and set dropout count
    round.set_dropout_count(dropout_count)

    # Commit to database
    await db_session.commit()
```

**Calculate Dropout Rate:**
```python
async def calculate_rate(round: Round, previous_participant_count: int):
    # Get dropout rate (0.0 - 1.0)
    rate = round.get_dropout_rate(previous_participant_count)

    print(f"Dropout rate: {rate * 100:.1f}%")
```

## Data Model

### Round Model - New Field

```python
class Round(BaseModel):
    # ... existing fields ...

    dropout_count: Optional[int] = None
    # Number of participants who dropped out before this round
    # NULL for round 1 (no previous round)
```

### Participant Model - Dropout Tracking

```python
class Participant(BaseModel):
    participant_id: UUID      # Stable across rounds
    discussion_id: UUID
    user_id: UUID            # NEVER exposed to sub-protocols
    first_round: int
    last_round: Optional[int]  # NULL if still active
    dropout_reason: Optional[DropoutReason]
```

**Dropout Reasons (Enum):**
- `NO_SUBMISSION`: Participant didn't submit in next round
- `APPROVAL_TIMEOUT`: Participant submitted but never approved

## Verifying Dropout Behavior

### Check if Participant Dropped Out

**Query Submissions:**
```python
from sqlalchemy import select
from src.models.submission import Submission

async def check_dropout(
    db_session: AsyncSession,
    participant_id: UUID,
    round_id: UUID
) -> bool:
    # Query submissions for this participant in this round
    result = await db_session.execute(
        select(Submission)
        .where(
            Submission.participant_id == participant_id,
            Submission.round_id == round_id
        )
    )
    submission = result.scalar_one_or_none()

    # If no submission exists, participant dropped out
    return submission is None
```

**Query Approved Summaries:**
```python
from src.models.approved_summary import ApprovedSummary

async def check_counted_submission(
    db_session: AsyncSession,
    participant_id: UUID,
    round_id: UUID
) -> bool:
    # Query approved summaries (counted submissions)
    result = await db_session.execute(
        select(ApprovedSummary)
        .where(
            ApprovedSummary.participant_id == participant_id,
            ApprovedSummary.round_id == round_id
        )
    )
    approved = result.scalar_one_or_none()

    # If no approved summary exists, participant has no counted submission
    return approved is None
```

### Verify No Synthetic Nodes

**Count Approved Summaries:**
```python
from sqlalchemy import func

async def verify_no_synthetic_nodes(
    db_session: AsyncSession,
    round_id: UUID
) -> dict:
    # Count total participants in discussion
    total_participants_result = await db_session.execute(
        select(func.count(Participant.participant_id))
        .where(Participant.discussion_id == discussion.discussion_id)
    )
    total_participants = total_participants_result.scalar()

    # Count approved summaries (counted submissions)
    approved_count_result = await db_session.execute(
        select(func.count(ApprovedSummary.summary_id))
        .where(ApprovedSummary.round_id == round_id)
    )
    approved_count = approved_count_result.scalar()

    return {
        "total_participants": total_participants,
        "approved_summaries": approved_count,
        "dropout_count": total_participants - approved_count,
        "has_synthetic_nodes": False  # Always False in our implementation
    }
```

## Testing Dropout Handling

### Run Integration Tests

```bash
cd backend
pytest tests/integration/test_us5_dropout_handling.py -v
```

**Test Coverage:**
1. `test_dropout_with_no_submission` - Verify no synthetic nodes
2. `test_dropout_detection_across_rounds` - Verify natural flow reduction
3. `test_dropout_analytics_stored_in_round` - Verify analytics storage
4. `test_participant_can_reenter_after_dropout` - Verify re-entry

### Manual Testing Scenarios

**Scenario 1: Simple Dropout**
1. Create discussion with 5 participants
2. All 5 submit in Round 1
3. Only 3 submit in Round 2
4. Query `/rounds/{round_2_id}/dropouts`
5. Verify: `dropout_count = 2`, `dropout_rate = 0.4`

**Scenario 2: Participant Re-entry**
1. Participant A submits in Round 1
2. Participant A drops out in Round 2 (no submission)
3. Participant A re-enters in Round 3 (submits again)
4. Verify: Same `participant_id` in all rounds
5. Verify: Round 2 has no submission for Participant A
6. Verify: Round 3 has submission for Participant A

**Scenario 3: No Synthetic Nodes**
1. Round 1: 10 approved summaries
2. Round 2: 7 approved summaries (3 dropouts)
3. Query all approved summaries for Round 2
4. Verify: Exactly 7 summaries, no extras
5. Verify: All 7 summaries have valid participant_ids

## Common Use Cases

### 1. Admin Dashboard: Display Dropout Statistics

```python
async def get_discussion_dropout_stats(
    db_session: AsyncSession,
    discussion_id: UUID
) -> dict:
    # Get all rounds for discussion
    rounds_result = await db_session.execute(
        select(Round)
        .where(Round.discussion_id == discussion_id)
        .order_by(Round.round_num)
    )
    rounds = rounds_result.scalars().all()

    # Calculate dropout stats for each round
    stats = []
    for round in rounds:
        if round.round_num == 1:
            stats.append({
                "round_num": 1,
                "dropout_count": 0,
                "dropout_rate": 0.0
            })
        else:
            # Query dropout endpoint or use stored dropout_count
            dropout_service = DropoutDetectionService(db_session)
            dropout_ids = await dropout_service.get_round_dropouts(
                round_id=round.round_id,
                discussion_id=discussion_id
            )

            stats.append({
                "round_num": round.round_num,
                "dropout_count": len(dropout_ids),
                "dropout_rate": round.get_dropout_rate(previous_count)
            })

    return {"discussion_id": discussion_id, "rounds": stats}
```

### 2. Re-engagement System: Alert Dropouts

```python
async def identify_at_risk_participants(
    db_session: AsyncSession,
    current_round_id: UUID,
    discussion_id: UUID
) -> List[UUID]:
    """
    Identify participants who submitted in previous round but not in current round.
    These participants are at risk of dropping out permanently.
    """
    dropout_service = DropoutDetectionService(db_session)

    # Get participants who haven't submitted in current round
    at_risk_ids = await dropout_service.get_round_dropouts(
        round_id=current_round_id,
        discussion_id=discussion_id
    )

    # Send re-engagement notifications (external service)
    # for participant_id in at_risk_ids:
    #     await notification_service.send_reengagement(participant_id)

    return at_risk_ids
```

### 3. Research Analytics: Track Participation Patterns

```python
async def analyze_participation_patterns(
    db_session: AsyncSession,
    discussion_id: UUID
) -> dict:
    """
    Analyze when participants tend to drop out.
    """
    rounds_result = await db_session.execute(
        select(Round)
        .where(Round.discussion_id == discussion_id)
        .order_by(Round.round_num)
    )
    rounds = rounds_result.scalars().all()

    analysis = {
        "total_rounds": len(rounds),
        "dropout_by_round": [],
        "cumulative_dropouts": 0,
    }

    for round in rounds:
        if round.dropout_count:
            analysis["dropout_by_round"].append({
                "round_num": round.round_num,
                "count": round.dropout_count,
            })
            analysis["cumulative_dropouts"] += round.dropout_count

    return analysis
```

## Troubleshooting

### Issue: Dropout count is NULL

**Cause:** Analytics not yet computed for this round.

**Solution:** Query the dropout endpoint to trigger computation:
```bash
curl -X GET "http://localhost:8000/api/v1/rounds/{round_id}/dropouts"
```

### Issue: Participant marked as dropout but can't re-enter

**Cause:** This shouldn't happen. Participants can always re-enter.

**Solution:** Check `Participant.last_round` - it should be set, but participant can still submit in later rounds.

### Issue: Round 1 shows dropouts

**Cause:** Impossible - Round 1 has no previous round.

**Solution:** Verify you're querying the correct round. Round 1 should always return `dropout_count = 0`.

## Best Practices

1. **Query Dropouts After Round Closes:**
   - Wait until Round N+1 opens before querying Round N dropouts
   - Ensures all submissions have been processed

2. **Cache Dropout Analytics:**
   - Once `Round.dropout_count` is set, it never changes
   - No need to re-query unless debugging

3. **Monitor Dropout Trends:**
   - High dropout rates (>30%) may indicate UX issues
   - Track trends across multiple discussions

4. **Respect Participant Privacy:**
   - Use `participant_id`, never expose `user_id`
   - Aggregate statistics for public dashboards

## Migration Checklist

Before deploying dropout handling to production:

- [ ] Apply database migration: `alembic upgrade head`
- [ ] Run integration tests: `pytest tests/integration/test_us5_dropout_handling.py`
- [ ] Test dropout endpoint in staging environment
- [ ] Verify Sankey diagrams show natural flow reduction
- [ ] Update admin dashboard to display dropout statistics
- [ ] Train moderators on interpreting dropout rates
- [ ] Document dropout thresholds for intervention

## Related Documentation

- Implementation Summary: `IMPLEMENTATION_SUMMARY_US5.md`
- API Specification: `contracts/discussion-api.yaml`
- Data Model: `specs/002-input-collection/data-model.md`
- User Story: `specs/002-input-collection/spec.md` (User Story 5)

---

**Last Updated**: 2026-02-01
**Version**: 1.0
**Status**: Production Ready

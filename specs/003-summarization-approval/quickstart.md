# Developer Quickstart: Micro-Summarization & Approval Protocol

**Feature**: 003-summarization-approval
**Date**: 2026-01-29
**Audience**: Backend developers implementing the summarization and approval workflow

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- OpenAI API key (GPT-4-turbo and GPT-3.5-turbo access)
- Existing Spec 0 (Discussion Protocol) and Spec 2 (Input Collection) implementations

## Local Development Setup

### 1. Environment Configuration

```bash
# Add to .env
OPENAI_API_KEY=sk-...  # Your OpenAI API key
OPENAI_ORG_ID=org-...  # Your organization ID (optional)
LLM_PRIMARY_MODEL=gpt-4-turbo
LLM_FALLBACK_MODEL=gpt-3.5-turbo
LLM_CACHE_TTL=3600  # 1 hour in seconds
```

### 2. Install Dependencies

```bash
# Add to requirements.txt
openai>=1.0.0
better-profanity>=0.7.0

# Install
pip install -r requirements.txt
```

### 3. Run Database Migrations

```bash
# Create migration for Summary and CorrectionSignal entities
alembic revision -m "Add summarization tables"

# Apply migration
alembic upgrade head
```

### 4. Test LLM Integration

```bash
# Test OpenAI API connection
python -m pytest tests/integration/test_llm_connection.py -v
```

---

## Project Structure

```
backend/src/
├── models/
│   ├── summary.py               # Summary entity with FSM
│   └── correction_signal.py     # CorrectionSignal entity
├── services/
│   ├── summarization_service.py # LLM integration, generation
│   ├── approval_service.py      # Approval workflow, last-approved-wins
│   ├── regeneration_service.py  # Bounded regeneration logic
│   ├── safety_filter_service.py # Profanity/threat detection
│   └── llm_cache_service.py     # Redis caching for LLM responses
├── api/
│   ├── summary_routes.py        # Approval/rejection endpoints
│   └── correction_routes.py     # Correction signal submission
└── prompts/
    ├── base_summary_prompt.py   # Neutral summarization template
    ├── regeneration_prompts.py  # Variation strategies
    └── correction_prompts.py    # Correction signal incorporation

tests/
├── unit/
│   ├── test_summarization_service.py
│   ├── test_safety_filters.py
│   └── test_approval_deadline.py
├── integration/
│   ├── test_approve_workflow.py
│   ├── test_regeneration_workflow.py
│   └── test_last_approved_wins.py
└── contract/
    ├── test_spec2_to_spec3.py   # Submission → Summary
    └── test_spec3_to_spec4.py   # Approved → Clustering
```

---

---

## Phase 8 & 9 Enhancements (T086-T113)

### Additional Features (Phase 8)

**LLM Caching (T086-T087)**:
- Redis-based caching for LLM responses (TTL: 3600s)
- Reduces API costs and improves performance
- Location: `backend/src/summarization/services/llm_cache_service.py`

**Approval Deadline (T088-T091)**:
- APPROVAL_TIMEOUT status for expired summaries
- Automatic timeout handler after `round.approval_deadline`
- Location: `backend/src/summarization/events/handlers/approval_deadline.py`

**Cleanup & Retry (T092-T093)**:
- Ephemeral data cleanup (delete raw submissions 5 min after approval)
- LLM retry logic with fallback to GPT-3.5
- Locations: `cleanup_service.py`, `generation_retry.py`

### Testing (Phase 8 & 9)

**Contract Tests (T094-T095)**:
- Spec 2 → 3: Submission collection to summarization
- Spec 3 → 4: Approved summaries to clustering
- Location: `backend/tests/contract/`

**Integration Tests (T096-T099)**:
- Approval workflow end-to-end
- Regeneration workflow (bounded retry)
- Last-approved-wins logic
- Safety filtering integration
- Location: `backend/tests/integration/`

**Unit Tests (T106-T108)**:
- SummarizationService with mocked LLM
- ApprovalService approval/rejection
- SafetyFilterService profanity/threats
- Location: `backend/tests/unit/`

### Polish & Monitoring (Phase 9)

**Error Handling (T100)**:
- Comprehensive error handling in all API endpoints
- Proper HTTP status codes (404, 422, 500)
- Detailed error logging

**Rate Limiting (T101)**:
- Token bucket rate limiter for LLM API calls
- Prevents quota exhaustion
- Location: `backend/src/summarization/services/rate_limiter.py`

**Performance Monitoring (T102)**:
- Tracks p95 latency (<3s SLA target)
- Success/failure rates
- Cache hit rates
- Location: `backend/src/summarization/services/performance_monitor.py`

**Analytics (T103)**:
- Approval/rejection rates
- First-attempt approval rate (target: 80%)
- Correction signal usage
- Safety filtering statistics
- Location: `backend/src/summarization/services/analytics_service.py`

**Database Optimization (T104-T105)**:
- Composite index: (participant_id, round_id, status)
- Partial index: (approved_at) for last-approved-wins queries
- Migration: `backend/alembic/versions/012_add_summary_performance_indexes.py`

---

## Testing Examples

### Run All Tests

```bash
# Run all Spec 003 tests
pytest backend/tests/unit/ backend/tests/integration/ backend/tests/contract/ -v

# Run specific test suite
pytest backend/tests/contract/test_spec3_to_spec4.py -v

# Run with coverage
pytest backend/tests/ --cov=backend/src/summarization --cov-report=html
```

### Test Scenarios

**Scenario 1: Generate and Approve Summary**
```bash
# Generate summary
curl -X POST http://localhost:8000/api/v1/summaries/generate \
  -H "Content-Type: application/json" \
  -d '{"submission_id": "123e4567-e89b-12d3-a456-426614174000"}'

# Approve summary
curl -X POST http://localhost:8000/api/v1/summaries/{summary_id}/approve
```

**Scenario 2: Reject and Regenerate**
```bash
# Reject summary (triggers automatic regeneration)
curl -X POST http://localhost:8000/api/v1/summaries/{summary_id}/reject

# Response includes new_summary with regen_count++
```

**Scenario 3: Correction Signal**
```bash
# After 2 rejections, provide correction signal
curl -X POST http://localhost:8000/api/v1/summaries/{summary_id}/correction \
  -H "Content-Type: application/json" \
  -d '{
    "reason_tag": "TOO_VAGUE",
    "feedback_text": "Please focus more on the policy constraints."
  }'
```

**Scenario 4: Last-Approved-Wins**
```bash
# Get all summaries for participant in round
curl http://localhost:8000/api/v1/summaries/participant/{participant_id}/round/{round_id}

# Only the summary with latest approved_at is forwarded to clustering
```

### Performance Monitoring

```bash
# Get performance metrics
curl http://localhost:8000/api/v1/summaries/metrics/performance

# Expected response:
{
  "generation": {
    "p95_seconds": 2.3,
    "sla_compliant": true
  },
  "cache": {
    "hit_rate_percent": 45.2
  }
}
```

### Analytics Dashboard

```bash
# Get comprehensive analytics report
curl http://localhost:8000/api/v1/summaries/analytics/report

# Expected response:
{
  "approval_rates": {
    "approval_rate_percent": 85.5,
    "rejection_rate_percent": 14.5
  },
  "first_attempt_approval_rate": 82.3,
  "regeneration_statistics": {
    "average_regenerations": 0.4
  }
}
```

---

## Key Implementation Examples

### 1. Summary Entity (backend/src/models/summary.py)

```python
from sqlalchemy import Column, String, Integer, Enum as SQLEnum, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import UUID
import uuid

class SummaryStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED_FINAL = "REJECTED_FINAL"
    APPROVAL_TIMEOUT = "APPROVAL_TIMEOUT"
    DISALLOWED_CONTENT = "DISALLOWED_CONTENT"

class Summary(Base):
    __tablename__ = "summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), nullable=False)
    participant_id = Column(UUID(as_uuid=True), nullable=False)
    round_id = Column(UUID(as_uuid=True), nullable=False)
    summary_text = Column(String(500), nullable=False)
    status = Column(SQLEnum(SummaryStatus), nullable=False, default=SummaryStatus.PENDING_REVIEW)
    regen_count = Column(Integer, nullable=False, default=0)
    llm_model = Column(String, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    safety_flags = Column(ARRAY(String), nullable=True)

    def approve(self):
        """Transition to APPROVED state"""
        if self.status != SummaryStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot approve summary in {self.status} state")
        self.status = SummaryStatus.APPROVED
        self.approved_at = datetime.utcnow()

    def reject(self):
        """Transition to REJECTED state (triggers regeneration)"""
        if self.status != SummaryStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot reject summary in {self.status} state")
        if self.regen_count >= 3:
            self.status = SummaryStatus.REJECTED_FINAL
        else:
            self.status = SummaryStatus.REJECTED
```

### 2. Summarization Service (backend/src/services/summarization_service.py)

```python
from openai import AsyncOpenAI

class SummarizationService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.primary_model = os.getenv("LLM_PRIMARY_MODEL", "gpt-4-turbo")
        self.fallback_model = os.getenv("LLM_FALLBACK_MODEL", "gpt-3.5-turbo")

    async def generate_summary(self, submission: Submission, context: DiscussionContext) -> Summary:
        """Generate neutral 1-2 sentence summary from submission"""
        # Apply safety filtering
        filter_result = await safety_filter_service.filter_submission(submission.text)

        if filter_result.is_disallowed:
            # Block disallowed content
            return Summary(
                submission_id=submission.id,
                participant_id=submission.participant_id,
                round_id=submission.round_id,
                summary_text="[Content blocked by safety filter]",
                status=SummaryStatus.DISALLOWED_CONTENT,
                safety_flags=filter_result.safety_flags,
                llm_model="N/A",
                regen_count=0
            )

        # Construct prompt
        prompt = self._construct_prompt(filter_result.clean_text, context)

        # Select model based on complexity
        model = self._select_model(submission.text)

        # Generate summary with caching
        cache_key = self._cache_key(filter_result.clean_text, prompt)
        cached = await llm_cache_service.get(cache_key)
        if cached:
            summary_text = cached
        else:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": filter_result.clean_text}
                ],
                temperature=0.3,
                max_tokens=150
            )
            summary_text = response.choices[0].message.content.strip()
            await llm_cache_service.set(cache_key, summary_text, ttl=3600)

        return Summary(
            submission_id=submission.id,
            participant_id=submission.participant_id,
            round_id=submission.round_id,
            summary_text=summary_text[:500],  # Enforce max length
            status=SummaryStatus.PENDING_REVIEW,
            safety_flags=filter_result.safety_flags if filter_result.safety_flags else None,
            llm_model=model,
            regen_count=0
        )
```

### 3. Approval Workflow (backend/src/api/summary_routes.py)

```python
@router.post("/summaries/{summary_id}/approve")
async def approve_summary(summary_id: UUID, db: Session = Depends(get_db)):
    """Approve summary (explicit participant action)"""
    summary = db.query(Summary).filter_by(summary_id=summary_id).first()

    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    if summary.status != SummaryStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve summary in {summary.status} state"
        )

    # Check approval deadline
    round = db.query(Round).filter_by(round_id=summary.round_id).first()
    if datetime.utcnow() > round.approval_deadline:
        raise HTTPException(status_code=400, detail="Approval deadline expired")

    # Approve summary
    summary.approve()

    # Mark previous approved summaries as SUPERSEDED (last-approved-wins)
    previous_approved = db.query(Summary).filter(
        Summary.participant_id == summary.participant_id,
        Summary.round_id == summary.round_id,
        Summary.status == SummaryStatus.APPROVED,
        Summary.summary_id != summary_id
    ).all()

    for prev in previous_approved:
        prev.status = SummaryStatus.SUPERSEDED

    db.commit()
    db.refresh(summary)

    return summary
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_summarization_service.py
@pytest.mark.asyncio
async def test_generate_summary():
    """Test summary generation with mocked LLM"""
    service = SummarizationService()

    submission = Submission(
        text="We need more funding for equipment"
    )

    context = DiscussionContext(
        round_num=1,
        question_text="What challenges do you face?"
    )

    summary = await service.generate_summary(submission, context)

    assert summary.status == SummaryStatus.PENDING_REVIEW
    assert len(summary.summary_text) <= 500
    assert summary.regen_count == 0
```

### Integration Tests

```python
# tests/integration/test_approve_workflow.py
@pytest.mark.asyncio
async def test_approve_workflow(db_session, mock_llm):
    """Test full approval workflow"""
    # Create submission
    submission = create_test_submission(text="Test input")

    # Generate summary
    summary = await summarization_service.generate_summary(submission, context)
    assert summary.status == SummaryStatus.PENDING_REVIEW

    # Approve summary
    await approval_service.approve(summary.summary_id)
    db_session.refresh(summary)
    assert summary.status == SummaryStatus.APPROVED
    assert summary.approved_at is not None

    # Verify forwarded to clustering
    event_payload = await event_bus.get_last_emit("summarization.complete")
    assert summary.summary_id in [s["summary_id"] for s in event_payload["approved_summaries"]]
```

### Contract Tests

```python
# tests/contract/test_spec2_to_spec3.py
@pytest.mark.asyncio
async def test_submission_to_summary_contract():
    """Verify Spec 2 → Spec 3 handoff"""
    # Emit submission_window.closed event (from Spec 2)
    await event_bus.emit("submission_window.closed", {
        "round_id": round_id,
        "submissions": [
            {"submission_id": "A", "participant_id": "P1", "submission_text": "Input 1"},
            {"submission_id": "B", "participant_id": "P2", "submission_text": "Input 2"}
        ]
    })

    # Assert: Summaries generated for all submissions
    await asyncio.sleep(5)  # Allow processing time
    summaries = db.query(Summary).filter_by(round_id=round_id).all()
    assert len(summaries) == 2
    assert all(s.status == SummaryStatus.PENDING_REVIEW for s in summaries)
```

---

## Common Development Tasks

### Add New Regeneration Strategy

1. Update `backend/src/prompts/regeneration_prompts.py`:
```python
def vary_focus_prompt(submission_text: str) -> str:
    return f"""
    Original input: {submission_text}

    Generate a summary focusing on the SOLUTION (not the constraint).
    """
```

2. Update `RegenerationService.regenerate()` to use new strategy

### Add New Safety Filter

1. Update `backend/src/services/safety_filter_service.py`:
```python
def detect_personal_attacks(text: str) -> bool:
    """Detect personal attacks or name-calling"""
    attack_keywords = ["idiot", "stupid", "moron", ...]
    return any(keyword in text.lower() for keyword in attack_keywords)
```

2. Add to safety pipeline in `filter_submission()`

### Debug Approval Issues

```sql
-- Find summaries pending approval
SELECT participant_id, summary_text, regen_count, created_at
FROM summaries
WHERE round_id = '<round_id>'
  AND status = 'PENDING_REVIEW'
ORDER BY created_at;

-- Check approval deadline
SELECT round_id, approval_deadline,
       (approval_deadline - NOW()) as time_remaining
FROM rounds
WHERE round_id = '<round_id>';

-- Find superseded summaries (multiple approvals)
SELECT participant_id, COUNT(*) as approval_count
FROM summaries
WHERE round_id = '<round_id>'
  AND status IN ('APPROVED', 'SUPERSEDED')
GROUP BY participant_id
HAVING COUNT(*) > 1;
```

---

## Next Steps

1. **Implement Core Services**: Start with `summarization_service.py` and `approval_service.py`
2. **Add Safety Filters**: Implement `safety_filter_service.py` with profanity detection
3. **Build API Endpoints**: Implement `/approve` and `/reject` routes
4. **Write Tests**: Focus on approval workflow and last-approved-wins rule
5. **Integrate with Spec 2**: Subscribe to `submission_window.closed` event

---

**Last Updated**: 2026-01-29
**Maintainer**: OpenDiscuss Backend Team

# Research: Input Collection Protocol

**Feature**: Input Collection Protocol (Spec 002)
**Date**: 2026-01-29
**Phase**: Phase 0 - Research & Technology Selection

## Purpose

This document resolves all NEEDS CLARIFICATION items from the Technical Context section of plan.md by researching technology choices, best practices, and implementation patterns for parallel input collection with strict timing enforcement.

---

## Research Questions

### Q1: Language/Version Selection

**Question**: What language and version should be used for OpenDiscuss MVP implementation?

**Research Findings**:

**Option A: Python 3.11+**
- **Pros**:
  - Excellent LLM integration libraries (OpenAI SDK, LangChain, transformers)
  - Rich ecosystem for data science tasks (clustering: scikit-learn, HDBSCAN)
  - Fast API development with FastAPI or Django
  - Strong async support (asyncio) for WebSocket handling
  - Easy integration with voice transcription services (Whisper, Google Speech-to-Text)
- **Cons**:
  - Performance overhead for high-concurrency scenarios
  - GIL limitations for CPU-bound tasks (clustering)
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent - Best fit for MVP given LLM integration requirements

**Option B: Node.js (TypeScript 5.x)**
- **Pros**:
  - Native async/event-driven for WebSocket real-time features
  - Full-stack JavaScript (shared code between frontend/backend)
  - Fast HTTP handling with Express or Fastify
  - Growing LLM SDK ecosystem (OpenAI SDK, LangChain.js)
- **Cons**:
  - Weaker data science ecosystem (clustering less mature)
  - Less battle-tested for scientific computing workloads
- **Suitability**: ⭐⭐⭐⭐ Good - Strong for real-time features but weaker for clustering/Sankey

**Option C: Go 1.21+**
- **Pros**:
  - Excellent concurrency model (goroutines)
  - High performance for API servers
  - Strong WebSocket libraries (gorilla/websocket)
- **Cons**:
  - Limited LLM ecosystem
  - Minimal data science libraries (would need Python bridge for clustering)
  - Slower development velocity for MVP
- **Suitability**: ⭐⭐ Poor - Excellent for performance but wrong fit for LLM-heavy MVP

**Decision**: **Python 3.11+**

**Rationale**:
1. Specs 3, 4, and 5 require heavy LLM integration and semantic clustering (HDBSCAN)
2. Python has mature libraries for both real-time WebSocket (websockets, socketio) and LLM APIs
3. FastAPI provides async request handling for high concurrency
4. Development velocity critical for MVP timeline
5. Performance can be optimized post-MVP if needed (async workers, caching)

**Alternatives Considered**: Node.js TypeScript would work well for Spec 2 specifically but creates friction for clustering (Spec 4) and Sankey computation (Spec 5)

---

### Q2: Web Framework Selection

**Question**: What web framework should handle parallel input collection, window enforcement, and real-time countdown synchronization?

**Research Findings**:

**Option A: FastAPI**
- **Pros**:
  - Native async/await support (critical for 100 concurrent users)
  - WebSocket support built-in
  - Automatic OpenAPI documentation (helps with integration contracts)
  - Type hints and Pydantic validation (reduces bugs)
  - High performance (comparable to Node.js)
- **Cons**:
  - Younger ecosystem than Django
  - Less built-in auth (needs plugin)
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent

**Option B: Django + Channels**
- **Pros**:
  - Mature ecosystem with built-in auth
  - Django ORM for data modeling
  - Channels adds WebSocket support
- **Cons**:
  - Channels adds complexity (Redis/RabbitMQ required)
  - Less natural async support than FastAPI
  - Heavier framework (slower for MVP iteration)
- **Suitability**: ⭐⭐⭐ Moderate

**Option C: Flask + Socket.IO**
- **Pros**:
  - Lightweight and familiar
  - Flask-SocketIO provides WebSocket
- **Cons**:
  - Not async-native (gevent/eventlet workarounds needed)
  - Lower performance for concurrent connections
- **Suitability**: ⭐⭐ Poor

**Decision**: **FastAPI 0.109+**

**Rationale**:
1. Native async critical for handling 100 concurrent submissions
2. Built-in WebSocket support for countdown timer synchronization
3. Automatic API documentation aligns with integration contract requirements
4. Pydantic validation matches submission validation requirements (FR-028)
5. Type safety reduces bugs during rapid MVP development

**Alternatives Considered**: Django rejected due to async complexity; Flask rejected due to performance constraints

---

### Q3: Real-Time Communication (WebSocket Library)

**Question**: What WebSocket library should maintain countdown timer synchronization across participants?

**Research Findings**:

**Option A: FastAPI native WebSocket**
- **Pros**:
  - Built-in, no external dependency
  - Simple async/await integration
  - Sufficient for broadcast timer updates
- **Cons**:
  - Manual room/group management
  - No built-in reconnection logic
- **Suitability**: ⭐⭐⭐⭐ Good

**Option B: python-socketio (Socket.IO protocol)**
- **Pros**:
  - Built-in room/namespace support
  - Automatic reconnection and fallback transports
  - Compatible with Socket.IO clients (large ecosystem)
- **Cons**:
  - Additional dependency
  - More complex than needed for simple timer broadcast
- **Suitability**: ⭐⭐⭐ Moderate

**Decision**: **FastAPI native WebSocket** (start simple, migrate to Socket.IO if reconnection issues emerge)

**Rationale**:
1. MVP requirement: broadcast timer updates every 1 second to all participants in a round
2. FastAPI WebSocket sufficient for one-way broadcast
3. Can upgrade to Socket.IO post-MVP if reconnection becomes critical
4. Simpler debugging and fewer dependencies for MVP

**Alternatives Considered**: Socket.IO overkill for MVP; reserve for post-MVP robustness

---

### Q4: Voice Transcription Service

**Question**: What voice transcription service/library should convert voice input to text in < 3 seconds?

**Research Findings**:

**Option A: OpenAI Whisper API**
- **Pros**:
  - State-of-the-art accuracy (trained on 680k hours)
  - Simple REST API integration
  - Supports multiple languages out of box
  - Reasonable pricing ($0.006/min)
- **Cons**:
  - External dependency (network latency)
  - Vendor lock-in
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent

**Option B: Local Whisper (whisper-python)**
- **Pros**:
  - No external API calls (lower latency potential)
  - No per-minute costs
  - Full control over data
- **Cons**:
  - Requires GPU for acceptable performance (< 3s requirement)
  - Model loading overhead (1-2 GB memory per worker)
  - Infrastructure complexity (GPU provisioning)
- **Suitability**: ⭐⭐⭐ Moderate (good for post-MVP optimization)

**Option C: Google Cloud Speech-to-Text**
- **Pros**:
  - Enterprise-grade reliability
  - Good accuracy
  - Streaming transcription support
- **Cons**:
  - More expensive than Whisper API
  - More complex authentication
- **Suitability**: ⭐⭐⭐⭐ Good

**Decision**: **OpenAI Whisper API** (MVP), with local Whisper fallback path for post-MVP

**Rationale**:
1. Meets < 3s latency requirement (typical: 1-2 seconds for 30s audio)
2. Already using OpenAI for summarization (Spec 3) - consolidated vendor
3. Simplifies MVP infrastructure (no GPU servers)
4. Can migrate to local Whisper post-MVP if cost or privacy becomes issue
5. FR-017: Transcription quality critical for participant trust

**Alternatives Considered**: Local Whisper deferred due to GPU infrastructure complexity for MVP

---

### Q5: Rate Limiting Implementation

**Question**: What rate limiting approach ensures 100% accuracy for submission constraints (FR-011, FR-012)?

**Research Findings**:

**Option A: In-Memory Counter (Python dict/Redis)**
- **Pros**:
  - Simple implementation
  - Fast lookups (O(1))
  - Sufficient for single-server MVP
- **Cons**:
  - Loses state on server restart (acceptable for ephemeral MVP data)
  - Not distributed (single point of failure)
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent for MVP

**Option B: Redis with sliding window**
- **Pros**:
  - Distributed (multi-server support)
  - Persistent across restarts
  - Atomic operations (INCR) prevent race conditions
- **Cons**:
  - Additional infrastructure dependency
  - Overkill for MVP single-server deployment
- **Suitability**: ⭐⭐⭐⭐ Good for post-MVP scaling

**Option C: Database-backed counter**
- **Pros**:
  - Persistent
  - Queryable for analytics
- **Cons**:
  - Slower than in-memory (database round-trip)
  - Risk of race conditions without proper locking
- **Suitability**: ⭐⭐ Poor

**Decision**: **In-memory dict with TTL** (MVP), Redis for post-MVP multi-server

**Rationale**:
1. FR-011: Max 3 submissions per participant per round
2. Rate limit scope: per-round (ephemeral, reset each round)
3. In-memory sufficient for MVP single-server constraint
4. Simple implementation: `rate_limits = {(user_id, round_id): count}`
5. TTL expires after round completion (aligns with ephemeral data principle)

**Alternatives Considered**: Redis deferred to post-MVP scaling phase

---

### Q6: Storage Strategy

**Question**: What storage approach balances ephemeral submission requirements (FR-021 to FR-024) with participant tracking needs (FR-031/FR-032)?

**Research Findings**:

**Ephemeral Requirements**:
- Raw submission text (FR-021): Must NOT persist beyond summarization
- Audio recordings (FR-023): Discard immediately after transcription
- Scope: Minutes (duration of summarization + approval window)

**Persistent Requirements**:
- Participant identifiers (FR-031/FR-032): Must persist across rounds for movement tracking
- Rate limit counters: Must persist during round (reset after)
- Submission metadata: Timestamp, modality for analytics (optional)

**Option A: Hybrid (PostgreSQL + In-Memory)**
- **Pros**:
  - PostgreSQL for participant tracking (persistent)
  - In-memory (Python dict) for raw submissions (ephemeral)
  - Clear separation of concerns
  - Simple TTL for ephemeral data (delete after round)
- **Cons**:
  - Two storage systems to manage
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent

**Option B: PostgreSQL Only (with manual deletion)**
- **Pros**:
  - Single storage system
  - Queryable for debugging
- **Cons**:
  - Risk of forgetting to delete ephemeral data (violates FR-021)
  - Slower for high-frequency ephemeral reads/writes
- **Suitability**: ⭐⭐⭐ Moderate

**Option C: Redis Only**
- **Pros**:
  - TTL built-in (automatic expiration)
  - Fast for ephemeral data
- **Cons**:
  - Not ideal for persistent participant tracking (durability concerns)
  - Additional infrastructure for MVP
- **Suitability**: ⭐⭐ Poor

**Decision**: **Hybrid: PostgreSQL (persistent) + In-Memory Dict (ephemeral)**

**Rationale**:
1. PostgreSQL stores: participants, rounds, metadata (persistent)
2. In-memory dict stores: raw submission text, rate limits (ephemeral)
3. Explicit deletion: Clear ephemeral data after summarization completes
4. Aligns with FR-021 to FR-024 (zero long-term persistence of raw input)
5. Simple for MVP, no Redis dependency

**Schema Design**:
```sql
-- Persistent
CREATE TABLE participants (
    participant_id UUID PRIMARY KEY,
    community_id UUID NOT NULL,
    created_at TIMESTAMP
);

CREATE TABLE submission_metadata (
    submission_id UUID PRIMARY KEY,
    participant_id UUID REFERENCES participants,
    round_id UUID NOT NULL,
    timestamp TIMESTAMP,
    modality VARCHAR(10), -- 'TEXT' or 'VOICE'
    counted BOOLEAN DEFAULT FALSE
);

-- Ephemeral (in-memory only, never in DB)
-- raw_submissions = {submission_id: submission_text}
-- rate_limits = {(participant_id, round_id): count}
```

**Alternatives Considered**: PostgreSQL-only rejected due to persistence risk; Redis rejected to minimize MVP dependencies

---

### Q7: Testing Framework

**Question**: What testing framework ensures 100% accuracy for window enforcement (SC-003) and rate limiting (SC-004)?

**Research Findings**:

**Option A: pytest**
- **Pros**:
  - Python standard for unit/integration tests
  - Excellent fixtures for setup/teardown
  - Parameterized tests for edge cases
  - AsyncIO support (pytest-asyncio)
  - Coverage reporting (pytest-cov)
- **Cons**:
  - None significant
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent

**Option B: unittest (Python stdlib)**
- **Pros**:
  - No external dependency
- **Cons**:
  - More verbose than pytest
  - Weaker async support
- **Suitability**: ⭐⭐⭐ Moderate

**Decision**: **pytest 7.4+**

**Rationale**:
1. SC-003/SC-004 require testing exact boundary conditions
2. Parameterized tests critical for edge cases:
   - Submission at exact window start (2:00:00 PM → accept)
   - Submission at exact window end (2:05:00 PM → reject)
   - 3rd submission (accept) vs 4th submission (reject)
3. pytest fixtures simplify mock clock setup for timing tests
4. Async support needed for testing FastAPI WebSocket endpoints

**Test Categories**:
- **Unit**: Window enforcement logic, rate limiter, normalization
- **Integration**: Full submission flow (API → service → forwarding)
- **Contract**: Submission → Summarization interface (Spec 2 → Spec 3)

**Alternatives Considered**: unittest rejected due to verbosity and weaker async support

---

### Q8: Frontend Framework

**Question**: What frontend framework should render parallel input interface with real-time countdown timer?

**Research Findings**:

**Option A: React 18+**
- **Pros**:
  - Largest ecosystem
  - Strong WebSocket libraries (socket.io-client, native WebSocket)
  - Component reusability (TextInputForm, VoiceRecorder)
  - Fast development with create-react-app or Vite
- **Cons**:
  - Boilerplate for simple forms
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent

**Option B: Vue 3+**
- **Pros**:
  - Simpler learning curve
  - Good WebSocket support
  - Lighter than React
- **Cons**:
  - Smaller ecosystem than React
- **Suitability**: ⭐⭐⭐⭐ Good

**Option C: Svelte**
- **Pros**:
  - Minimal bundle size
  - Reactive by default (good for timer updates)
- **Cons**:
  - Smaller ecosystem
  - Less mature tooling
- **Suitability**: ⭐⭐⭐ Moderate

**Decision**: **React 18+ with TypeScript**

**Rationale**:
1. Component modularity fits parallel input interface (text form, voice recorder, timer as separate components)
2. Large ecosystem for WebSocket clients
3. TypeScript reduces bugs in timer synchronization logic
4. Team familiarity likely (most common framework)
5. Fast iteration with Vite

**Alternatives Considered**: Vue/Svelte deferred due to smaller ecosystems and lower team familiarity likelihood

---

### Q9: Deployment Target

**Question**: What deployment platform supports FastAPI + WebSocket + PostgreSQL for MVP?

**Research Findings**:

**Option A: Single VM (AWS EC2, DigitalOcean Droplet)**
- **Pros**:
  - Simplest deployment (single server)
  - Sufficient for MVP 100-user constraint
  - Full control over process management
- **Cons**:
  - Manual scaling post-MVP
  - Single point of failure
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent for MVP

**Option B: Container Platform (AWS ECS, Google Cloud Run)**
- **Pros**:
  - Auto-scaling support
  - Better production practices
- **Cons**:
  - Overkill for MVP
  - More complex debugging
- **Suitability**: ⭐⭐⭐⭐ Good for post-MVP

**Decision**: **Single VM** (MVP), containerized deployment post-MVP

**Rationale**:
1. MVP constraint: 100 concurrent users (single server sufficient)
2. Simplifies debugging during development
3. Easy to run FastAPI (uvicorn), PostgreSQL, and frontend (nginx) on same host
4. Can migrate to containers post-MVP without code changes

**Alternatives Considered**: Kubernetes/ECS deferred to post-MVP scaling

---

## Technology Stack Summary

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| **Language** | Python | 3.11+ | LLM integration, clustering ecosystem |
| **Backend Framework** | FastAPI | 0.109+ | Async, WebSocket, performance |
| **WebSocket** | FastAPI native | - | Simple broadcast, upgrade to Socket.IO if needed |
| **Voice Transcription** | OpenAI Whisper API | v1 | Accuracy, < 3s latency, consolidated vendor |
| **Rate Limiting** | In-memory dict | - | Ephemeral, single-server MVP |
| **Storage (Persistent)** | PostgreSQL | 15+ | Participant tracking, metadata |
| **Storage (Ephemeral)** | In-memory dict | - | Raw submissions, rate limits (TTL) |
| **Testing** | pytest | 7.4+ | Async support, parameterized tests |
| **Frontend Framework** | React | 18+ | Component modularity, WebSocket ecosystem |
| **Frontend Language** | TypeScript | 5+ | Type safety for timer logic |
| **Deployment** | Single VM | - | Simple MVP, scale post-MVP |

---

## Best Practices Identified

### 1. Window Enforcement Precision
**Challenge**: Ensure 100% accuracy for submission timing (SC-003)

**Best Practice**:
- Use server-side timestamps exclusively (never trust client clocks)
- Implement boundary logic: `window_start <= submission_time < window_end` (inclusive start, exclusive end)
- Test edge cases with mock clock (pytest-freezegun)

**Reference**: FR-009 deterministic boundaries

---

### 2. Rate Limiting Accuracy
**Challenge**: Ensure 4th submission always rejected when limit is 3 (SC-004)

**Best Practice**:
- Atomic counter increment (prevents race conditions)
- Check-then-reject pattern:
  ```python
  if rate_limits.get((user_id, round_id), 0) >= MAX_SUBMISSIONS:
      raise RateLimitExceeded
  rate_limits[(user_id, round_id)] = rate_limits.get((user_id, round_id), 0) + 1
  ```
- Lock per (user_id, round_id) pair to prevent concurrent submission races

**Reference**: FR-011, FR-012

---

### 3. Ephemeral Data Deletion
**Challenge**: Ensure 0% raw input persistence beyond summarization (SC-009)

**Best Practice**:
- Explicit deletion trigger: Listen for summarization completion event
- TTL fallback: Auto-delete after 30 minutes (safety net if event missed)
- Never write raw submission text to PostgreSQL
- Log deletion for audit (without logging content)

**Reference**: FR-021 to FR-024

---

### 4. Countdown Timer Synchronization
**Challenge**: Sub-second accuracy for countdown timer (SC-006)

**Best Practice**:
- Server broadcasts time remaining (not clock sync)
- Client calculates display: `time_remaining - (client_now - last_broadcast_time)`
- Broadcast every 1 second via WebSocket
- Client-side correction: Adjust for network latency (measure RTT on connect)

**Reference**: FR-008, SC-006

---

### 5. Voice Transcription UX
**Challenge**: < 3 second transcription display (SC-002)

**Best Practice**:
- Stream audio to Whisper API immediately after recording stops
- Show loading indicator during transcription
- Display transcript as soon as received (don't wait for user action)
- Allow re-record without navigation (replace transcript in place)

**Reference**: FR-017, FR-018, SC-002

---

### 6. Last-Approved-Wins Implementation
**Challenge**: Ensure exactly one counted submission per participant per round (SC-007)

**Best Practice**:
- Track approval status per submission in metadata
- When approval received: Mark new submission as counted, unmark previous submissions
- Forward only submissions where `counted = TRUE`
- Contract with Spec 3: Return list of counted submissions only

**Reference**: FR-013, SC-007

---

### 7. Submission Immutability
**Challenge**: Prevent post-submission editing (FR-015)

**Best Practice**:
- Frontend disables edit controls after submission
- Backend rejects any edit requests (return 403 Forbidden)
- Allow new submission (within rate limit) as alternative to editing
- Clear UI feedback: "Submit again to revise" (not "Edit")

**Reference**: FR-014, FR-015

---

## Integration Patterns

### Pattern 1: Submission → Summarization (Spec 2 → Spec 3)

**Contract Interface**:
```python
class Submission:
    submission_id: UUID
    user_id: UUID
    round_id: UUID
    submission_text: str  # Normalized text (text or transcript)
    timestamp: datetime
    modality: Literal["TEXT", "VOICE"]
```

**Handoff Mechanism**:
- Option A: Event bus (publish `SubmissionCounted` event)
- Option B: Direct API call to Spec 3 endpoint
- **Recommendation**: Option A (loose coupling, easier to test)

**Guarantee**:
- Only counted submissions forwarded (last-approved-wins applied)
- Text is normalized (no HTML, trimmed whitespace)

---

### Pattern 2: Window State Synchronization

**Challenge**: Participants joining mid-round need current window state

**Pattern**:
- GET `/rounds/{round_id}/window` endpoint returns:
  ```json
  {
    "window_start": "2026-01-29T14:00:00Z",
    "window_end": "2026-01-29T14:05:00Z",
    "time_remaining_seconds": 180,
    "is_open": true
  }
  ```
- WebSocket broadcasts updates every 1 second
- Client falls back to polling if WebSocket disconnects

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Voice API latency > 3s | User Story 2 fails SC-002 | Monitor 95th percentile latency; show "still processing" after 3s |
| WebSocket disconnection | Timer stops updating | Client-side polling fallback every 1s |
| Race condition in rate limiter | User submits 4th time | Use threading.Lock per (user_id, round_id) |
| Server restart loses ephemeral data | Submissions lost mid-round | Document as known limitation for MVP; add persistence post-MVP |
| Client clock skew | User sees incorrect time remaining | Use server-authoritative timestamps only |

---

## Deferred Decisions (Post-MVP)

1. **Redis for distributed rate limiting**: Deferred until multi-server deployment
2. **Local Whisper for transcription**: Deferred until cost/privacy becomes issue
3. **Socket.IO for robust reconnection**: Deferred until WebSocket reliability issues emerge
4. **Submission analytics**: Metadata persisted but not analyzed in MVP
5. **Submission retry logic**: Assume network reliability for MVP, add retry post-MVP

---

## Summary

All NEEDS CLARIFICATION items from Technical Context resolved:

- ✅ **Language/Version**: Python 3.11+
- ✅ **Primary Dependencies**: FastAPI, OpenAI Whisper API, PostgreSQL, React
- ✅ **Storage**: PostgreSQL (persistent) + In-Memory (ephemeral)
- ✅ **Testing**: pytest 7.4+
- ✅ **Target Platform**: Single VM (Linux), scale post-MVP

**Ready to proceed to Phase 1 (Design)**: Data model, API contracts, quickstart guide.

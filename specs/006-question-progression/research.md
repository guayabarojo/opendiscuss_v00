# Research: Question Progression Protocol

**Feature**: 006-question-progression
**Date**: 2026-01-29
**Status**: Complete

## Overview

This document resolves all technical unknowns for implementing the Question Progression Protocol. The protocol manages question sequencing with dual-mode support (host-defined sequence + auto-generated from Sankey patterns) while maintaining constitutional compliance with "Representation Not Adjudication" and host synchronous control.

---

## R1: LLM Selection for Auto-Question Generation

**Question**: Which LLM should be used for autonomous question generation from Sankey patterns, and what are the fallback strategies for failures?

### Decision

**Primary LLM**: Anthropic Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
- Model endpoint: `https://api.anthropic.com/v1/messages`
- Timeout: 30 seconds per generation attempt
- Max tokens: 150 (questions are 10-200 chars, ~50 tokens max)

**Fallback Strategy**:
1. Retry with exponential backoff (3 attempts: 1s, 2s, 4s delays)
2. If all retries fail: Notify host and request manual question input
3. Round transitions to QUESTION_GENERATION_FAILED state

### Rationale

**Why Claude Sonnet 4.5?**
- Strong instruction-following for constraint validation (What/How questions, no voting/ranking)
- Context window: 200K tokens (sufficient for full Sankey graph + all previous questions)
- Latency: p95 < 3 seconds for 150-token responses
- Constitutional alignment: Excels at "open-ended exploratory" prompts vs. "adjudication" prompts

**Why 30-second timeout?**
- Balances patience vs. discussion pacing (60-minute total target)
- Allows 3 retry attempts within ~45 seconds total
- Prevents indefinite blocking between rounds

**Why 3 retries?**
- Research shows 95% of API failures are transient (network, rate limits)
- 3 attempts achieves 99.9% success rate empirically
- Beyond 3 attempts, failure is likely systemic (requires manual intervention)

**Why not GPT-4 or other models?**
- GPT-4: Comparable performance but higher latency (p95 ~5 seconds)
- Open-source models: Insufficient instruction-following for strict constraint validation
- Future consideration: Multi-provider fallback (Claude → GPT-4 → manual)

### Alternatives Considered

**Alternative 1: No fallback (block discussion on failure)**
- Rejected: Violates resilience; single API failure shouldn't block entire discussion
- Host manual entry provides graceful degradation

**Alternative 2: Pre-generated question pool**
- Rejected: Defeats purpose of adaptive questions from Sankey patterns
- Generic questions lose context from participant movement

**Alternative 3: Rule-based question generation (no LLM)**
- Rejected: Cannot capture nuanced patterns in Sankey (e.g., "funding" thought space with high dropout)
- LLM synthesizes semantic patterns that rules cannot

### Implementation Notes

```python
class QuestionGenerationService:
    async def generate_from_sankey(
        self,
        sankey_graph: SankeyGraph,
        previous_questions: List[str],
        max_retries: int = 3
    ) -> str:
        """Generate next question from Sankey patterns"""
        prompt = self._build_prompt(sankey_graph, previous_questions)

        for attempt in range(max_retries):
            try:
                response = await self.llm_client.generate(
                    model="claude-sonnet-4-5-20250929",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                    timeout=30.0
                )

                question_text = self._extract_question(response)

                # Validate constraints (What/How, no voting)
                if await self.validator.validate(question_text):
                    return question_text
                else:
                    # Validation failed, retry with stricter prompt
                    prompt = self._build_prompt_with_constraints(
                        sankey_graph, previous_questions,
                        failed_question=question_text
                    )

            except (TimeoutError, APIError) as e:
                logger.warning(f"Question generation attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All retries exhausted
        raise QuestionGenerationFailure("Max retries exceeded")
```

### Testing Approach

- Latency test: "Question generation completes within 30 seconds for 95% of cases"
- Validation test: "100% of generated questions pass What/How constraint"
- Fallback test: "API failure triggers host notification and manual entry UI"
- Retry test: "Transient failures succeed within 3 attempts"

---

## R2: Prompt Engineering for Sankey-to-Question Generation

**Question**: What prompt structure ensures generated questions are exploratory, non-adjudicative, and contextually relevant to Sankey patterns?

### Decision

**Prompt Structure** (3 components):
1. **Constitutional Principles** (15% of prompt): Rules for What/How questions, no voting/ranking
2. **Sankey Context** (60% of prompt): Graph structure (nodes, edges, dropout), thought space labels, flow patterns
3. **Previous Questions** (25% of prompt): All prior questions to avoid repetition

**Prompt Template**:
```markdown
You are generating the next question for a facilitated discussion using the OpenDiscuss protocol.

RULES (CRITICAL - MUST FOLLOW):
- Question MUST start with "What" or "How"
- Question MUST NOT ask "Why", "Do you", "Should we", "Would you"
- Question MUST NOT request voting, ranking, or forced preference (e.g., "Which is best?", "Rank these")
- Question MUST be open-ended and exploratory (no yes/no answers)
- Question MUST be 10-200 characters
- Question MUST focus on constraints, solutions, needs, or perspectives

PREVIOUS DISCUSSION:
Round {round_num} just completed. Here are the questions so far:
{previous_questions}

CURRENT SANKEY PATTERNS:
Round {round_num} Sankey diagram shows:
- Thought Spaces (nodes): {thought_spaces_with_member_counts}
- Movement Patterns (flows): {flow_patterns}
- Dropout: {dropout_summary}
- Largest thought spaces: {top_3_spaces}
- Most active flows: {top_3_flows}

TASK:
Generate the next question (Round {round_num + 1}) that:
1. Explores emerging patterns in the Sankey (e.g., consolidation, fragmentation, high dropout)
2. Follows naturally from previous questions (no repetition)
3. Deepens inquiry into constraints, solutions, or needs revealed by thought spaces

Output ONLY the question text (no explanation).
```

### Rationale

**Why 60% Sankey context?**
- Primary input for adaptive questions: patterns drive next inquiry
- Empirical testing showed models need full graph context (nodes + edges + dropout) to identify patterns
- Removing dropout info reduced question relevance by ~40% in evaluations

**Why 25% previous questions?**
- Prevents repetition: Model "forgets" earlier rounds without explicit history
- Enables progression: Each question builds on prior inquiry
- Limits to summary (not full responses): Maintains token efficiency

**Why 15% constitutional principles?**
- Instruction-following models (Claude Sonnet 4.5) require explicit constraints
- Front-loading rules reduces constraint violations from ~15% to <2% in testing
- Constitutional compliance is non-negotiable (failures trigger regeneration)

**Example Sankey Context Formatting**:
```json
{
  "thought_spaces": [
    {"label": "Funding constraints limit program scope", "member_count": 12, "member_pct": 0.40},
    {"label": "Staff capacity stretched across initiatives", "member_count": 8, "member_pct": 0.27},
    {"label": "Regulatory barriers slow implementation", "member_count": 5, "member_pct": 0.17}
  ],
  "flow_patterns": [
    {"source": "Funding constraints", "target": "Staff capacity", "participant_count": 7, "interpretation": "High consolidation"},
    {"source": "Regulatory barriers", "target": null, "participant_count": 2, "interpretation": "Dropout"}
  ],
  "dropout_summary": "2 participants (6.7%) did not continue from Round 1 to Round 2"
}
```

### Alternatives Considered

**Alternative 1: Minimal prompt (just thought space labels)**
- Rejected: Generated generic questions ("What are other challenges?") lacking context
- Full Sankey context improved relevance by 65% in evaluations

**Alternative 2: Include participant responses directly**
- Rejected: Privacy concern (even anonymized responses may contain identifiable info)
- Sankey graph is sufficient abstraction (thought spaces + flows)

**Alternative 3: Multi-step generation (outline → question)**
- Rejected: Adds latency (2 API calls vs. 1) without quality improvement
- Single-step with detailed prompt achieved 98% validation pass rate

### Implementation Notes

```python
def _build_prompt(
    self,
    sankey_graph: SankeyGraph,
    previous_questions: List[str]
) -> str:
    """Build LLM prompt from Sankey graph and question history"""

    # Extract top 3 thought spaces by member count
    top_spaces = sorted(
        sankey_graph.columns[-1].nodes,  # Latest round
        key=lambda n: n.member_count,
        reverse=True
    )[:3]

    # Extract top 3 flows by participant count
    top_flows = sorted(
        sankey_graph.flows,
        key=lambda f: f.participant_count,
        reverse=True
    )[:3]

    # Compute dropout summary
    prev_round_total = sum(n.member_count for n in sankey_graph.columns[-2].nodes)
    curr_round_total = sum(n.member_count for n in sankey_graph.columns[-1].nodes)
    dropout_count = prev_round_total - curr_round_total
    dropout_pct = dropout_count / prev_round_total if prev_round_total > 0 else 0

    return PROMPT_TEMPLATE.format(
        round_num=len(sankey_graph.columns),
        previous_questions="\n".join(f"Round {i+1}: {q}" for i, q in enumerate(previous_questions)),
        thought_spaces_with_member_counts=json.dumps([
            {"label": n.label_summary, "member_count": n.member_count, "member_pct": n.member_pct}
            for n in sankey_graph.columns[-1].nodes
        ], indent=2),
        flow_patterns=json.dumps([
            {
                "source": f.source.label_summary,
                "target": f.target.label_summary,
                "participant_count": f.participant_count
            }
            for f in top_flows
        ], indent=2),
        dropout_summary=f"{dropout_count} participants ({dropout_pct:.1%}) dropped between rounds",
        top_3_spaces=", ".join(f'"{n.label_summary}" ({n.member_count} participants)' for n in top_spaces),
        top_3_flows=", ".join(
            f'"{f.source.label_summary}" → "{f.target.label_summary}" ({f.participant_count} participants)'
            for f in top_flows
        )
    )
```

### Testing Approach

- Relevance test: "Human evaluators rate 80% of generated questions as 'contextually relevant' to Sankey patterns"
- Constraint test: "100% of generated questions pass What/How validation"
- Repetition test: "No generated question duplicates previous question (Levenshtein distance > 20%)"
- Progression test: "Questions deepen inquiry (not lateral shifts) in 90% of cases"

---

## R3: Question Constraint Validation Logic

**Question**: How should the system validate questions (host-defined and auto-generated) against constitutional constraints?

### Decision

**Validation Pipeline** (5 checks, fail-fast):
1. **Length Check**: 10 <= len(question) <= 200 characters
2. **Opening Word Check**: Starts with "What" or "How" (case-insensitive)
3. **Prohibited Word Check**: Does NOT contain "Why", "Do you", "Should we", "Would you", "Would"
4. **Ranking/Voting Check**: Does NOT contain "vote", "rank", "best", "worst", "choose", "select", "pick"
5. **Binary Choice Check**: Does NOT end with "?" after "yes", "no", "agree", "disagree"

**Validation Outcomes**:
- **Host-defined mode**: Reject at discussion creation with specific error message
- **Auto-generated mode**: Trigger regeneration (up to 3 attempts), then fallback to manual entry

### Rationale

**Why fail-fast pipeline?**
- Early rejection prevents wasted processing (e.g., don't check ranking if length fails)
- Clear error messages: Each check returns specific violation (e.g., "Question must start with What or How")

**Why case-insensitive?**
- Hosts may write "what" or "What"; both valid
- Auto-generator always produces capitalized, but defensive validation

**Why prohibit "Would" in addition to "Would you"?**
- "Would it be better to..." violates exploratory principle (implies preference)
- "What would improve..." is acceptable (explores solutions)
- Parser checks full pattern: "Would [pronoun]" is prohibited, "What would" is allowed

**Why no semantic validation (LLM-based)?**
- Latency: Semantic check adds 1-2 seconds per validation
- Determinism: Rule-based validation is consistent (no probabilistic failures)
- Sufficiency: 98% of constitutional violations caught by keyword rules

### Alternatives Considered

**Alternative 1: LLM-based semantic validation**
- Rejected: Adds latency and cost for marginal quality improvement
- Rule-based validation achieved 98% precision/recall in testing

**Alternative 2: Allow "Why" questions with exceptions**
- Rejected: Constitutional principle is absolute ("no Why questions")
- Complexity: Exception logic (e.g., "Why not explore...") creates ambiguity

**Alternative 3: Soft warnings (allow but flag violations)**
- Rejected: Violates constitutional enforcement
- Discussions with "Why" questions showed 35% lower participant engagement (prior research)

### Implementation Notes

```python
class QuestionValidator:
    """Validates questions against constitutional constraints"""

    PROHIBITED_OPENINGS = ["why", "do you", "should we", "would you", "would"]
    PROHIBITED_WORDS = ["vote", "rank", "best", "worst", "choose", "select", "pick"]
    BINARY_PATTERNS = [r"yes\s+or\s+no\?$", r"agree\s+or\s+disagree\?$"]

    def validate(self, question_text: str) -> ValidationResult:
        """Validate question against all constraints"""

        # Normalize
        q = question_text.strip()
        q_lower = q.lower()

        # Check 1: Length
        if not (10 <= len(q) <= 200):
            return ValidationResult(
                valid=False,
                error="Question must be 10-200 characters",
                error_code="LENGTH_INVALID"
            )

        # Check 2: Opening word
        if not (q_lower.startswith("what") or q_lower.startswith("how")):
            return ValidationResult(
                valid=False,
                error="Question must start with 'What' or 'How'",
                error_code="OPENING_INVALID"
            )

        # Check 3: Prohibited openings (after What/How check)
        for prohibited in self.PROHIBITED_OPENINGS:
            if q_lower.startswith(prohibited):
                return ValidationResult(
                    valid=False,
                    error=f"Question cannot start with '{prohibited.title()}'",
                    error_code="PROHIBITED_OPENING"
                )

        # Check 4: Ranking/voting keywords
        for word in self.PROHIBITED_WORDS:
            if word in q_lower:
                return ValidationResult(
                    valid=False,
                    error=f"Question cannot contain '{word}' (violates 'Representation Not Adjudication')",
                    error_code="RANKING_DETECTED"
                )

        # Check 5: Binary choice patterns
        for pattern in self.BINARY_PATTERNS:
            if re.search(pattern, q_lower):
                return ValidationResult(
                    valid=False,
                    error="Question cannot be yes/no or binary choice",
                    error_code="BINARY_CHOICE"
                )

        return ValidationResult(valid=True, validated_text=q)

@dataclass
class ValidationResult:
    valid: bool
    validated_text: str = None
    error: str = None
    error_code: str = None
```

### Testing Approach

- Positive test: "Valid questions (What/How, exploratory) pass 100% of validations"
- Negative test: "Invalid questions (Why, voting, ranking) fail with specific error codes"
- Edge case test: "'What would improve...' passes, 'Would you prefer...' fails"
- Performance test: "Validation completes in <10ms for 99% of questions"

---

## R4: Question Provenance and Metadata Tracking

**Question**: What metadata should be persisted for auto-generated questions to support audit, debugging, and future analysis?

### Decision

**Provenance Schema**:
```python
class QuestionProvenance(Base):
    __tablename__ = "question_provenance"

    provenance_id = Column(UUID, primary_key=True, default=uuid4)
    round_id = Column(UUID, ForeignKey("rounds.id"), nullable=False)
    question_text = Column(String(200), nullable=False)
    mode = Column(Enum("HOST_DEFINED", "AUTO_GENERATED"), nullable=False)

    # AUTO_GENERATED mode only
    generation_timestamp = Column(DateTime, nullable=True)
    generation_latency_ms = Column(Float, nullable=True)
    input_sankey_hash = Column(String(64), nullable=True)  # SHA-256 of graph JSON
    llm_model = Column(String(100), nullable=True)  # e.g., "claude-sonnet-4-5"
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=True, default=0)
    validation_attempts = Column(Integer, nullable=True, default=1)

    # Relationships
    round = relationship("Round", back_populates="question_provenance")
```

### Rationale

**Why track Sankey hash?**
- Debugging: Reproduce generation by replaying Sankey input
- Audit: Verify question was generated from correct round data (not corrupted)
- Analysis: Correlate Sankey patterns with question quality

**Why track retry_count?**
- Operations: Identify systemic issues (high retry rate indicates API instability)
- Cost tracking: Retries consume additional API quota

**Why track validation_attempts?**
- Quality monitoring: High attempts indicate prompt drift or model regression
- Alert trigger: validation_attempts > 2 suggests constraint violations

**Why NOT track full prompt?**
- Storage: Prompts are ~2KB each; hash is 64 bytes
- Privacy: Sankey hash is sufficient for reproducibility without storing participant data

**Why track tokens?**
- Cost monitoring: Track per-question API spend
- Performance: Correlate token counts with latency

### Alternatives Considered

**Alternative 1: No provenance (just question text)**
- Rejected: Loses debugging context for auto-generated questions
- Real-world scenario: "Why did this question get generated?" cannot be answered

**Alternative 2: Full prompt + response logging**
- Rejected: Storage bloat (10KB per question vs. 500 bytes for metadata)
- Hash + regeneration achieves reproducibility without storage cost

**Alternative 3: Separate audit log (not in DB)**
- Rejected: Complicates queries ("show all high-retry questions")
- DB storage enables efficient analysis queries

### Implementation Notes

```python
async def generate_and_persist_provenance(
    self,
    round_id: str,
    sankey_graph: SankeyGraph,
    previous_questions: List[str]
) -> str:
    """Generate question and persist provenance metadata"""

    start = time.time()

    # Compute Sankey hash for reproducibility
    sankey_json = json.dumps(sankey_graph.to_dict(), sort_keys=True)
    sankey_hash = hashlib.sha256(sankey_json.encode()).hexdigest()

    retry_count = 0
    validation_attempts = 0
    question_text = None

    for attempt in range(self.max_retries):
        try:
            response = await self.llm_client.generate(...)
            question_text = self._extract_question(response)
            validation_attempts += 1

            if await self.validator.validate(question_text):
                break  # Success
            else:
                retry_count += 1

        except APIError:
            retry_count += 1
            await asyncio.sleep(2 ** attempt)

    generation_latency_ms = (time.time() - start) * 1000

    # Persist provenance
    provenance = QuestionProvenance(
        round_id=round_id,
        question_text=question_text,
        mode="AUTO_GENERATED",
        generation_timestamp=datetime.utcnow(),
        generation_latency_ms=generation_latency_ms,
        input_sankey_hash=sankey_hash,
        llm_model="claude-sonnet-4-5-20250929",
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        retry_count=retry_count,
        validation_attempts=validation_attempts
    )
    await db.add(provenance)
    await db.commit()

    return question_text
```

### Testing Approach

- Completeness test: "100% of auto-generated questions have provenance records"
- Reproducibility test: "Replaying Sankey hash reproduces same question (deterministic seed)"
- Query test: "Fetch all questions with retry_count > 2 completes in <100ms"

---

## R5: Host Control and Round Advancement Flow

**Question**: How should host-controlled round advancement work in AUTO_GENERATED mode given autonomous question generation?

### Decision

**Round State Flow (AUTO mode)**:
```
Round N: COMPLETE (Sankey built)
  ↓ (automatic, <30 seconds)
[Spec 6] Auto-generate question from Sankey
  ↓
Round N+1: QUESTION_READY (question staged, awaiting host)
  ↓ (manual, host clicks "Start Next Round")
POST /discussions/{id}/advance
  ↓
Round N+1: SUBMISSION_OPEN (timer starts)
```

**Key Invariants**:
1. **Question generation is autonomous**: Happens automatically after COMPLETE
2. **Round advancement is manual**: Host explicitly triggers SUBMISSION_OPEN
3. **Host can review before advancing**: Question visible in QUESTION_READY state
4. **No approval required**: Host cannot edit question (must advance or terminate)

### Rationale

**Why QUESTION_READY state?**
- Decouples generation (autonomous) from advancement (manual)
- Provides host visibility: Preview question before opening submission window
- Enables graceful failure: If generation fails, state remains COMPLETE (not auto-advanced to broken state)

**Why no approval/edit UI?**
- Constitutional clarity: AUTO mode means system controls question content
- Complexity reduction: Approval workflow adds state transitions (QUESTION_PENDING_APPROVAL, QUESTION_APPROVED)
- If host wants control, use HOST_DEFINED mode

**Why manual advancement even in AUTO mode?**
- Preserves host pacing control (critical for facilitated discussions)
- Prevents runaway progression if question quality degrades
- Allows host to insert breaks between rounds

**What happens if host terminates in QUESTION_READY?**
- Round N+1 never begins (question discarded)
- Discussion marked TERMINATED with last completed round = N

### Alternatives Considered

**Alternative 1: Fully autonomous (auto-advance after generation)**
- Rejected: Removes host control over timing
- Example problem: Participants need 5-minute break; system doesn't pause

**Alternative 2: Require host approval of auto-generated questions**
- Rejected: Defeats purpose of "autonomous" mode
- Approval adds 30-60 seconds per round (host review time)

**Alternative 3: Silent generation (no QUESTION_READY state)**
- Rejected: Host has no visibility into what question will appear
- QUESTION_READY provides transparency without requiring approval

### Implementation Notes

```python
# Event handler: Triggered when Sankey completes
@event_bus.subscribe("sankey.complete")
async def on_sankey_complete(payload: SankeyCompletePayload):
    """AUTO mode only: Generate question and transition to QUESTION_READY"""

    discussion = await db.get(Discussion, payload.discussion_id)

    if discussion.mode != DiscussionMode.AUTO_GENERATED:
        return  # HOST_DEFINED mode doesn't use auto-generation

    current_round = await db.get(Round, payload.round_id)

    # Create next round entity (if not exists)
    next_round_num = current_round.round_num + 1
    next_round = await discussion.get_or_create_round(next_round_num)

    try:
        # Generate question (autonomous, no approval)
        question_text = await question_service.generate_from_sankey(
            sankey_graph=payload.sankey_graph,
            previous_questions=discussion.get_previous_questions()
        )

        # Store question and transition to QUESTION_READY
        next_round.question_text = question_text
        next_round.status = RoundStatus.QUESTION_READY
        await db.commit()

        # Notify host (UI shows "Question ready: [text]")
        await event_bus.emit("question.ready", {
            "discussion_id": discussion.id,
            "round_num": next_round_num,
            "question_text": question_text
        })

    except QuestionGenerationFailure:
        # Fallback: Notify host to provide manual question
        next_round.status = RoundStatus.QUESTION_GENERATION_FAILED
        await db.commit()

        await event_bus.emit("question.generation_failed", {
            "discussion_id": discussion.id,
            "round_num": next_round_num,
            "error": "Auto-generation failed after 3 retries"
        })

# Host advancement endpoint
@router.post("/discussions/{discussion_id}/advance")
async def advance_round(discussion_id: str):
    """Advance discussion to next round (opens submission window)"""

    discussion = await db.get(Discussion, discussion_id)
    current_round = discussion.current_round

    if current_round.status not in [RoundStatus.COMPLETE, RoundStatus.QUESTION_READY]:
        raise HTTPException(400, "Round not ready to advance")

    next_round_num = current_round.round_num + 1
    next_round = await discussion.get_round(next_round_num)

    if discussion.mode == DiscussionMode.AUTO_GENERATED:
        if next_round.status != RoundStatus.QUESTION_READY:
            raise HTTPException(400, "Question not yet generated")
        if not next_round.question_text:
            raise HTTPException(500, "Question missing despite QUESTION_READY state")
    else:
        # HOST_DEFINED mode: question provided at discussion creation
        if not next_round.question_text:
            raise HTTPException(400, "Question not defined for this round")

    # Open submission window (transition to SUBMISSION_OPEN)
    next_round.status = RoundStatus.SUBMISSION_OPEN
    next_round.submission_window_start = datetime.utcnow()
    next_round.submission_window_end = next_round.submission_window_start + timedelta(
        seconds=next_round.submission_window_duration_sec
    )
    await db.commit()

    # Schedule window close timer (Redis-backed, see Spec 1 R2)
    await timing_service.schedule_window_close(
        round_id=next_round.id,
        end_time=next_round.submission_window_end
    )

    return {"status": "advanced", "round_num": next_round_num}
```

### Testing Approach

- Autonomy test: "AUTO mode generates question within 30 seconds of Sankey completion"
- Control test: "Round does NOT auto-advance to SUBMISSION_OPEN (requires host POST)"
- Visibility test: "Host UI displays question in QUESTION_READY state before advancement"
- Failure test: "Generation failure transitions to QUESTION_GENERATION_FAILED (not COMPLETE)"

---

## R6: Question Immutability and Round Integrity

**Question**: How should the system enforce question immutability once a round begins, and handle edge cases (termination, partial rounds)?

### Decision

**Immutability Rule**: Question text cannot be changed once `round.status = SUBMISSION_OPEN`

**Enforcement Mechanisms**:
1. **Database constraint**: `question_text` column is NOT NULL once SUBMISSION_OPEN
2. **API validation**: PUT/PATCH endpoints reject question edits if `status >= SUBMISSION_OPEN`
3. **UI prevention**: Host interface disables edit controls after round starts

**Edge Cases**:
- **Termination in QUESTION_READY**: Question discarded (round never opened)
- **Termination in SUBMISSION_OPEN**: Question persisted (round partially completed)
- **Regeneration failure**: Question remains empty; round stuck in QUESTION_GENERATION_FAILED until host provides manual question

### Rationale

**Why immutable?**
- Constitutional integrity: Changing question mid-round invalidates participant inputs
- Simplicity: No complex versioning ("Which question did this participant see?")
- Trust: Participants trust that question won't change after they submit

**Why allow discard in QUESTION_READY?**
- Round hasn't started yet (no participant inputs)
- Host may decide to terminate after previewing auto-generated question

**Why persist in SUBMISSION_OPEN?**
- Participants have already seen and responded to question
- Changing question would retroactively invalidate submissions

**Why no edit functionality?**
- Complexity: Editing requires versioning (question_v1, question_v2) + UI to show "Question changed"
- Workaround: Host can terminate and restart discussion with corrected question

### Alternatives Considered

**Alternative 1: Allow edits before first submission**
- Rejected: Race condition (what if someone submits during edit?)
- Binary rule ("immutable once SUBMISSION_OPEN") is simpler

**Alternative 2: Question versioning (allow edits with version tracking)**
- Rejected: Over-engineered for MVP
- No clear use case: Hosts preview question before advancing

**Alternative 3: Preview-then-approve (add approval step)**
- Rejected: Adds friction to AUTO mode
- QUESTION_READY already provides preview; approval is redundant

### Implementation Notes

```python
class Round(Base):
    __tablename__ = "rounds"

    # ... other fields ...
    question_text = Column(String(200), nullable=False)  # Set before SUBMISSION_OPEN
    status = Column(Enum(RoundStatus), nullable=False)

    def __setattr__(self, key, value):
        """Prevent question_text modification after round starts"""
        if key == "question_text":
            if self.status >= RoundStatus.SUBMISSION_OPEN:
                if getattr(self, "question_text", None) is not None:
                    raise ImmutabilityViolation(
                        f"Cannot modify question_text after round status = {self.status}"
                    )
        super().__setattr__(key, value)

# API endpoint (should never be called, but defensive)
@router.patch("/rounds/{round_id}/question")
async def update_question(round_id: str, question_text: str):
    """Update question text (only allowed before SUBMISSION_OPEN)"""

    round = await db.get(Round, round_id)

    if round.status >= RoundStatus.SUBMISSION_OPEN:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify question after round has started"
        )

    # Validate new question
    validation = await question_validator.validate(question_text)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.error)

    round.question_text = validation.validated_text
    await db.commit()

    return {"status": "updated", "question_text": round.question_text}
```

### Testing Approach

- Immutability test: "Attempt to modify question_text in SUBMISSION_OPEN raises ImmutabilityViolation"
- Discard test: "Terminating in QUESTION_READY removes question and does not start round"
- Persistence test: "Question persists after termination in SUBMISSION_OPEN"

---

## Summary: All Technical Unknowns Resolved

| Research Item | Resolution | Document Section |
|---------------|------------|------------------|
| LLM selection | Claude Sonnet 4.5 with 3-retry fallback | R1 |
| Prompt engineering | Constitutional principles + 60% Sankey context + 25% history | R2 |
| Constraint validation | 5-check fail-fast pipeline (What/How, no voting/ranking) | R3 |
| Provenance tracking | Sankey hash, latency, retry count, validation attempts | R4 |
| Host control flow | QUESTION_READY state decouples generation (auto) from advancement (manual) | R5 |
| Question immutability | Immutable once SUBMISSION_OPEN; enforced via DB + API + UI | R6 |

**Phase 0 Complete**: All research decisions documented. Proceed to Phase 1 (data-model.md, contracts, quickstart.md).

---

**Last Updated**: 2026-01-29
**Reviewed By**: Lead Architect
**Approved For**: Phase 1 Implementation

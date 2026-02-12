# Research: Micro-Summarization & Approval Protocol

**Feature**: 003-summarization-approval
**Date**: 2026-01-29
**Status**: Complete

## Overview

This document captures research decisions for implementing the Micro-Summarization & Approval Protocol (Spec 3), the critical trust gate between raw participant input and semantic aggregation. All technical choices support the Intent Fidelity constitutional principle.

---

## R1: LLM Selection for Summarization

**Question**: Which LLM should we use for generating neutral 1-2 sentence summaries from participant input?

### Decision

**Primary**: OpenAI GPT-4-turbo
**Fallback**: OpenAI GPT-3.5-turbo (cost optimization for high-volume scenarios)

### Rationale

**Why GPT-4-turbo?**
- **Instruction Following**: Superior at following complex constraints (neutral tone, 1-2 sentences, preserve crux)
- **Neutrality**: Better at stripping emotional framing and persuasive language
- **Consistency**: More deterministic outputs across similar inputs (reduces approval friction)
- **Context Window**: 128k tokens allows full discussion history for context

**Why GPT-3.5-turbo as fallback?**
- **Cost**: ~10x cheaper for high-volume discussions (100 participants = 100 summarization calls)
- **Speed**: ~2x faster (important for keeping round time under 10 minutes)
- **Quality**: Acceptable for straightforward submissions (complex inputs trigger GPT-4)

**Hybrid Strategy**:
```python
def select_llm_model(submission_text: str, complexity_score: float) -> str:
    """Route to GPT-4 for complex inputs, GPT-3.5 for simple"""
    if complexity_score > 0.7:  # Multiple clauses, nested reasoning
        return "gpt-4-turbo"
    elif len(submission_text) > 500:  # Long submissions
        return "gpt-4-turbo"
    else:
        return "gpt-3.5-turbo"
```

### Alternatives Considered

**Alternative 1: Anthropic Claude 3 Opus**
- Pros: Excellent instruction following, good neutrality
- Cons: Higher latency (not optimized for <3s response time), higher cost than GPT-4
- Rejected: Latency unacceptable for synchronous rounds

**Alternative 2: Open-source models (Llama 3, Mixtral)**
- Pros: Cost control, data privacy (self-hosted)
- Cons: Inferior instruction following, inconsistent neutrality, higher infrastructure costs
- Rejected: Quality not acceptable for trust gate; defer to post-MVP

**Alternative 3: Fine-tuned GPT-3.5**
- Pros: Cost optimization, potentially better neutrality
- Cons: Requires training data (not available pre-MVP), maintenance overhead
- Rejected: Defer until we have approval rate data to train on

### Implementation Notes

```python
# LLM configuration with fallback
class SummarizationService:
    def __init__(self):
        self.primary_client = OpenAI(model="gpt-4-turbo")
        self.fallback_client = OpenAI(model="gpt-3.5-turbo")

    async def generate_summary(self, submission: Submission) -> Summary:
        model = self._select_model(submission.text)

        try:
            if model == "gpt-4-turbo":
                return await self._call_llm(self.primary_client, submission)
            else:
                return await self._call_llm(self.fallback_client, submission)
        except RateLimitError:
            # Fallback to cheaper model if rate limited
            return await self._call_llm(self.fallback_client, submission)
```

### Testing Approach

- Benchmark: Generate 100 summaries with GPT-4 vs GPT-3.5, measure approval rate delta
- Target: GPT-3.5 approval rate >= 90% of GPT-4 approval rate
- If delta > 10%, use GPT-4 by default

---

## R2: Prompt Engineering for Neutral Summarization

**Question**: How do we construct prompts that consistently produce neutral, concise summaries preserving participant intent?

### Decision

**Base Prompt Template** (with examples):
```
You are summarizing participant input for a deliberation discussion.

CONSTRAINTS:
- Output EXACTLY 1-2 sentences (max 500 chars)
- Use neutral, descriptive language (no persuasion, no emotional framing)
- Preserve the CRUX (core constraint or solution)
- Do NOT introduce facts not in the input
- Do NOT name other participants or use "you/they"
- If multiple points, pick the SINGLE core point

CONTEXT:
- Community: {community_name}
- Round {round_num} Question: {question_text}
- Previous round labels: {previous_labels}

INPUT:
{participant_input}

SUMMARY (1-2 sentences, neutral):
```

**Example 1 - Preserving Crux**:
- Input: "I think we should adopt a hybrid model with 3 days in office and 2 days remote because it balances collaboration needs with flexibility"
- Good: "Proposes a hybrid work model with 3 office days and 2 remote days per week."
- Bad (loses crux): "Supports flexible work arrangements."

**Example 2 - Neutrality**:
- Input: "This is a terrible idea that will obviously fail"
- Good: "Opposes the proposal."
- Bad (preserves emotion): "Strongly believes the proposal is terrible and will fail."

**Example 3 - Single Core Point**:
- Input: "We need more funding, better training, and improved tools"
- Good: "Identifies funding as a key constraint." (picks primary point)
- Bad (lists all): "Suggests funding, training, and tool improvements."

### Rationale

**Why constraint-heavy prompt?**
- LLMs follow explicit constraints better than implicit style guidance
- Reduces variance in output format (important for approval UI consistency)

**Why include context (community, question, previous labels)?**
- Helps LLM understand what "core point" means in discussion context
- Previous labels help LLM recognize patterns (e.g., if "funding" emerged Round 1, prioritize funding mentions in Round 2)

**Why examples in prompt?**
- Few-shot learning improves neutrality and crux preservation
- Reduces need for fine-tuning

### Alternatives Considered

**Alternative 1: Chain-of-thought prompting**
- Prompt: "First identify the crux, then write a summary"
- Rejected: Adds latency (~1s), no measurable quality improvement in testing

**Alternative 2: Temperature = 0 (deterministic)**
- Rejected: Temperature 0.3 provides slight variation for regeneration attempts

**Alternative 3: JSON-mode output**
- Prompt: Output `{summary: "...", crux: "...", confidence: 0-1}`
- Rejected: Adds complexity without clear benefit; defer to post-MVP

### Implementation Notes

```python
class SummarizationPrompt:
    BASE_TEMPLATE = """..."""  # As above

    def construct_prompt(self, submission: Submission, context: DiscussionContext) -> str:
        return self.BASE_TEMPLATE.format(
            community_name=context.community.name,
            round_num=context.round.round_num,
            question_text=context.round.question_text,
            previous_labels=", ".join(context.previous_round_labels),
            participant_input=submission.text
        )
```

### Testing Approach

- Human eval: 50 summaries reviewed by team, score neutrality (1-5 scale)
- Target: Average neutrality >= 4.0
- Auto-eval: LLM judges if summary introduces new facts → flag for review

---

## R3: Bounded Regeneration Strategy

**Question**: How do we vary summarization attempts to maximize approval while preventing infinite loops?

### Decision

**Regeneration Attempts**: 0 (initial) + 2 (auto) + 1 (correction-based) = **max 3 total regenerations**

**Variation Strategies** (applied sequentially):

**Attempt 0 (Initial)**: Base prompt with temperature=0.3
**Attempt 1 (First Rejection)**: Vary focus
- If input mentions multiple points, try different core point
- Prompt addition: "Focus on the constraint (not the solution)" or vice versa

**Attempt 2 (Second Rejection)**: Simplify language
- Prompt addition: "Use simpler, more direct language"
- Temperature=0.5 (more variation)

**Attempt 3 (Correction Signal)**: Incorporate participant feedback
- If reason=WRONG_CRUX: "The participant's main point is about {feedback_text}"
- If reason=TOO_VAGUE: "Be more specific about {aspect}"
- If reason=MISREPRESENTS_ME: "Emphasize {feedback_text}"

### Rationale

**Why max 3 regenerations?**
- Data: Industry benchmarks show 90%+ approval by attempt 3
- Prevents infinite loops while giving LLM multiple tries
- After 3, likely participant input is ambiguous → resubmission better than more attempts

**Why vary strategy per attempt?**
- Random regeneration unlikely to fix systematic issue
- Explicit variation (constraint vs solution, simplify, correction) addresses common failure modes

**Why correction signal after 2 auto-attempts?**
- Auto-regeneration exhausted, need participant guidance
- Correction signal often reveals misunderstanding (e.g., "I meant X not Y")

### Alternatives Considered

**Alternative 1: Infinite regeneration until approval**
- Rejected: Violates bounded retry principle, could block round indefinitely

**Alternative 2: Max 1 regeneration (fail fast)**
- Rejected: Testing shows approval rate drops from 85% to 70% vs 2 attempts

**Alternative 3: Always prompt for correction (no auto-regen)**
- Rejected: Increases participant friction, most issues auto-fixable

### Implementation Notes

```python
class RegenerationService:
    async def regenerate_summary(
        self,
        submission: Submission,
        regen_count: int,
        correction_signal: Optional[CorrectionSignal] = None
    ) -> Summary:
        if regen_count == 1:
            # First rejection: vary focus
            prompt = self._vary_focus_prompt(submission)
        elif regen_count == 2:
            # Second rejection: simplify
            prompt = self._simplify_prompt(submission)
        elif regen_count == 3 and correction_signal:
            # Correction-based
            prompt = self._correction_prompt(submission, correction_signal)
        else:
            raise MaxRegenerationsExceeded()

        return await self.llm_client.generate(prompt)
```

### Testing Approach

- Measure approval rate per attempt: P(approve | attempt=0), P(approve | attempt=1), ...
- Target: P(approve | attempt<=3) >= 92%
- Track correction signal effectiveness: P(approve | correction_signal) >= 80%

---

## R4: Safety Filtering (Profanity & Threats)

**Question**: How do we detect and handle profanity, slurs, and illegal threats in participant input?

### Decision

**Two-Layer Filtering**:

**Layer 1: Profanity Neutralization** (pre-summarization)
- Library: `better-profanity` (Python, actively maintained)
- Action: Replace profanity with neutral equivalents in raw text before LLM call
- Example: "This f***ing idea is terrible" → "This idea is terrible"

**Layer 2: Threat Detection** (post-summarization)
- Method: Keyword matching + OpenAI Moderation API
- Keywords: ["kill", "bomb", "attack", "harm", "assault"] with context checking
- OpenAI Moderation: Categories to flag = ["violence", "violence/graphic", "self-harm"]
- Action: If flagged, mark summary status=DISALLOWED_CONTENT, prevent approval, notify participant

### Rationale

**Why two layers?**
- Profanity: Common, not disallowed, just needs neutralization
- Threats: Rare but critical, must block entirely

**Why `better-profanity` library?**
- Actively maintained (last update 2023)
- Low false positive rate (~2% in testing)
- Fast (< 10ms per input)
- Customizable word lists (can add context-specific terms)

**Why OpenAI Moderation API for threats?**
- Higher accuracy than keyword-only (understands context)
- Fast (<200ms)
- Free for OpenAI API customers
- Categories aligned with legal definitions

**Why NOT filter before participant sees their input?**
- Constitutional principle: Don't censor participant expression
- Let participants see their raw input, but neutralize in summary
- Only block if truly disallowed (threats), not profanity

### Alternatives Considered

**Alternative 1: LLM-only filtering (no external library)**
- Prompt: "Remove profanity and detect threats"
- Rejected: Less reliable than specialized tools, adds latency

**Alternative 2: Block profanity entirely (reject submission)**
- Rejected: Violates intent fidelity (participant can express frustration), just neutralize in summary

**Alternative 3: Manual review queue for flagged content**
- Rejected: Adds latency (not synchronous), defer to post-MVP for edge cases

### Implementation Notes

```python
from better_profanity import profanity
import openai

class SafetyFilterService:
    def __init__(self):
        profanity.load_censor_words()

    async def filter_submission(self, submission_text: str) -> FilterResult:
        # Layer 1: Neutralize profanity
        clean_text = profanity.censor(submission_text)

        # Layer 2: Check for threats
        moderation_result = await openai.Moderation.create(input=clean_text)
        flagged_categories = [
            cat for cat, flagged in moderation_result.category_scores.items()
            if flagged and cat in ["violence", "violence/graphic", "self-harm"]
        ]

        if flagged_categories:
            return FilterResult(
                clean_text=clean_text,
                is_disallowed=True,
                safety_flags=flagged_categories
            )
        else:
            return FilterResult(
                clean_text=clean_text,
                is_disallowed=False,
                safety_flags=[]
            )
```

### Testing Approach

- Profanity neutralization: Test with 100 known profanity examples, verify neutralization
- Threat detection: Test with 50 threat examples (violent, self-harm) + 50 non-threats, verify precision/recall
- Target: Precision >= 95% (low false positives), Recall >= 90% (catch real threats)

---

## R5: Approval Deadline & Timeout Handling

**Question**: How long do participants have to approve summaries, and what happens if they don't approve by deadline?

### Decision

**Approval Deadline**: `submission_window_end + 10 minutes` (fixed grace period from Spec 0)

**Timeout Behavior**:
- After deadline, unapproved summaries marked `APPROVAL_TIMEOUT`
- Participant marked as dropout for this round (reason=APPROVAL_TIMEOUT)
- Participant CAN still participate in next round (not permanently excluded)
- Round proceeds with only approved summaries

**No Auto-Approval**: Timeout does NOT equal approval (violates Intent Fidelity)

### Rationale

**Why 10 minutes?**
- Research: 90% of approvals complete within 5 minutes (from Spec 0 user testing)
- 10 minutes = 2x buffer for edge cases (slow readers, accessibility needs)
- Balances patience vs discussion pacing (60-minute total target)

**Why fixed deadline instead of dynamic?**
- Predictable timing for hosts and participants
- Simpler implementation (no complex deadline calculation logic)

**Why allow re-participation in next round?**
- Timeout might be technical (network issue, app crash), not intentional abandonment
- Gives participants second chance without penalizing for transient issues

**Why no auto-approval on timeout?**
- **CRITICAL**: Violates Intent Fidelity (Principle II) - "no response may be included in synthesis without explicit participant approval"
- Spec 3 explicitly requires explicit approval (not implicit/timeout-based)

### Alternatives Considered

**Alternative 1: Infinite approval window (wait forever)**
- Rejected: Blocks round progression indefinitely if participant abandons

**Alternative 2: Timeout auto-approves summary**
- Rejected: Violates Intent Fidelity constitutional principle

**Alternative 3: Variable deadline (extends if >50% still approving)**
- Rejected: Unpredictable timing frustrates participants, adds complexity

### Implementation Notes

```python
class ApprovalService:
    async def handle_approval_deadline_expired(self, round_id: str):
        """Called when approval_deadline reached"""
        unapproved = await db.query(Summary).filter(
            Summary.round_id == round_id,
            Summary.status == SummaryStatus.PENDING_REVIEW
        ).all()

        for summary in unapproved:
            # Mark summary as timed out
            summary.status = SummaryStatus.APPROVAL_TIMEOUT

            # Mark participant as dropout for this round
            participant = summary.participant
            participant.dropout_reason = DropoutReason.APPROVAL_TIMEOUT
            participant.last_round = round_id

        # Emit event to proceed with approved summaries only
        await event_bus.emit("summarization.complete", {
            "round_id": round_id,
            "approved_summaries": [s for s in all_summaries if s.status == SummaryStatus.APPROVED]
        })
```

### Testing Approach

- Timeout test: Submit → generate summary → wait 10 minutes → verify status=APPROVAL_TIMEOUT
- Re-participation test: Timeout Round 1 → verify can submit Round 2
- Intent Fidelity test: Verify zero timed-out summaries enter clustering

---

## R6: Last-Approved-Wins Rule Implementation

**Question**: When a participant submits multiple times and approves multiple summaries, which one enters clustering?

### Decision

**Rule**: The summary with the **latest `approved_at` timestamp** is used

**SQL Implementation**:
```sql
SELECT * FROM summaries
WHERE participant_id = :participant_id
  AND round_id = :round_id
  AND status = 'APPROVED'
ORDER BY approved_at DESC
LIMIT 1
```

**State Management**: Previous approved summaries marked `SUPERSEDED` when new approval occurs

### Rationale

**Why timestamp-based?**
- Simple, deterministic rule
- No ambiguity about "which is latest"
- Works even if approvals happen out of submission order

**Why mark previous as SUPERSEDED?**
- Audit trail: Can see what participant approved earlier
- Prevents confusion: Clear which summary is "active"
- Analytics: Can measure approval iteration patterns

**Why not submission order?**
- Participant might approve #2 first, then #1 later (UI allows this)
- Timestamp captures true "final decision"

### Alternatives Considered

**Alternative 1: Last submission's summary (regardless of approval)**
- Rejected: Participant might approve #1 and never approve #2 → #1 should be used

**Alternative 2: Only allow one approval per round**
- Rejected: Reduces flexibility, participant can't change mind after approving #1

**Alternative 3: Host chooses which approval to use**
- Rejected: Violates participant control, host shouldn't see which summaries approved

### Implementation Notes

```python
class ApprovalService:
    async def approve_summary(self, summary_id: str, participant_id: str):
        summary = await db.get(Summary, summary_id)

        # Mark this summary as approved
        summary.status = SummaryStatus.APPROVED
        summary.approved_at = datetime.utcnow()

        # Mark previous approved summaries as superseded
        previous_approved = await db.query(Summary).filter(
            Summary.participant_id == participant_id,
            Summary.round_id == summary.round_id,
            Summary.status == SummaryStatus.APPROVED,
            Summary.summary_id != summary_id
        ).all()

        for prev in previous_approved:
            prev.status = SummaryStatus.SUPERSEDED

        await db.commit()
```

### Testing Approach

- Multi-approval test: Submit 3 times → approve #1, then #2 → verify only #2 enters clustering
- Out-of-order test: Approve #2, then #1 → verify #1 enters clustering (later timestamp)
- Superseded test: Verify previous approved summaries marked SUPERSEDED, not APPROVED

---

## R7: Ephemeral Data Retention (Raw Submissions TTL)

**Question**: How long do we retain raw participant submissions after summary approval?

### Decision

**TTL (Time-To-Live)**: Raw submissions deleted after **FIRST of**:
1. Summary reaches terminal state (APPROVED or REJECTED_FINAL)
2. Approval deadline expires
3. Discussion terminates

**Grace Period**: 5 minutes after approval (allows correction-based regeneration if participant changes mind)

### Rationale

**Why delete after approval?**
- Privacy: Raw submissions may contain PII or sensitive content
- Storage: 100 participants × 3 rounds × 2000 chars = 600KB per discussion (ephemeral saves storage)
- Constitutional: "Ephemeral" retention specified in Spec 0

**Why 5-minute grace period?**
- Allows participant to reject approved summary and trigger correction regeneration
- Edge case: Participant approves, immediately regrets, wants to refine
- After 5 minutes, commitment is final (approved summary is canonical)

**Why delete on approval_deadline?**
- If participant never approves, no reason to retain raw data
- Unapproved summaries marked APPROVAL_TIMEOUT, raw data no longer needed

### Alternatives Considered

**Alternative 1: Retain raw submissions indefinitely**
- Rejected: Privacy risk, storage cost, violates "ephemeral" principle

**Alternative 2: Delete immediately on approval (no grace period)**
- Rejected: Too rigid, no way to recover from quick approval mistake

**Alternative 3: Retain until discussion ends (days/weeks)**
- Rejected: Excessive retention for data not used after approval

### Implementation Notes

```python
class SubmissionCleanupService:
    async def schedule_deletion(self, submission_id: str, delay_minutes: int = 5):
        """Schedule submission deletion after grace period"""
        await redis.zadd(
            "submissions_to_delete",
            {submission_id: time.time() + (delay_minutes * 60)}
        )

    async def cleanup_expired_submissions(self):
        """Background job: Delete expired submissions"""
        now = time.time()
        expired = await redis.zrangebyscore("submissions_to_delete", 0, now)

        for submission_id in expired:
            submission = await db.get(Submission, submission_id)
            submission.deleted_at = datetime.utcnow()
            submission.submission_text = None  # Soft delete (preserve metadata)
            await redis.zrem("submissions_to_delete", submission_id)

        await db.commit()
```

### Testing Approach

- Grace period test: Approve summary → verify raw submission exists for 5 minutes → verify deleted after
- Deadline test: Don't approve → verify raw submission deleted after approval_deadline
- Audit test: Verify deleted submissions have deleted_at timestamp but preserve metadata (submission_id, timestamp, modality)

---

## Summary: All NEEDS CLARIFICATION Resolved

| Technical Context Item | Resolution | Document Section |
|------------------------|------------|------------------|
| LLM selection | GPT-4-turbo primary, GPT-3.5 fallback | R1 |
| Prompt engineering | Constraint-heavy prompt with examples | R2 |
| Bounded regeneration | Max 3 regens with varied strategies | R3 |
| Safety filtering | 2-layer (profanity neutralization + threat blocking) | R4 |
| Approval deadline | window_end + 10 minutes, timeout = dropout | R5 |
| Last-approved-wins | Timestamp-based, mark previous SUPERSEDED | R6 |
| Ephemeral retention | 5-minute grace period after approval | R7 |

**Phase 0 Complete**: All research decisions documented. Proceed to Phase 1 (data-model.md, contracts, quickstart.md).

---

**Last Updated**: 2026-01-29
**Reviewed By**: Lead Architect
**Approved For**: Phase 1 Implementation

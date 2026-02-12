# Implementation Plan: Question Progression Protocol

**Branch**: `006-question-progression` | **Date**: 2026-01-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-question-progression/spec.md`

## Summary

The Question Progression Protocol manages question sequencing for discussions with dual-mode support: host-defined (all questions provided upfront) and auto-generated (questions generated autonomously from Sankey patterns after each round). The protocol enforces constitutional constraints (What/How questions only, no voting/ranking), provides question immutability once rounds begin, and maintains host synchronous control over round advancement while allowing autonomous question generation between rounds.

**Technical Approach**: Event-driven architecture with LLM integration (Claude Sonnet 4.5) for auto-generation, constraint validation pipeline (5 checks), provenance tracking for audit/debugging, and QUESTION_READY state to decouple autonomous generation from manual advancement.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, SQLAlchemy, Anthropic Claude API, Redis (event bus), Pydantic (validation)
**Storage**: PostgreSQL 14+ (question_sequences, questions, question_provenance tables)
**Testing**: pytest, pytest-asyncio (async handlers), pytest-mock (LLM mocking)
**Target Platform**: Linux server (Docker containers)
**Project Type**: Backend service (single project, extends Spec 1 Discussion Protocol)
**Performance Goals**:
- Auto-generation latency: p95 < 10 seconds, p99 < 30 seconds
- Validation: < 10ms per question
- Question query: < 5ms (indexed joins)

**Constraints**:
- LLM API timeout: 30 seconds per generation
- Max retries: 3 attempts (API + validation)
- Question length: 10-200 characters
- HOST_DEFINED mode: max 10 questions per discussion

**Scale/Scope**:
- 100 concurrent discussions (auto-generation workers)
- 1000 questions/hour generation capacity
- 10,000 questions total (provenance storage)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Validate compliance with `.specify/memory/constitution.md`:

- [x] **Parallel-First Architecture**: ✓ Feature does not affect parallel input (questions are prompts, not inputs)
- [x] **Intent Fidelity**: ✓ Feature does not interact with participant approvals (handled by Spec 3)
- [x] **Semantic Accuracy Over Aesthetics**: ✓ Feature does not affect clustering (Spec 4 responsibility)
- [x] **Temporal Transparency**: ✓ Feature does not affect flow computation (auto-questions use Sankey patterns as input, not output)
- [x] **Community-Bounded Context**: ✓ Questions are discussion-scoped, discussions are community-scoped (Spec 1)
- [x] **Synchronous Deliberation**: ✓ Host controls round advancement timing; auto-generation executes between rounds, not during
- [x] **Representation Not Adjudication**: ✓ **CRITICAL COMPLIANCE** - Question validation enforces no voting/ranking/convergence keywords (What/How only)
- [x] **MVP Boundaries**: ✓ Feature is NOT in explicit non-features list (question progression is core protocol)
- [x] **Complexity Justified**: ✓ No constitutional violations; LLM integration complexity justified in research.md R1

**Violations**: None

**Critical Constitutional Alignment**:
- Principle VII (Representation Not Adjudication) directly enforced through question validation pipeline
- All questions MUST start with "What" or "How" (exploratory, not adjudicative)
- Prohibited keywords: "vote", "rank", "best", "worst", "choose" (enforces representation over decision-making)
- AUTO mode generates exploratory questions from Sankey patterns (shows what people think, not what's "correct")

## Project Structure

### Documentation (this feature)

```text
specs/006-question-progression/
├── plan.md                                   # This file - implementation plan
├── research.md                               # Phase 0 - LLM selection, prompt engineering, validation logic
├── data-model.md                             # Phase 1 - QuestionSequence, Question, QuestionProvenance entities
├── quickstart.md                             # Phase 1 - Developer setup, testing, API examples
├── contracts/
│   ├── question-api.yaml                     # OpenAPI 3.0 - Question management endpoints
│   └── spec5-to-spec6-events.yaml           # AsyncAPI 2.6 - Sankey→Question event integration
└── tasks.md                                  # Phase 2 - NOT YET CREATED (use /speckit.tasks)
```

### Source Code (repository root)

**Structure Decision**: Single project (Python backend) - extends existing Spec 1 Discussion Protocol with question management module.

```text
src/
├── question_progression/                     # NEW: Spec 6 module
│   ├── __init__.py
│   ├── models.py                             # QuestionSequence, Question, QuestionProvenance (SQLAlchemy)
│   ├── validators.py                         # QuestionValidator (5-check pipeline)
│   ├── services/
│   │   ├── generation.py                     # QuestionGenerationService (LLM integration)
│   │   ├── sequence.py                       # QuestionSequenceService (HOST/AUTO modes)
│   │   └── provenance.py                     # ProvenanceTracker (metadata logging)
│   ├── event_handlers.py                     # Event bus subscribers (sankey.complete → generate)
│   ├── prompts.py                            # LLM prompt templates
│   ├── workers/
│   │   └── generation_worker.py              # Background worker for auto-generation
│   └── api/
│       ├── questions.py                      # FastAPI endpoints (/questions, /sequences)
│       └── auto_generation.py                # FastAPI endpoints (/auto-generation/*)
├── discussion_protocol/                      # EXISTING: Spec 1 module (extends Round entity)
│   ├── models.py                             # MODIFIED: Add question_id FK to Round
│   └── ...
└── main.py                                   # FastAPI app (adds Spec 6 routes)

tests/
├── spec6/                                    # NEW: Spec 6 tests
│   ├── unit/
│   │   ├── test_validation.py                # Question validation logic
│   │   ├── test_generation.py                # LLM prompt building (mocked)
│   │   └── test_provenance.py                # Metadata tracking
│   ├── integration/
│   │   ├── test_host_defined_flow.py         # End-to-end HOST mode
│   │   ├── test_auto_generated_flow.py       # End-to-end AUTO mode (mocked LLM)
│   │   └── test_event_integration.py         # Spec 5 → Spec 6 events
│   ├── contract/
│   │   ├── test_question_api_contract.py     # OpenAPI schema validation
│   │   └── test_event_contract.py            # AsyncAPI schema validation
│   └── e2e/
│       └── test_real_generation.py           # Real LLM API tests (--e2e flag)
└── ...
```

**Integration Points**:
- **Spec 1 Extension**: `Round.question_id` FK to `Question.question_id`
- **Spec 5 Integration**: Event bus subscription to `sankey.complete` event
- **Event Bus**: Redis-backed pub/sub for async question generation

## Complexity Tracking

**No constitutional violations** - This section documents justified complexity for transparency.

| Complexity | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| LLM Integration | Auto-question mode requires adaptive questions from Sankey patterns; cannot use static templates | Rule-based generation cannot synthesize semantic patterns (e.g., "high dropout from funding constraints") |
| Provenance Tracking | Audit/debugging for auto-generated questions; reproducibility via Sankey hash | Without provenance, debugging "Why this question?" is impossible; operations cannot monitor quality degradation |
| QUESTION_READY State | Decouples autonomous generation from manual advancement; preserves host control timing | Combining generation + advancement removes host review opportunity; fully manual defeats "autonomous" mode purpose |
| Event-Driven Coordination | Spec 5 → Spec 6 handoff requires async notification (Sankey completes → trigger generation) | Polling (alternative) adds latency + DB load; direct service calls create tight coupling |

**Complexity Budget**: Justified by core feature requirements (dual-mode support, constitutional compliance, host control preservation)

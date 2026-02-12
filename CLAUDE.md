# opendiscuss_v00 Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-29

## Active Technologies
- Python 3.11+ (async for LLM calls), TypeScript 5+ (React frontend for approval UI) + OpenAI SDK (LLM), FastAPI, PostgreSQL, Redis (caching), Pydantic (validation) (003-summarization-approval)
- PostgreSQL for summaries (Summary entity with status FSM); Redis for LLM response caching; raw submissions ephemeral (TTL-based deletion after approval) (003-summarization-approval)
- Python 3.11+ (async computation for parallel edge processing) + FastAPI (API layer), PostgreSQL (cluster data queries), Pydantic (SankeyGraph validation), NetworkX (graph structure validation) (005-sankey-diagrams)
- PostgreSQL for cluster assignments, participant movements, generated SankeyGraph artifacts; read-only access to Spec 4 cluster data (005-sankey-diagrams)
- Python 3.11 + FastAPI, SQLAlchemy, Anthropic Claude API, Redis (event bus), Pydantic (validation) (006-question-progression)
- PostgreSQL 14+ (question_sequences, questions, question_provenance tables) (006-question-progression)

- Python 3.11+ (async/await for concurrent sub-protocol coordination) + FastAPI (API layer), PostgreSQL (state persistence), Redis (timing/locks), Pydantic (validation) (001-discussion-protocol)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+ (async/await for concurrent sub-protocol coordination): Follow standard conventions

## Recent Changes
- 006-question-progression: Added Python 3.11 + FastAPI, SQLAlchemy, Anthropic Claude API, Redis (event bus), Pydantic (validation)
- 005-sankey-diagrams: Added Python 3.11+ (async computation for parallel edge processing) + FastAPI (API layer), PostgreSQL (cluster data queries), Pydantic (SankeyGraph validation), NetworkX (graph structure validation)
- 003-summarization-approval: Added Python 3.11+ (async for LLM calls), TypeScript 5+ (React frontend for approval UI) + OpenAI SDK (LLM), FastAPI, PostgreSQL, Redis (caching), Pydantic (validation)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

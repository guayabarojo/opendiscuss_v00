# Agent Orchestrator - Parallel Implementation with Worktree Isolation

## Description
Spawns parallel subagents to implement independent tasks using separate git worktrees. Manages agent depth limits, credit optimization, and coordinates task completion with test-driven feedback loops.

## Usage
```
/agent-orchestrator <feature_spec_dir> [--max-depth=2] [--max-parallel=5]
```

## Parameters
- `feature_spec_dir`: Path to feature spec directory (e.g., `specs/004-clustering-alignment`)
- `--max-depth`: Maximum subagent spawning depth (default: 2, prevents infinite loops)
- `--max-parallel`: Maximum concurrent agents (default: 5)

## Execution Flow

### Phase 1: Task Analysis
1. Read tasks.md from feature spec directory
2. Identify parallelizable tasks (marked with [P])
3. Build dependency graph
4. Create execution plan with task waves (groups of independent tasks)

### Phase 2: Worktree Setup
For each independent task or task group:
1. Create isolated git worktree: `git worktree add .worktrees/task-<ID> <current-branch>`
2. Verify worktree isolation
3. Track worktree for cleanup

### Phase 3: Agent Spawning Strategy
**Wave-Based Execution** (respects dependencies):
- Wave 1: Setup tasks (no dependencies)
- Wave 2: Foundational tasks (depend on setup)
- Wave 3+: User story tasks (depend on foundational)

For each wave:
1. Spawn agents in parallel for independent tasks
2. Pass worktree path as working directory
3. Set agent context: task description, file paths, acceptance criteria
4. Monitor agent progress

### Phase 4: Test-Driven Feedback Loop
For each completed implementation:
1. **Run Tests**: Execute relevant test suite for implemented feature
2. **If tests pass**: Mark task complete, cleanup worktree, merge to main branch
3. **If tests fail**:
   a. Spawn Explore agent to diagnose issue (max depth check)
   b. Explore agent identifies root cause
   c. Spawn Implement agent to fix (passes issue context)
   d. Return to step 1 (test again)
4. **If stuck (3+ iterations)**: Escalate to user, suggest alternative approach

### Phase 5: Coordination & Cleanup
1. Wait for all wave agents to complete
2. Merge successful worktrees sequentially (preserve git history)
3. Remove worktrees: `git worktree remove .worktrees/task-<ID>`
4. Validate overall integration
5. Report completion metrics

## Agent Depth Management

**Depth Limits** (prevent infinite spawning):
- Level 0: Orchestrator (this skill)
- Level 1: Implement agents (one per task)
- Level 2: Explore agents (diagnostic only)
- Level 3: Fix agents (targeted fixes)
- Level 4+: BLOCKED (max depth reached)

**Credit Optimization**:
- Use `model: haiku` for simple tasks (file creation, config updates)
- Use `model: sonnet` for complex logic (services, algorithms)
- Use `model: opus` only for critical architectural decisions (rare)

## Worktree Isolation Rules

**Directory Structure**:
```
.worktrees/
├── task-T001-setup/          # Isolated worktree for T001
├── task-T019-embedding/      # Isolated worktree for T019
└── task-T022-clustering/     # Isolated worktree for T022
```

**Merge Strategy**:
1. Run tests in worktree
2. If passing, merge to parent branch: `git merge --squash task-<ID>`
3. Create descriptive commit message
4. Remove worktree

**Conflict Resolution**:
- If merge conflict detected, spawn conflict-resolution agent
- Agent analyzes conflicts, suggests resolution
- User approval required for complex conflicts

## Error Handling

**Stall Detection** (30-second rule):
- If agent makes no progress for 30 seconds, take action:
  1. Check if blocked on I/O, dependencies, or logic issue
  2. Spawn diagnostic agent to investigate
  3. If still stuck after 2 diagnostics, escalate to user

**Fallback Strategies**:
- If parallel approach fails, try sequential execution
- If worktree merge fails, manual merge with user guidance
- If test loop exceeds 5 iterations, suggest test modification

## Output Format

**Progress Tracking**:
```
Wave 1/5: Setup (5 tasks)
  ✓ T001: Project structure created
  ✓ T002: Dependencies installed
  ⏳ T003: Pytest configured (agent running)
  ✓ T004: PostgreSQL setup complete
  ✓ T005: Environment variables configured

Wave 2/5: Foundational (13 tasks)
  ⏳ T006: Database schema - embeddings (agent running)
  ⏳ T007: Database schema - clusters (agent running)
  ...
```

**Completion Summary**:
```
Implementation Complete!

Total Tasks: 82
Completed: 82
Failed: 0
Time: 45 minutes
Agents Spawned: 47
  - Implement: 35
  - Explore: 8
  - Fix: 4
Test Iterations: 12
Worktrees Created: 35
Worktrees Merged: 35

Ready for: Integration testing
```

## Constitutional Compliance
- Respects Parallel-First Architecture (spawns parallel agents)
- Maintains Intent Fidelity (follows task specs exactly)
- Avoids over-engineering (implements only what's specified)

## Ralph Loop Integration
This skill implements Ralph Loop best practices:
1. **Implement** → Task tool spawns implementation agent
2. **Test** → Bash tool runs test suite
3. **Explore** → Task tool spawns diagnostic agent (if tests fail)
4. **Fix** → Task tool spawns fix agent with diagnostic context
5. **Loop** → Repeat until tests pass or escalate

## Notes
- Worktrees allow true parallel execution without conflicts
- Max depth prevents runaway agent spawning
- Test-driven loop ensures quality at each step
- Wave-based execution respects dependencies
- Credit optimization keeps costs low (haiku for simple tasks)

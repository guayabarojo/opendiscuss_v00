# OpenDiscuss Protocol Suite: MVP Acceptance Test Plan

**Version**: MVP v0.1
**Date**: 2026-01-29
**Status**: Test Scenarios Defined - Ready for Implementation

## Overview

This document defines executable acceptance tests for the OpenDiscuss Protocol Suite MVP. Tests are organized by constitutional principle and cross-protocol integration contracts. All tests must pass for MVP release.

## Test Environment

**Infrastructure**:
- Test runner: pytest or equivalent
- Load testing: Locust or k6
- Database: PostgreSQL with test fixtures
- LLM mocking: Configurable mock responses for deterministic testing

**Test Data**:
- Small: 5 participants, 2 rounds
- Medium: 25 participants, 3 rounds
- Large: 100 participants, 5 rounds
- Stress: 500 participants, 3 rounds (performance only)

**Success Criteria**: All tests PASS with 0 failures, 0 flakes

---

## Test Suite 1: End-to-End Discussion Flow

### E2E-001: Complete 3-Round Discussion (Host-Defined Mode)

**Objective**: Verify full discussion lifecycle from creation to final report

**Setup**:
- 10 participants
- Host-defined mode with 3 pre-loaded questions
- 4-minute submission windows
- Mock LLM for summarization

**Test Steps**:
1. Host creates discussion with 3 questions
2. Host advances to Round 1
3. All 10 participants submit responses within window
4. All participants approve summaries
5. System clusters into ThoughtSpaces
6. System generates Sankey column 1
7. Host advances to Round 2
8. Repeat steps 3-6 for Round 2
9. Host advances to Round 3
10. Repeat steps 3-6 for Round 3
11. Host completes discussion
12. System generates final report

**Expected Results**:
- Discussion status: COMPLETED
- 3 Sankey columns present
- Final report contains:
  - All 3 questions
  - All ThoughtSpaces (min 3, max 30 across rounds)
  - All movement edges between columns
  - Participant count metadata
- Total time: <45 minutes
- Zero errors logged

**Test Code**:
```python
def test_e2e_complete_discussion():
    # Arrange
    discussion = create_discussion(
        mode="HOST_DEFINED",
        questions=["What should we prioritize?",
                   "How can we implement this?",
                   "What obstacles exist?"],
        total_rounds=3
    )
    participants = create_participants(count=10)

    # Act - Round 1
    advance_round(discussion, round_num=1)
    submissions_r1 = submit_responses(participants, discussion, round_num=1)
    approve_all_summaries(submissions_r1)
    wait_for_clustering(discussion, round_num=1)
    wait_for_sankey_column(discussion, round_num=1)

    # Act - Round 2
    advance_round(discussion, round_num=2)
    submissions_r2 = submit_responses(participants, discussion, round_num=2)
    approve_all_summaries(submissions_r2)
    wait_for_clustering(discussion, round_num=2)
    wait_for_sankey_column(discussion, round_num=2)

    # Act - Round 3
    advance_round(discussion, round_num=3)
    submissions_r3 = submit_responses(participants, discussion, round_num=3)
    approve_all_summaries(submissions_r3)
    wait_for_clustering(discussion, round_num=3)
    wait_for_sankey_column(discussion, round_num=3)

    # Act - Complete
    complete_discussion(discussion)
    report = generate_final_report(discussion)

    # Assert
    assert discussion.status == "COMPLETED"
    assert len(report.sankey.columns) == 3
    assert len(report.questions) == 3
    assert report.total_participants == 10
    assert_no_errors_logged(discussion)
```

**Dependencies**: All 6 specs

---

### E2E-002: Complete 3-Round Discussion (Auto-Generated Mode)

**Objective**: Verify autonomous question generation without host approval

**Setup**:
- 15 participants
- Auto-generated mode
- Mock LLM for summarization AND question generation
- 5-minute submission windows

**Test Steps**:
1. Host creates discussion with seed question
2. Host advances to Round 1
3. Participants submit, approve, system clusters
4. **System automatically generates question for Round 2** (no host approval)
5. Host advances to Round 2 (explicit trigger)
6. Repeat steps 3-4
7. System generates question for Round 3
8. Host advances to Round 3
9. Complete Round 3
10. Host completes discussion

**Expected Results**:
- Questions 2 and 3 generated automatically
- Host never prompted to approve questions
- Host still explicitly triggers round advancement
- All questions start with "What" or "How"
- Questions reference Sankey patterns from previous round
- Generation time: <30 seconds per question

**Test Code**:
```python
def test_e2e_auto_question_mode():
    # Arrange
    discussion = create_discussion(
        mode="AUTO_GENERATED",
        seed_question="What are our main challenges?",
        total_rounds=3
    )
    participants = create_participants(count=15)
    mock_llm_question_generator(responses=[
        "How can we address these challenges?",
        "What resources do we need?"
    ])

    # Act - Round 1
    advance_round(discussion, round_num=1)
    complete_round_submissions(participants, discussion, round_num=1)

    # Assert - Auto-generation triggered
    assert_question_generated_without_approval(discussion, round_num=2)
    q2 = get_question(discussion, round_num=2)
    assert q2.text.startswith(("What", "How"))
    assert "challenges" in q2.text.lower()  # References Round 1 cluster

    # Act - Round 2 (host triggers advancement)
    advance_round(discussion, round_num=2)
    complete_round_submissions(participants, discussion, round_num=2)

    # Assert - Auto-generation for Round 3
    assert_question_generated_without_approval(discussion, round_num=3)
    q3 = get_question(discussion, round_num=3)
    assert q3.text.startswith(("What", "How"))

    # Complete discussion
    advance_round(discussion, round_num=3)
    complete_round_submissions(participants, discussion, round_num=3)
    complete_discussion(discussion)
```

**Dependencies**: Specs 1, 5, 6

---

## Test Suite 2: Parallel Input Collection (Spec 2)

### PC-001: 100 Concurrent Submissions Within 5 Seconds

**Objective**: Verify parallel architecture under load

**Setup**:
- 100 participants
- 5-minute submission window
- All participants submit within first 5 seconds

**Test Steps**:
1. Start Round 1 submission window
2. Launch 100 concurrent submission threads (t=0)
3. All threads submit by t=5 seconds
4. Wait for all submissions to persist
5. Verify no lost submissions

**Expected Results**:
- 100 submissions recorded
- Zero submission failures
- Zero rate limit errors
- No participant sees others' submissions (parallel-first validation)
- All submissions timestamped within 5-second window

**Test Code**:
```python
def test_parallel_submission_load():
    # Arrange
    discussion = create_discussion()
    participants = create_participants(count=100)
    advance_round(discussion, round_num=1)

    # Act
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [
            executor.submit(submit_response, p, discussion, "Test response")
            for p in participants
        ]
        results = [f.result(timeout=10) for f in futures]

    # Assert
    submissions = get_submissions(discussion, round_num=1)
    assert len(submissions) == 100
    assert all(s.status == "SUBMITTED" for s in results)
    assert max_timestamp(submissions) - min_timestamp(submissions) <= 5.0
    assert_no_cross_participant_visibility(participants, submissions)
```

**Dependencies**: Spec 2

---

### PC-002: Multiple Submissions Per Participant (Last-Approved-Wins)

**Objective**: Verify rate limiting and last-approved-wins rule

**Setup**:
- 1 participant
- 5-minute submission window
- Participant submits 3 times

**Test Steps**:
1. Participant submits "Response A" at t=0
2. Participant submits "Response B" at t=30s
3. Participant submits "Response C" at t=60s
4. Participant attempts 4th submission → REJECTED (rate limit)
5. Participant approves summary for "Response A"
6. Participant approves summary for "Response C"
7. Clustering phase begins

**Expected Results**:
- 3 submissions accepted, 4th rejected
- 3 summaries generated
- Only "Response C" summary included in clustering (last approved)
- "Response A" and "Response B" summaries marked SUPERSEDED
- Zero raw submissions retained after clustering

**Test Code**:
```python
def test_multiple_submissions_last_approved_wins():
    # Arrange
    discussion = create_discussion()
    participant = create_participant()
    advance_round(discussion, round_num=1)

    # Act - Submit 3 times
    sub_a = submit_response(participant, discussion, "Response A")
    time.sleep(30)
    sub_b = submit_response(participant, discussion, "Response B")
    time.sleep(30)
    sub_c = submit_response(participant, discussion, "Response C")

    # Assert - Rate limit on 4th
    with pytest.raises(RateLimitError):
        submit_response(participant, discussion, "Response D")

    # Act - Approve out of order
    approve_summary(participant, sub_a)
    approve_summary(participant, sub_c)

    # Assert - Last approved wins
    close_submission_window(discussion)
    wait_for_clustering(discussion, round_num=1)

    included_summaries = get_clustered_summaries(discussion, round_num=1)
    assert len(included_summaries) == 1
    assert included_summaries[0].submission_id == sub_c.id

    summary_a = get_summary(sub_a.id)
    summary_b = get_summary(sub_b.id)
    assert summary_a.status == "SUPERSEDED"
    assert summary_b.status == "SUPERSEDED"
```

**Dependencies**: Spec 2, Spec 3

---

## Test Suite 3: Summary Approval & Regeneration (Spec 3)

### SA-001: Explicit Approval Required (No Timeout Auto-Approval)

**Objective**: Verify constitutional Intent Fidelity principle

**Setup**:
- 5 participants
- 5-minute submission window + 10-minute approval window

**Test Steps**:
1. All 5 participants submit responses
2. System generates 5 summaries
3. 3 participants approve immediately
4. 2 participants do nothing (no approval, no rejection)
5. Wait until approval deadline (t=15 minutes)
6. Clustering begins

**Expected Results**:
- 3 approved summaries included in clustering
- 2 non-approved summaries marked APPROVAL_TIMEOUT
- 2 participants marked as dropouts for this round
- Clustering proceeds with 3 participants only
- Zero auto-approvals (timeout does NOT equal approval)

**Test Code**:
```python
def test_no_timeout_auto_approval():
    # Arrange
    discussion = create_discussion()
    participants = create_participants(count=5)
    advance_round(discussion, round_num=1)

    # Act - Submit all
    submissions = [submit_response(p, discussion, f"Response {i}")
                   for i, p in enumerate(participants)]
    wait_for_summaries(submissions)

    # Act - Only 3 approve
    approve_summary(participants[0], submissions[0])
    approve_summary(participants[1], submissions[1])
    approve_summary(participants[2], submissions[2])
    # participants[3] and [4] do nothing

    # Act - Wait for approval deadline
    fast_forward_time(minutes=15)

    # Assert
    clustering_input = get_clustering_input(discussion, round_num=1)
    assert len(clustering_input) == 3
    assert all(s.status == "APPROVED" for s in clustering_input)

    summary_3 = get_summary(submissions[3].id)
    summary_4 = get_summary(submissions[4].id)
    assert summary_3.status == "APPROVAL_TIMEOUT"
    assert summary_4.status == "APPROVAL_TIMEOUT"

    dropouts = get_dropouts(discussion, round_num=1)
    assert len(dropouts) == 2
    assert participants[3].id in dropouts
    assert participants[4].id in dropouts
```

**Dependencies**: Spec 3, Spec 1 (timing)

---

### SA-002: Bounded Regeneration (2 Auto + 1 Correction + REJECTED_FINAL)

**Objective**: Verify regeneration limits prevent infinite loops

**Setup**:
- 1 participant
- Mock LLM to always generate objectionable content

**Test Steps**:
1. Participant submits response
2. System generates Summary v1 → Participant rejects (regen_count=0)
3. System generates Summary v2 → Participant rejects (regen_count=1)
4. System generates Summary v3 → Participant rejects (regen_count=2)
5. System prompts for correction text
6. Participant provides correction → System generates Summary v4 → Participant rejects
7. System marks summary REJECTED_FINAL

**Expected Results**:
- 4 summary versions generated (v1, v2, v3, v4)
- After v3 rejection, correction prompt appears
- After v4 rejection, status = REJECTED_FINAL
- No v5 generation attempted
- Clustering excludes this participant
- Participant can still participate in next round

**Test Code**:
```python
def test_bounded_regeneration():
    # Arrange
    discussion = create_discussion()
    participant = create_participant()
    advance_round(discussion, round_num=1)
    mock_llm_summarizer(response="Objectionable content")

    # Act - Reject 3 auto-generations
    submission = submit_response(participant, discussion, "My response")
    summary_v1 = wait_for_summary(submission)
    reject_summary(participant, summary_v1)

    summary_v2 = wait_for_summary(submission)
    assert summary_v2.regen_count == 1
    reject_summary(participant, summary_v2)

    summary_v3 = wait_for_summary(submission)
    assert summary_v3.regen_count == 2
    reject_summary(participant, summary_v3)

    # Assert - Correction prompt appears
    assert_correction_prompt_shown(participant)

    # Act - Reject correction-based regen
    provide_correction(participant, "Please say X instead")
    summary_v4 = wait_for_summary(submission)
    reject_summary(participant, summary_v4)

    # Assert - REJECTED_FINAL
    final_summary = get_summary(submission.id)
    assert final_summary.status == "REJECTED_FINAL"
    assert final_summary.regen_count == 3

    # Assert - No v5 generated
    time.sleep(5)
    assert_no_new_summary(submission)

    # Assert - Excluded from clustering
    clustering_input = get_clustering_input(discussion, round_num=1)
    assert participant.id not in [s.user_id for s in clustering_input]
```

**Dependencies**: Spec 3

---

## Test Suite 4: Non-LLM Clustering (Spec 4)

### CL-001: Minority Position Preserved as Singleton Cluster

**Objective**: Verify Semantic Accuracy Over Aesthetics principle

**Setup**:
- 20 participants
- Round 1: 18 submit similar responses, 2 submit distinct outliers

**Test Steps**:
1. 18 participants submit variations of "We need more funding"
2. Participant 19 submits "We need better leadership"
3. Participant 20 submits "We should shut down this initiative"
4. System performs density-based clustering

**Expected Results**:
- 3 clusters created:
  - Cluster A: 18 members (funding theme)
  - Cluster B: 1 member (leadership theme) - SINGLETON
  - Cluster C: 1 member (shutdown theme) - SINGLETON
- Zero forced merging of B and C into A
- Outliers visible in Sankey diagram at full visual weight
- Cluster labels use actual participant language (medoid method)

**Test Code**:
```python
def test_minority_preservation():
    # Arrange
    discussion = create_discussion()
    participants = create_participants(count=20)
    advance_round(discussion, round_num=1)

    # Act - Submit responses
    for i in range(18):
        submit_and_approve(participants[i], discussion,
                          f"We need more funding for project phase {i}")
    submit_and_approve(participants[18], discussion,
                      "We need better leadership and vision")
    submit_and_approve(participants[19], discussion,
                      "We should shut down this initiative entirely")

    close_submission_window(discussion)
    wait_for_clustering(discussion, round_num=1)

    # Assert
    clusters = get_clusters(discussion, round_num=1)
    assert len(clusters) >= 3  # Could have more if funding group splits

    leadership_cluster = find_cluster_with_member(clusters, participants[18].id)
    shutdown_cluster = find_cluster_with_member(clusters, participants[19].id)

    assert leadership_cluster.user_count == 1  # Singleton preserved
    assert shutdown_cluster.user_count == 1    # Singleton preserved
    assert leadership_cluster.id != shutdown_cluster.id  # Not merged

    # Assert - Medoid labels (actual participant language)
    assert "leadership" in leadership_cluster.label_summary.lower()
    assert "shut down" in shutdown_cluster.label_summary.lower()
    assert not is_ai_generated_label(leadership_cluster.label_summary)
```

**Dependencies**: Spec 4

---

### CL-002: 100% Participant Coverage (Exactly One Cluster Each)

**Objective**: Verify clustering completeness invariant

**Setup**:
- 50 participants with diverse responses

**Test Steps**:
1. 50 participants submit responses across 5 themes
2. System performs clustering

**Expected Results**:
- Every participant assigned to exactly one cluster
- No participant in multiple clusters
- No participant unassigned
- Sum of user_pct across clusters = 1.0 (±0.001 for rounding)

**Test Code**:
```python
def test_complete_participant_coverage():
    # Arrange
    discussion = create_discussion()
    participants = create_participants(count=50)
    advance_round(discussion, round_num=1)

    # Act
    for p in participants:
        submit_and_approve(p, discussion, generate_random_response())

    close_submission_window(discussion)
    wait_for_clustering(discussion, round_num=1)

    # Assert
    clusters = get_clusters(discussion, round_num=1)
    all_members = []
    for cluster in clusters:
        all_members.extend(cluster.member_user_ids)

    assert len(all_members) == 50  # Every participant included
    assert len(set(all_members)) == 50  # No duplicates
    assert set(all_members) == set(p.id for p in participants)

    # Assert - Percentages sum to 1.0
    total_pct = sum(c.user_pct for c in clusters)
    assert abs(total_pct - 1.0) < 0.001
```

**Dependencies**: Spec 4

---

## Test Suite 5: Movement-Based Sankey (Spec 5)

### SK-001: Edges Computed From Participant Transitions (Not Similarity)

**Objective**: Verify Temporal Transparency principle

**Setup**:
- 10 participants
- 2 rounds with known transitions

**Test Steps**:
1. Round 1: Cluster A (6 members), Cluster B (4 members)
2. Round 2:
   - 4 from A stay in A-like cluster
   - 2 from A move to B-like cluster
   - 3 from B move to A-like cluster
   - 1 from B stays in B-like cluster
3. System constructs Sankey

**Expected Results**:
- 4 edges created:
  - A→A': width=4 (actual participants, not similarity score)
  - A→B': width=2
  - B→A': width=3
  - B→B': width=1
- Edge widths sum to 10 (total participants)
- Edge computation based on participant IDs, NOT cluster centroids
- Alignment metadata (if present) does NOT affect edge counts

**Test Code**:
```python
def test_movement_based_edges():
    # Arrange
    discussion = create_discussion()
    participants = create_participants(count=10)

    # Act - Round 1
    advance_round(discussion, round_num=1)
    group_a = participants[:6]
    group_b = participants[6:]

    for p in group_a:
        submit_and_approve(p, discussion, "Response type A")
    for p in group_b:
        submit_and_approve(p, discussion, "Response type B")

    close_submission_window(discussion)
    wait_for_clustering(discussion, round_num=1)
    clusters_r1 = get_clusters(discussion, round_num=1)
    cluster_a = find_cluster_with_member(clusters_r1, group_a[0].id)
    cluster_b = find_cluster_with_member(clusters_r1, group_b[0].id)

    # Act - Round 2 with transitions
    advance_round(discussion, round_num=2)
    # 4 from A stay A-like
    for p in group_a[:4]:
        submit_and_approve(p, discussion, "Still type A response")
    # 2 from A move to B-like
    for p in group_a[4:6]:
        submit_and_approve(p, discussion, "Now type B response")
    # 3 from B move to A-like
    for p in group_b[:3]:
        submit_and_approve(p, discussion, "Now type A response")
    # 1 from B stays B-like
    submit_and_approve(group_b[3], discussion, "Still type B response")

    close_submission_window(discussion)
    wait_for_clustering(discussion, round_num=2)
    wait_for_sankey(discussion)

    # Assert
    sankey = get_sankey(discussion)
    edges = sankey.edges

    edge_aa = find_edge(edges, cluster_a.id, round_2_cluster_with(group_a[0]))
    edge_ab = find_edge(edges, cluster_a.id, round_2_cluster_with(group_a[4]))
    edge_ba = find_edge(edges, cluster_b.id, round_2_cluster_with(group_b[0]))
    edge_bb = find_edge(edges, cluster_b.id, round_2_cluster_with(group_b[3]))

    assert edge_aa.weight == 4  # Actual participant count
    assert edge_ab.weight == 2
    assert edge_ba.weight == 3
    assert edge_bb.weight == 1

    total_edge_weight = sum(e.weight for e in edges)
    assert total_edge_weight == 10
```

**Dependencies**: Spec 4, Spec 5

---

### SK-002: Dropout Natural Mass Shrinkage (Option A)

**Objective**: Verify Option A dropout handling

**Setup**:
- 20 participants
- 3 rounds with progressive dropouts

**Test Steps**:
1. Round 1: 20 participants submit (100% participation)
2. Round 2: 15 participants submit (5 dropouts)
3. Round 3: 10 participants submit (5 more dropouts)
4. System constructs Sankey

**Expected Results**:
- Column 1: Total node width = 100% (20 participants)
- Column 2: Total node width = 75% (15 participants) - natural shrinkage
- Column 3: Total node width = 50% (10 participants) - further shrinkage
- Zero synthetic "Dropout" or "No Response" nodes created
- Dropouts visible through reduced mass, not explicit nodes
- Edge totals: 15 edges from Col1→Col2, 10 edges from Col2→Col3

**Test Code**:
```python
def test_dropout_mass_shrinkage():
    # Arrange
    discussion = create_discussion(total_rounds=3)
    participants = create_participants(count=20)

    # Act - Round 1 (all participate)
    advance_round(discussion, round_num=1)
    for p in participants:
        submit_and_approve(p, discussion, f"Round 1 response")
    complete_round(discussion, round_num=1)

    # Act - Round 2 (5 dropout)
    advance_round(discussion, round_num=2)
    for p in participants[:15]:  # Only 15 submit
        submit_and_approve(p, discussion, f"Round 2 response")
    complete_round(discussion, round_num=2)

    # Act - Round 3 (10 total remaining)
    advance_round(discussion, round_num=3)
    for p in participants[:10]:  # Only 10 submit
        submit_and_approve(p, discussion, f"Round 3 response")
    complete_round(discussion, round_num=3)

    # Assert
    sankey = get_sankey(discussion)

    col1_nodes = sankey.get_column_nodes(round_num=1)
    col2_nodes = sankey.get_column_nodes(round_num=2)
    col3_nodes = sankey.get_column_nodes(round_num=3)

    assert sum(n.user_count for n in col1_nodes) == 20
    assert sum(n.user_count for n in col2_nodes) == 15
    assert sum(n.user_count for n in col3_nodes) == 10

    # Assert - No synthetic dropout nodes
    all_nodes = col1_nodes + col2_nodes + col3_nodes
    assert not any(n.label.lower() in ["dropout", "no response"] for n in all_nodes)

    # Assert - Edge counts reflect actual transitions
    edges_r1_r2 = sankey.get_edges_between(round_1, round_2)
    edges_r2_r3 = sankey.get_edges_between(round_2, round_3)

    assert sum(e.weight for e in edges_r1_r2) == 15  # Only continuing participants
    assert sum(e.weight for e in edges_r2_r3) == 10
```

**Dependencies**: Spec 2 (dropout detection), Spec 5

---

## Test Suite 6: Question Progression (Spec 6)

### QP-001: Question Constraints Enforced (What/How Only, No Voting)

**Objective**: Verify Representation Not Adjudication principle

**Setup**:
- Host-defined mode
- Host attempts to create questions with prohibited patterns

**Test Steps**:
1. Host attempts: "Why do you think this happened?" → REJECTED
2. Host attempts: "Should we vote on this proposal?" → REJECTED
3. Host attempts: "Rank these options from best to worst" → REJECTED
4. Host attempts: "Do you prefer option A or B?" → REJECTED
5. Host submits: "What obstacles are preventing progress?" → ACCEPTED
6. Host submits: "How can we address these obstacles?" → ACCEPTED

**Expected Results**:
- 4 rejections with clear error messages
- 2 acceptances
- Error messages cite specific constraint violation
- 100% validation rate (no prohibited questions bypass filter)

**Test Code**:
```python
def test_question_constraints():
    # Arrange
    discussion = create_discussion(mode="HOST_DEFINED")
    host = create_host()

    # Act & Assert - Prohibited patterns
    with pytest.raises(ValidationError, match="must start with What or How"):
        add_question(discussion, host, "Why do you think this happened?")

    with pytest.raises(ValidationError, match="no voting"):
        add_question(discussion, host, "Should we vote on this proposal?")

    with pytest.raises(ValidationError, match="no ranking"):
        add_question(discussion, host, "Rank these options from best to worst")

    with pytest.raises(ValidationError, match="no binary choice"):
        add_question(discussion, host, "Do you prefer option A or B?")

    # Act & Assert - Valid questions
    q1 = add_question(discussion, host, "What obstacles are preventing progress?")
    q2 = add_question(discussion, host, "How can we address these obstacles?")

    assert q1.status == "VALIDATED"
    assert q2.status == "VALIDATED"
    assert q1.text.startswith("What")
    assert q2.text.startswith("How")
```

**Dependencies**: Spec 6

---

### QP-002: Auto-Generated Questions Reference Sankey Patterns

**Objective**: Verify auto-questions use temporal data, not random prompts

**Setup**:
- Auto-generated mode
- 2 rounds with clear cluster movement

**Test Steps**:
1. Round 1: Cluster A "Funding issues" (60%), Cluster B "Timeline concerns" (40%)
2. Round 2 auto-question generation triggered
3. Validate generated question references Round 1 clusters or movement

**Expected Results**:
- Generated question mentions "funding" OR "timeline" OR "concerns"
- Question references cluster labels (actual participant language)
- Question generated within 30 seconds (95th percentile)
- Question does NOT reference external data or generic prompts

**Test Code**:
```python
def test_auto_question_sankey_context():
    # Arrange
    discussion = create_discussion(
        mode="AUTO_GENERATED",
        seed_question="What are our main challenges?"
    )
    participants = create_participants(count=10)

    # Act - Round 1 with clear themes
    advance_round(discussion, round_num=1)
    for p in participants[:6]:
        submit_and_approve(p, discussion, "We need more funding for equipment")
    for p in participants[6:]:
        submit_and_approve(p, discussion, "The timeline is too aggressive")

    complete_round(discussion, round_num=1)

    # Act - Auto-generation
    start_time = time.time()
    wait_for_auto_question(discussion, round_num=2)
    generation_time = time.time() - start_time

    # Assert
    q2 = get_question(discussion, round_num=2)

    assert generation_time < 30.0  # Performance requirement
    assert q2.text.startswith(("What", "How"))

    # Assert - References Round 1 context
    text_lower = q2.text.lower()
    assert any(keyword in text_lower for keyword in [
        "funding", "timeline", "equipment", "aggressive", "challenges"
    ])

    # Assert - Not generic
    generic_phrases = ["in general", "typically", "usually", "often"]
    assert not any(phrase in text_lower for phrase in generic_phrases)
```

**Dependencies**: Spec 5, Spec 6

---

## Test Suite 7: Constitutional Compliance

### CC-001: Zero Unapproved Summaries in Clustering (Intent Fidelity)

**Objective**: Verify Principle II compliance across all test scenarios

**Setup**:
- Run all E2E tests with assertion

**Expected Results**:
- 100% of summaries entering clustering have status=APPROVED
- Zero PENDING_REVIEW, REJECTED, or SUPERSEDED summaries in clusters
- Audit log confirms approval gate enforcement

**Test Code**:
```python
def test_intent_fidelity_across_all_scenarios():
    # Run all E2E scenarios
    for scenario in [e2e_001, e2e_002, pc_002, sa_001, sa_002]:
        discussion = run_scenario(scenario)

        # Assert - Clustering input validation
        for round_num in range(1, discussion.total_rounds + 1):
            clustering_input = get_clustering_input(discussion, round_num)

            assert all(s.status == "APPROVED" for s in clustering_input), \
                f"Scenario {scenario}: Round {round_num} contains unapproved summary"

            # Assert - Audit trail
            audit_events = get_audit_log(discussion, round_num,
                                         event_type="CLUSTERING_INPUT")
            assert all(e.validation_passed for e in audit_events)
```

**Dependencies**: All specs

---

### CC-002: Zero Forced Merges (Semantic Accuracy Over Aesthetics)

**Objective**: Verify Principle III compliance

**Setup**:
- Run clustering tests with forced-merge detection

**Expected Results**:
- Zero cluster merges based on size threshold
- Zero "miscellaneous" or "other" cluster labels
- All clusters semantically coherent (validated by medoid proximity)

**Test Code**:
```python
def test_no_forced_merges():
    for scenario in [cl_001, cl_002, sk_001]:
        discussion = run_scenario(scenario)

        for round_num in range(1, discussion.total_rounds + 1):
            clusters = get_clusters(discussion, round_num)

            # Assert - No minimum cluster size violation
            # (singletons allowed, so min size = 1)
            assert all(c.user_count >= 1 for c in clusters)

            # Assert - No generic labels (signs of forced merging)
            prohibited_labels = ["other", "miscellaneous", "various", "mixed"]
            for cluster in clusters:
                label_lower = cluster.label_summary.lower()
                assert not any(p in label_lower for p in prohibited_labels), \
                    f"Cluster {cluster.id} has generic label: {cluster.label_summary}"

            # Assert - Medoid coherence (members close to label)
            for cluster in clusters:
                assert_medoid_coherence(cluster, threshold=0.7)
```

**Dependencies**: Spec 4

---

### CC-003: Movement Tracking 100% Accurate (Temporal Transparency)

**Objective**: Verify Principle IV compliance

**Setup**:
- Run Sankey tests with edge validation

**Expected Results**:
- Edge weights match actual participant transitions (zero mismatches)
- No edges exceed user intersection between rounds
- Alignment metadata does NOT alter edge computation

**Test Code**:
```python
def test_temporal_transparency():
    discussion = run_scenario(sk_001)

    sankey = get_sankey(discussion)

    for edge in sankey.edges:
        # Reconstruct actual transitions
        source_cluster = get_cluster_by_id(edge.source_id)
        target_cluster = get_cluster_by_id(edge.target_id)

        source_round = source_cluster.round_id
        target_round = target_cluster.round_id

        # Count participants actually in both clusters
        actual_movers = set(source_cluster.member_user_ids) & \
                        set(target_cluster.member_user_ids)

        # Assert - Edge weight = actual count
        assert edge.weight == len(actual_movers), \
            f"Edge {edge.source_id}→{edge.target_id}: " \
            f"weight={edge.weight} but actual movers={len(actual_movers)}"

        # Assert - Alignment doesn't inflate edges
        if source_cluster.display_group_id == target_cluster.display_group_id:
            # Even with alignment, edge ONLY counts actual movers
            assert edge.weight <= len(actual_movers)
```

**Dependencies**: Spec 5

---

## Test Suite 8: Performance & Scale

### PERF-001: 100 Participants Process in <2 Seconds (Spec 5)

**Objective**: Verify Spec 5 SC-004 performance requirement

**Setup**:
- 100 participants, 3 rounds
- Hot cache (after warmup)

**Expected Results**:
- Sankey construction: <2 seconds per round
- 95th percentile: <1.5 seconds

**Test Code**:
```python
def test_sankey_performance():
    # Arrange
    discussion = setup_discussion_with_data(participants=100, rounds=3)

    # Act - Warmup
    construct_sankey(discussion, round_num=1)

    # Act - Measure
    times = []
    for round_num in [2, 3]:
        start = time.perf_counter()
        construct_sankey(discussion, round_num=round_num)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    # Assert
    avg_time = statistics.mean(times)
    assert avg_time < 2.0, f"Average: {avg_time:.2f}s"
    assert max(times) < 2.5, f"Max: {max(times):.2f}s"
```

**Dependencies**: Spec 5

---

### PERF-002: Auto-Question Generation in <30 Seconds (Spec 6)

**Objective**: Verify Spec 6 SC-002 performance requirement

**Setup**:
- Auto-generated mode
- Realistic Sankey input (20 clusters, 5 edges each)

**Expected Results**:
- 95% of generations: <30 seconds
- 99% of generations: <45 seconds

**Test Code**:
```python
def test_auto_question_performance():
    # Arrange - 20 test runs
    times = []

    for i in range(20):
        discussion = create_discussion(mode="AUTO_GENERATED")
        populate_sankey_data(discussion, clusters=20, edges=100)

        # Act
        start = time.perf_counter()
        generate_next_question(discussion, round_num=2)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    # Assert
    p95 = statistics.quantiles(times, n=20)[18]  # 95th percentile
    p99 = statistics.quantiles(times, n=20)[19]  # 99th percentile

    assert p95 < 30.0, f"P95: {p95:.2f}s"
    assert p99 < 45.0, f"P99: {p99:.2f}s"
```

**Dependencies**: Spec 6

---

## Test Execution Plan

### Phase 1: Unit Tests (Per-Spec)
- Run during spec implementation
- Target: Each spec's test suite passes independently
- **Estimated Duration**: 2 weeks (parallel per spec)

### Phase 2: Integration Tests (Cross-Spec)
- Run after Phase 1 complete
- Target: Contracts validated, E2E flows pass
- **Estimated Duration**: 1 week

### Phase 3: Performance Tests
- Run after Phase 2 complete
- Target: All performance benchmarks met
- **Estimated Duration**: 3 days

### Phase 4: Constitutional Compliance Audit
- Run after Phase 3 complete
- Target: All 7 principles verified across scenarios
- **Estimated Duration**: 2 days

---

## Pass/Fail Criteria

**MVP RELEASE GATE**: ALL tests PASS with:
- Zero failures
- Zero flakes (if test flakes, root cause fixed)
- Performance targets met (no degradation allowed)
- Constitutional compliance: 100% (no violations)

**Failure Response**:
1. Identify failing test
2. Root cause analysis (spec ambiguity vs. implementation bug)
3. Fix implementation OR update spec if ambiguity found
4. Re-run full suite
5. Repeat until all pass

---

## Related Documents

- `PROTOCOL_SUITE_INDEX.md`: Protocol architecture
- `CONFLICTS_RESOLUTIONS.md`: Known conflicts and resolutions
- `CANONICAL_GLOSSARY.md`: Standardized terminology
- `.specify/memory/constitution.md`: Constitutional principles

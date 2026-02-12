"""
LLM prompt templates for autonomous question generation.

Prompt structure (token allocation):
- Constitutional principles: 15%
- Sankey analysis context: 60%
- Previous question history: 25%

Questions must follow constitutional constraints:
- Start with "What" or "How"
- No "Why", "Do you", "Should we", "Would you"
- No voting/ranking (vote, rank, best, worst, choose)
- No binary yes/no questions
- Length: 10-200 characters
"""

from typing import List, Dict, Any
import json


# Main prompt template for question generation from Sankey patterns
QUESTION_GENERATION_PROMPT = """You are generating the next question for a facilitated discussion using the OpenDiscuss protocol.

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
Generate the next question (Round {next_round_num}) that:
1. Explores emerging patterns in the Sankey (e.g., consolidation, fragmentation, high dropout)
2. Follows naturally from previous questions (no repetition)
3. Deepens inquiry into constraints, solutions, or needs revealed by thought spaces

Output ONLY the question text (no explanation)."""


# Stricter prompt template used after validation failures
STRICT_QUESTION_GENERATION_PROMPT = """You are generating the next question for a facilitated discussion using the OpenDiscuss protocol.

CRITICAL RULES - YOUR PREVIOUS ATTEMPT VIOLATED CONSTRAINTS:
- Question MUST start with "What" or "How" (ONLY these two words)
- Question MUST NOT contain: "Why", "Do you", "Should we", "Would you", "Would"
- Question MUST NOT contain: vote, rank, best, worst, choose, select, pick, prefer, order, top, bottom
- Question MUST be 10-200 characters
- Question MUST NOT be a yes/no question or binary choice

FAILED ATTEMPT:
The question "{failed_question}" was rejected because: {rejection_reason}

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
Generate a NEW question (Round {next_round_num}) that:
1. STRICTLY follows all rules above
2. Explores Sankey patterns
3. Differs from previous questions AND the failed attempt

Output ONLY the question text (no explanation)."""


def build_generation_prompt(
    round_num: int,
    previous_questions: List[str],
    sankey_data: Dict[str, Any],
    failed_question: str = None,
    rejection_reason: str = None
) -> str:
    """
    Build LLM prompt from Sankey graph and question history.

    Args:
        round_num: Current round number
        previous_questions: List of previous question texts
        sankey_data: Dictionary containing Sankey graph data:
            - nodes: List of thought space nodes with labels and member counts
            - flows: List of flow edges between nodes
            - total_participants: Total number of participants
        failed_question: Previously generated question that failed validation (optional)
        rejection_reason: Reason why the question failed (optional)

    Returns:
        Formatted prompt string ready for LLM
    """
    # Format previous questions
    if previous_questions:
        questions_text = "\n".join(
            f"Round {i+1}: {q}" for i, q in enumerate(previous_questions)
        )
    else:
        questions_text = "None (this is the first question)"

    # Extract thought spaces with member counts
    nodes = sankey_data.get("nodes", [])
    thought_spaces_json = json.dumps([
        {
            "label": node.get("label_summary", ""),
            "member_count": node.get("member_count", 0),
            "member_pct": round(node.get("member_pct", 0.0), 2)
        }
        for node in nodes
    ], indent=2)

    # Extract top 3 thought spaces by member count
    sorted_nodes = sorted(nodes, key=lambda n: n.get("member_count", 0), reverse=True)
    top_3_nodes = sorted_nodes[:3]
    top_3_spaces = ", ".join(
        f'"{node.get("label_summary", "")}" ({node.get("member_count", 0)} participants)'
        for node in top_3_nodes
    )

    # Extract and format flow patterns
    flows = sankey_data.get("flows", [])
    flow_patterns_json = json.dumps([
        {
            "source": flow.get("source_label", ""),
            "target": flow.get("target_label", ""),
            "participant_count": flow.get("participant_count", 0)
        }
        for flow in flows
    ], indent=2)

    # Extract top 3 flows by participant count
    sorted_flows = sorted(flows, key=lambda f: f.get("participant_count", 0), reverse=True)
    top_3_flows_list = sorted_flows[:3]
    top_3_flows = ", ".join(
        f'"{flow.get("source_label", "")}" → "{flow.get("target_label", "")}" '
        f'({flow.get("participant_count", 0)} participants)'
        for flow in top_3_flows_list
    ) if top_3_flows_list else "No significant flows yet"

    # Compute dropout summary
    dropout_count = sankey_data.get("dropout_count", 0)
    total_participants = sankey_data.get("total_participants", 0)
    dropout_pct = (dropout_count / total_participants * 100) if total_participants > 0 else 0
    dropout_summary = (
        f"{dropout_count} participants ({dropout_pct:.1f}%) did not continue from Round {round_num-1} to Round {round_num}"
        if round_num > 1 else "No dropout data (first round)"
    )

    # Choose template based on whether this is a retry after validation failure
    if failed_question and rejection_reason:
        template = STRICT_QUESTION_GENERATION_PROMPT
        return template.format(
            round_num=round_num,
            next_round_num=round_num + 1,
            previous_questions=questions_text,
            thought_spaces_with_member_counts=thought_spaces_json,
            flow_patterns=flow_patterns_json,
            dropout_summary=dropout_summary,
            top_3_spaces=top_3_spaces,
            top_3_flows=top_3_flows,
            failed_question=failed_question,
            rejection_reason=rejection_reason
        )
    else:
        template = QUESTION_GENERATION_PROMPT
        return template.format(
            round_num=round_num,
            next_round_num=round_num + 1,
            previous_questions=questions_text,
            thought_spaces_with_member_counts=thought_spaces_json,
            flow_patterns=flow_patterns_json,
            dropout_summary=dropout_summary,
            top_3_spaces=top_3_spaces,
            top_3_flows=top_3_flows
        )

"""
Base summarization prompt template for Spec 003.

Generates neutral, intent-preserving summaries from participant input.
Constitutional Principle: Intent Fidelity - preserve participant meaning exactly.
"""


def build_base_summary_prompt(submission_text: str, round_context: str = "") -> str:
    """
    Build base summarization prompt for initial generation.

    Prompt Engineering Goals:
    - 1-2 sentences (enforced in prompt, not programmatically)
    - Max 500 characters (validated in service layer)
    - Neutral, factual tone (no editorializing)
    - Preserve participant intent exactly (Intent Fidelity)
    - Focus on crux of participant's position

    Args:
        submission_text: Raw participant input to summarize
        round_context: Optional discussion question/topic for context

    Returns:
        str: Complete prompt for LLM
    """
    context_section = ""
    if round_context:
        context_section = f"\n\nDiscussion Topic:\n{round_context}\n"

    prompt = f"""Summarize the following participant input in 1-2 sentences (maximum 500 characters).

Requirements:
- Be concise, neutral, and factual
- Preserve the participant's core intent and position
- Focus on the crux of their argument or perspective
- Use clear, accessible language
- Do NOT editorialize, interpret, or add your own opinions
- Do NOT include phrases like "The participant thinks..." - write as a direct statement{context_section}

Participant Input:
{submission_text}

Summary:"""

    return prompt


def build_regeneration_prompt(
    submission_text: str,
    previous_summary: str,
    regen_count: int,
    round_context: str = "",
) -> str:
    """
    Build prompt for summary regeneration (after rejection).

    Regeneration Strategy (T037 - User Story 2):
    - Attempt 1: Vary focus (emphasize different aspect)
    - Attempt 2: Simplify language
    - Attempt 3: With correction signal (see correction_prompts.py)

    Args:
        submission_text: Original participant input
        previous_summary: Previous summary that was rejected
        regen_count: Number of regenerations so far (1-2 for auto-regen)
        round_context: Optional discussion question/topic

    Returns:
        str: Complete prompt for LLM
    """
    context_section = ""
    if round_context:
        context_section = f"\n\nDiscussion Topic:\n{round_context}\n"

    if regen_count == 1:
        # First regeneration: vary focus
        strategy_instruction = """
The previous summary was rejected. Try emphasizing a different aspect of the participant's position.
If the previous summary focused on the problem, focus on the solution (or vice versa).
"""
    elif regen_count == 2:
        # Second regeneration: simplify
        strategy_instruction = """
The previous summary was rejected again. Try simplifying the language and being more direct.
Use shorter sentences and clearer phrasing.
"""
    else:
        # Fallback for regen_count > 2 (shouldn't happen in US1, but defensive)
        strategy_instruction = """
The previous summary was rejected. Try a different approach to capture the participant's intent.
"""

    prompt = f"""Summarize the following participant input in 1-2 sentences (maximum 500 characters).

Requirements:
- Be concise, neutral, and factual
- Preserve the participant's core intent and position
- Focus on the crux of their argument or perspective
- Use clear, accessible language
- Do NOT editorialize, interpret, or add your own opinions
- Do NOT include phrases like "The participant thinks..." - write as a direct statement{context_section}

Previous Summary (REJECTED):
{previous_summary}

{strategy_instruction}

Participant Input:
{submission_text}

New Summary:"""

    return prompt

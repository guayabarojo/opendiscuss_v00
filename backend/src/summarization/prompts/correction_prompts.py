"""
Correction signal prompt templates for Spec 003 (User Story 3).

Generates correction-signal-enhanced regeneration prompts after 2 rejections.
Constitutional Principle: Intent Fidelity - incorporate participant feedback exactly.
"""

from ..models.correction_signal import ReasonTag


def build_correction_prompt(
    submission_text: str,
    previous_summary: str,
    reason_tag: ReasonTag,
    feedback_text: str = "",
    round_context: str = "",
) -> str:
    """
    Build prompt for correction-signal-enhanced regeneration (regen_count=3).

    This is the final regeneration attempt after 2 automatic regenerations failed.
    Uses structured reason tags and optional participant feedback to guide LLM.

    Task T051 - User Story 3

    Args:
        submission_text: Original participant input
        previous_summary: Last rejected summary (regen_count=2)
        reason_tag: Structured reason for rejection (WRONG_CRUX, TOO_VAGUE, etc.)
        feedback_text: Optional participant feedback (<= 240 chars)
        round_context: Optional discussion question/topic

    Returns:
        str: Complete prompt for LLM
    """
    context_section = ""
    if round_context:
        context_section = f"\n\nDiscussion Topic:\n{round_context}\n"

    # Map reason tags to specific instructions
    reason_instructions = {
        ReasonTag.WRONG_CRUX: """
The participant indicated you identified the WRONG CRUX of their position.
Focus on finding the TRUE core point they're making. Re-read the input carefully to identify
what they consider most important. The crux might be different from what you initially thought.""",

        ReasonTag.TOO_VAGUE: """
The participant indicated the summary was TOO VAGUE.
Be MORE SPECIFIC. Include concrete details, numbers, or examples from their input.
Replace general statements with precise language that captures their exact position.""",

        ReasonTag.MISREPRESENTS_ME: """
The participant indicated the summary MISREPRESENTS their position.
This is critical - you may have changed their stance or added interpretation they didn't intend.
Use their exact framing. Do NOT rephrase in a way that alters meaning. Stay closer to their words.""",

        ReasonTag.MISSED_CONSTRAINT: """
The participant indicated you MISSED A KEY CONSTRAINT in their position.
Look for qualifiers, conditions, or limitations they stated. They likely have an "if", "when",
"only if", or other conditional statement that's essential to their position.""",

        ReasonTag.MISSED_SOLUTION: """
The participant indicated you MISSED THEIR PROPOSED SOLUTION.
They likely offered a specific recommendation, action, or approach. Focus on what they want to DO
or what they think SHOULD happen, not just the problem they identified.""",

        ReasonTag.OTHER: """
The participant indicated there's an issue with the summary (see their feedback below).
Carefully read their feedback and adjust your approach accordingly.""",
    }

    instruction = reason_instructions.get(
        reason_tag,
        "The participant rejected the previous summary. Try a different approach."
    )

    feedback_section = ""
    if feedback_text:
        feedback_section = f"""

Participant Feedback:
"{feedback_text}"
"""

    prompt = f"""Summarize the following participant input in 1-2 sentences (maximum 500 characters).

Requirements:
- Be concise, neutral, and factual
- Preserve the participant's core intent and position
- Focus on the crux of their argument or perspective
- Use clear, accessible language
- Do NOT editorialize, interpret, or add your own opinions
- Do NOT include phrases like "The participant thinks..." - write as a direct statement{context_section}

Previous Summary (REJECTED - Attempt 2):
{previous_summary}

CORRECTION SIGNAL from participant:
{instruction}{feedback_section}

This is your FINAL attempt (attempt 3/3). The participant has provided specific guidance above.
Carefully incorporate their correction signal into your new summary.

Participant Input:
{submission_text}

New Summary (FINAL ATTEMPT):"""

    return prompt


def get_reason_tag_display_name(reason_tag: ReasonTag) -> str:
    """
    Get human-readable display name for reason tag.

    Used for UI labels and logging.

    Args:
        reason_tag: ReasonTag enum value

    Returns:
        str: Display name
    """
    display_names = {
        ReasonTag.WRONG_CRUX: "Wrong crux - summary missed my main point",
        ReasonTag.TOO_VAGUE: "Too vague - summary needs more specificity",
        ReasonTag.MISREPRESENTS_ME: "Misrepresents me - summary changes my stance",
        ReasonTag.MISSED_CONSTRAINT: "Missed constraint - summary omitted key condition",
        ReasonTag.MISSED_SOLUTION: "Missed solution - summary omitted my proposal",
        ReasonTag.OTHER: "Other (see feedback)",
    }
    return display_names.get(reason_tag, reason_tag.value)


def get_reason_tag_description(reason_tag: ReasonTag) -> str:
    """
    Get detailed description for reason tag.

    Used for UI tooltips and help text.

    Args:
        reason_tag: ReasonTag enum value

    Returns:
        str: Detailed description
    """
    descriptions = {
        ReasonTag.WRONG_CRUX: (
            "The summary identified the wrong core point. Your main argument or "
            "perspective was not accurately captured."
        ),
        ReasonTag.TOO_VAGUE: (
            "The summary was too general or abstract. It needs more specific details "
            "to accurately represent your position."
        ),
        ReasonTag.MISREPRESENTS_ME: (
            "The summary changed or misrepresented your stance. The way it's phrased "
            "makes it sound like you said something different than you intended."
        ),
        ReasonTag.MISSED_CONSTRAINT: (
            "The summary omitted an important condition or qualifier from your input. "
            "Your position has specific constraints that weren't captured."
        ),
        ReasonTag.MISSED_SOLUTION: (
            "The summary missed your proposed solution or recommendation. It focused "
            "on the problem but not what you think should be done."
        ),
        ReasonTag.OTHER: (
            "The issue doesn't fit the above categories. Please provide specific "
            "feedback in the text box below."
        ),
    }
    return descriptions.get(reason_tag, "")

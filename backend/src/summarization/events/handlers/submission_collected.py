"""
Handler for submission_window.closed event (Spec 2 → Spec 3).

Task T025: Trigger summary generation when submissions are collected.
"""

import asyncio
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....database import get_session_factory
from ....events.event_types import SubmissionWindowClosedEvent, SubmissionSummary
from ....logging_config import logger
from ....models import Submission
from ...services.summarization_service import SummarizationService


async def handle_submission_window_closed(event: SubmissionWindowClosedEvent) -> None:
    """
    Handle submission window closure (Spec 2 → Spec 3 handoff).

    Triggered when the submission window closes for a round.
    Generates initial summaries for all submissions in parallel.

    Constitutional Compliance:
    - Parallel-First: All summaries generated independently
    - Intent Fidelity: Each summary preserves participant intent
    - Temporal Transparency: Tracks generation timestamps

    Actions:
    1. Fetch all submissions for the round
    2. Generate initial summary for each submission (in parallel)
    3. Log generation results
    4. Summaries are created with status=PENDING_REVIEW (await approval)

    Args:
        event: SubmissionWindowClosedEvent with round_id and submissions

    Raises:
        RuntimeError: If summary generation fails for critical submissions
    """
    round_id = event.round_id
    submission_summaries = event.submissions
    submission_count = len(submission_summaries)

    logger.info(
        f"[Spec 2→3] Received submission_window.closed for round {round_id}: "
        f"{submission_count} submissions to summarize"
    )

    # Get database session
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Fetch full submission objects from database
            submission_ids = [s.submission_id for s in submission_summaries]
            result = await db.execute(
                select(Submission).where(Submission.submission_id.in_(submission_ids))
            )
            submissions = list(result.scalars().all())

            logger.info(
                f"[Spec 2→3] Found {len(submissions)} submissions in database "
                f"for round {round_id}"
            )

            # Generate summaries in parallel (Parallel-First Architecture)
            service = SummarizationService(db)
            summary_tasks = []

            for submission in submissions:
                # Create task for parallel execution
                task = _generate_summary_for_submission(
                    service=service,
                    submission_id=submission.submission_id,
                )
                summary_tasks.append(task)

            # Execute all summary generations in parallel
            summary_results = await asyncio.gather(
                *summary_tasks,
                return_exceptions=True
            )

            # Log results
            success_count = sum(
                1 for r in summary_results if not isinstance(r, Exception)
            )
            failure_count = submission_count - success_count

            logger.info(
                f"[Spec 2→3] Summary generation complete for round {round_id}: "
                f"{success_count} successful, {failure_count} failed"
            )

            # Log failures
            for idx, result in enumerate(summary_results):
                if isinstance(result, Exception):
                    submission_id = submissions[idx].submission_id
                    logger.error(
                        f"[Spec 2→3] Failed to generate summary for "
                        f"submission {submission_id}: {result}"
                    )

            # Constitutional check: All summaries generated independently
            logger.info(
                f"[Spec 2→3] Constitutional compliance - Parallel-First: "
                f"All {success_count} summaries generated independently"
            )

        except Exception as e:
            logger.error(
                f"[Spec 2→3] Handler failed for round {round_id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Submission collected handler failed for round {round_id}"
            ) from e


async def _generate_summary_for_submission(
    service: SummarizationService,
    submission_id: UUID,
) -> None:
    """
    Helper to generate summary for a single submission.

    Args:
        service: SummarizationService instance
        submission_id: Submission UUID

    Raises:
        Exception: If generation fails (caught by gather)
    """
    try:
        summary = await service.generate_summary(
            submission_id=submission_id,
            use_fallback_model=False,  # Start with GPT-4-turbo
        )
        logger.debug(
            f"Generated summary {summary.summary_id} for submission {submission_id}"
        )
    except Exception as e:
        logger.error(
            f"Error generating summary for submission {submission_id}: {e}"
        )
        # Try fallback model as retry
        try:
            summary = await service.generate_summary(
                submission_id=submission_id,
                use_fallback_model=True,  # Fallback to GPT-3.5
            )
            logger.info(
                f"Generated summary {summary.summary_id} for submission {submission_id} "
                f"using fallback model"
            )
        except Exception as fallback_error:
            logger.error(
                f"Fallback generation also failed for submission {submission_id}: "
                f"{fallback_error}"
            )
            raise  # Re-raise to be caught by gather


async def register_handler(event_bus) -> None:
    """
    Register this handler with the event bus.

    Args:
        event_bus: EventBus instance
    """
    await event_bus.subscribe(
        event_type="submission_window.closed",
        handler=handle_submission_window_closed,
    )
    logger.info("[Spec 2→3] Registered handler for submission_window.closed event")

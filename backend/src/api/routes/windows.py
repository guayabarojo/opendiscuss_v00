"""
Window status endpoint for submission window enforcement.
Provides server-authoritative time and window status.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.schemas import WindowStatusResponse
from src.database import get_db
from src.models.round import Round

router = APIRouter(prefix="/rounds", tags=["windows"])


@router.get("/{round_id}/window", response_model=WindowStatusResponse)
async def get_window_status(
    round_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> WindowStatusResponse:
    """
    Get submission window status for a round.

    Returns server-authoritative time, window boundaries, time remaining,
    and window open status.

    Args:
        round_id: UUID of the round
        db: Database session

    Returns:
        WindowStatusResponse with window details

    Raises:
        404: Round not found
    """
    # Query round
    stmt = select(Round).where(Round.round_id == round_id)
    result = await db.execute(stmt)
    round_obj = result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Round {round_id} not found"
        )

    # Get current server time
    current_time = datetime.utcnow()

    # Extract window times
    window_start = round_obj.submission_window_start
    window_end = round_obj.submission_window_end
    round_status = round_obj.status.value if hasattr(round_obj.status, 'value') else str(round_obj.status)

    # Calculate time remaining and window status
    if window_start is None or window_end is None:
        # Window not yet opened
        time_remaining_seconds = None
        is_open = False
        window_status = "NOT_OPEN"
    elif current_time < window_start:
        # Before window opens
        time_remaining_seconds = int((window_start - current_time).total_seconds())
        is_open = False
        window_status = "BEFORE_WINDOW"
    elif window_start <= current_time < window_end:
        # Window is open (inclusive start, exclusive end)
        time_remaining_seconds = int((window_end - current_time).total_seconds())
        is_open = True
        window_status = "OPEN"
    else:
        # Window has closed
        time_remaining_seconds = 0
        is_open = False
        window_status = "CLOSED"

    return WindowStatusResponse(
        round_id=round_id,
        window_start=window_start,
        window_end=window_end,
        current_time=current_time,
        time_remaining_seconds=time_remaining_seconds,
        is_open=is_open,
        status=window_status,
        round_status=round_status
    )

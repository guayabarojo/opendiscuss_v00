"""
Example usage of the Event Bus and Timing Service.

This demonstrates the basic patterns for emitting and subscribing to events,
as well as scheduling window closures with the timing service.

To run this example:
1. Ensure Redis is running (docker-compose up -d)
2. Install dependencies (poetry install)
3. Run: poetry run python examples/event_bus_usage.py
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.events import (
    EventBus,
    DiscussionStartedEvent,
    SubmissionWindowClosedEvent,
    RoundCompleteEvent,
)
from src.services import TimingService


async def handle_discussion_started(event: DiscussionStartedEvent) -> None:
    """Example handler for discussion.started events."""
    print(f"[Handler] Discussion {event.discussion_id} started at {event.timestamp}")
    print(f"[Handler] First round: {event.round_id}")


async def handle_submission_window_closed(event: SubmissionWindowClosedEvent) -> None:
    """Example handler for submission_window.closed events."""
    print(f"[Handler] Submission window closed for round {event.round_id}")
    print(f"[Handler] Received {len(event.submissions)} submissions")


async def handle_round_complete(event: RoundCompleteEvent) -> None:
    """Example handler for round.complete events."""
    print(f"[Handler] Round {event.round_id} completed at {event.timestamp}")
    if event.next_round_id:
        print(f"[Handler] Next round: {event.next_round_id}")
    else:
        print("[Handler] Final round - discussion complete")


async def main() -> None:
    """Demonstrate event bus and timing service usage."""
    print("=== Event Bus and Timing Service Demo ===\n")

    # Initialize event bus
    print("1. Connecting to event bus...")
    event_bus = EventBus()
    await event_bus.connect()
    print(f"   Connected: {event_bus.is_connected()}\n")

    # Subscribe to events
    print("2. Subscribing to events...")
    await event_bus.subscribe("discussion.started", handle_discussion_started)
    await event_bus.subscribe("submission_window.closed", handle_submission_window_closed)
    await event_bus.subscribe("round.complete", handle_round_complete)
    print("   Subscribed to 3 event types\n")

    # Wait a moment for subscriptions to be active
    await asyncio.sleep(0.5)

    # Emit discussion started event
    print("3. Emitting discussion.started event...")
    discussion_id = uuid4()
    round_id = uuid4()
    await event_bus.emit(
        "discussion.started",
        DiscussionStartedEvent(
            discussion_id=discussion_id,
            round_id=round_id,
            timestamp=datetime.now(timezone.utc),
        ),
    )
    await asyncio.sleep(0.5)  # Wait for handlers to process
    print()

    # Initialize timing service
    print("4. Starting timing service...")
    timing_service = TimingService()
    await timing_service.connect()
    await timing_service.start_worker()
    print(f"   Worker running: {timing_service.is_running()}\n")

    # Schedule a window closure (5 seconds from now for demo)
    print("5. Scheduling submission window closure (5 seconds from now)...")
    close_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    await timing_service.schedule_closure(round_id, close_at)
    scheduled_count = await timing_service.get_scheduled_count()
    print(f"   Scheduled closures: {scheduled_count}")
    next_closure = await timing_service.get_next_closure()
    if next_closure:
        print(f"   Next closure: round {next_closure[0]} at {next_closure[1]}\n")

    # Wait for the scheduled closure to fire
    print("6. Waiting for scheduled closure (this will take 5 seconds)...")
    await asyncio.sleep(6)  # Wait a bit longer to ensure closure processes
    print()

    # Emit round complete event
    print("7. Emitting round.complete event...")
    await event_bus.emit(
        "round.complete",
        RoundCompleteEvent(
            round_id=round_id,
            next_round_id=uuid4(),  # Simulate multi-round discussion
            timestamp=datetime.now(timezone.utc),
        ),
    )
    await asyncio.sleep(0.5)  # Wait for handlers to process
    print()

    # Check service health
    print("8. Health checks...")
    event_bus_healthy = await event_bus.health_check()
    timing_service_healthy = await timing_service.health_check()
    print(f"   Event bus healthy: {event_bus_healthy}")
    print(f"   Timing service healthy: {timing_service_healthy}\n")

    # Cleanup
    print("9. Disconnecting services...")
    await timing_service.disconnect()
    await event_bus.disconnect()
    print("   Services disconnected\n")

    print("=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

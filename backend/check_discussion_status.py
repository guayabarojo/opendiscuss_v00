"""
Quick script to check discussion status in the database
"""
import asyncio
from src.database import get_session_factory, init_db
from src.models.discussion import Discussion
from sqlalchemy import select

async def check_status():
    discussion_id = '03fdec50-97d2-44da-97be-d6f786b30b2a'

    # Initialize database connection
    await init_db()
    session_factory = get_session_factory()

    async with session_factory() as db:
        result = await db.execute(
            select(Discussion).where(Discussion.discussion_id == discussion_id)
        )
        disc = result.scalar_one_or_none()

        if disc:
            print(f'Discussion ID: {disc.discussion_id}')
            print(f'Status: {disc.status}')
            print(f'Current round: {disc.current_round_num}')
            print(f'Total rounds: {disc.total_rounds}')
            print(f'Created at: {disc.created_at}')
        else:
            print(f'Discussion {discussion_id} not found')

if __name__ == '__main__':
    asyncio.run(check_status())

"""
Create database tables directly using SQLAlchemy models.
"""
import asyncio
from src.database import get_engine
from src.models import Base

async def create_tables():
    """Create all tables defined in SQLAlchemy models."""
    engine = get_engine()
    async with engine.begin() as conn:
        print("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("✓ All tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())

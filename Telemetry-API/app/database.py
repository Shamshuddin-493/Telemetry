import os
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

load_dotenv(interpolate=True)

db_url = os.getenv("DB_URL") or os.getenv("DATABASE_URL") or "sqlite:///./telemetry.db"


engine = create_async_engine(
    db_url, 
    echo=False, 
    pool_size=20,
    max_overflow=10
    )
AsyncSessionLocal= async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
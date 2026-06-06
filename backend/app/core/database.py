from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

logger.debug("Async database engine created (pool target: %s)", settings.DATABASE_URL.split("@")[-1])


async def get_db():
    """Yield a database session to be used as a FastAPI dependency."""
    async with AsyncSessionLocal() as session:
        yield session

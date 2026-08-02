# @ai-generated
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.config.env_config import EnvConfig


class DatabaseManager:
    _engine: AsyncEngine = None
    _session_maker: async_sessionmaker[AsyncSession] = None

    @classmethod
    def initialize(cls) -> None:
        if cls._engine is not None:
            return
        db_url = (
            f"mysql+aiomysql://{EnvConfig.DB_USERNAME}:{EnvConfig.DB_PASSWORD}"
            f"@{EnvConfig.DB_HOST}:{EnvConfig.DB_PORT}/{EnvConfig.DB_DATABASE}"
            f"?charset=utf8mb4"
        )
        cls._engine = create_async_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,
        )
        cls._session_maker = async_sessionmaker(
            bind=cls._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @classmethod
    def get_session(cls) -> AsyncSession:
        if cls._session_maker is None:
            raise RuntimeError("Database not initialized")
        return cls._session_maker()

    @classmethod
    async def dispose(cls) -> None:
        if cls._engine is not None:
            await cls._engine.dispose()
            cls._engine = None
            cls._session_maker = None

    @classmethod
    async def health_check(cls) -> bool:
        try:
            async with cls.get_session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception:
            return False


async def get_db() -> AsyncSession:
    async with DatabaseManager.get_session() as session:
        yield session
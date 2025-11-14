from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker as sync_sessionmaker
class Base(DeclarativeBase):
    pass


# Синхронный движок для Alembic
sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", ""),  # Убираем asyncpg
    echo=True
)

SyncSessionLocal = sync_sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
engine = create_async_engine(
    settings.DATABASE_URL, echo=False, pool_pre_ping=True
)

AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_models():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
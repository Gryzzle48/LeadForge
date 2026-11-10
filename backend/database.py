import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import DATABASE_URL, DB_CONNECT_ARGS
from .models.audit_log import AuditLog  # noqa: F401
from .models.campaign import Base
from .models.lead import Lead  # noqa: F401

logger = logging.getLogger(__name__)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=DB_CONNECT_ARGS,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)

_COLUMN_UPDATES = (
    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS status_detail TEXT",
    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS sheet_url VARCHAR(500)",
    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS min_reviews INTEGER",
    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS max_reviews INTEGER",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS maps_url TEXT",
)


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.warning(f"Database init failed (server will still start): {e}")
        return

    for statement in _COLUMN_UPDATES:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(statement))
        except Exception as e:
            logger.warning("Schema update skipped (%s): %s", statement, e)


async def get_session():
    async with async_session() as session:
        yield session

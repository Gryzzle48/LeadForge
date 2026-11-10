import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .config import DATABASE_URL
from .models.campaign import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"timeout": 5})
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Lightweight forward-compatible migrations for existing PostgreSQL
            # installations. New databases already receive these via create_all.
            if engine.dialect.name == "postgresql":
                statements = [
                    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS country VARCHAR(80)",
                    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS state VARCHAR(120)",
                    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS city VARCHAR(120)",
                    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS max_results INTEGER NOT NULL DEFAULT 100",
                    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS instagram_url VARCHAR(500)",
                    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS google_maps_url VARCHAR(1000)",
                ]
                for statement in statements:
                    await conn.execute(text(statement))

        logger.info("Database tables created/updated successfully")
    except Exception as e:
        logger.exception("Database initialization/migration failed: %s", e)
        raise


async def get_session():
    async with async_session() as session:
        yield session

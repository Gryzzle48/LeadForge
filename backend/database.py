import logging

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import DATABASE_URL, DB_CONNECT_ARGS
from .models.audit_log import AuditLog  # noqa: F401
from .models.campaign import Base
from .models.lead import Lead  # noqa: F401
from .schema_upgrade import plan_schema_upgrade

logger = logging.getLogger(__name__)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=DB_CONNECT_ARGS,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)

_SCHEMA_TABLES = tuple(Base.metadata.tables)


async def _apply_schema_upgrade():
    async with engine.begin() as conn:
        statement = text(
            """
            SELECT table_name, column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN :tables
            """
        ).bindparams(bindparam("tables", expanding=True))
        result = await conn.execute(statement, {"tables": list(_SCHEMA_TABLES)})
        db_columns = [
            {
                "table_name": row.table_name,
                "column_name": row.column_name,
                "is_nullable": row.is_nullable,
            }
            for row in result
        ]
        statements = plan_schema_upgrade(Base.metadata, db_columns)

    for statement in statements:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(statement))
            logger.info("Schema upgrade applied: %s", statement)
        except Exception as exc:
            logger.warning("Schema upgrade skipped (%s): %s", statement, exc)


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.warning(f"Database init failed (server will still start): {e}")
        return

    try:
        await _apply_schema_upgrade()
    except Exception as exc:
        logger.warning(f"Schema upgrade failed (server will still start): {exc}")


async def get_session():
    async with async_session() as session:
        yield session

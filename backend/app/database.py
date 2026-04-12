from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import resolved_database_url

engine: AsyncEngine = create_async_engine(
    resolved_database_url(),
    echo=False,
    future=True,
)

async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.run_sync(_run_legacy_migrations)


def _run_legacy_migrations(sync_conn) -> None:
    """
    Lightweight compatibility migrations for existing local DBs.
    Keeps old data and adds newly introduced columns/tables.
    """
    dialect_name = sync_conn.dialect.name
    user_table = "`user`" if dialect_name == "mysql" else '"user"'
    varchar_255 = "VARCHAR(255)"

    insp = inspect(sync_conn)
    tables = set(insp.get_table_names())
    if "user" in tables:
        cols = {c["name"] for c in insp.get_columns("user")}
        if "email_verified" not in cols:
            sync_conn.execute(text(f"ALTER TABLE {user_table} ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
        if "plan" not in cols:
            sync_conn.execute(text(f"ALTER TABLE {user_table} ADD COLUMN plan {varchar_255} DEFAULT 'free'"))
    if "resume" in tables:
        cols = {c["name"] for c in insp.get_columns("resume")}
        if "active_template_id" not in cols:
            sync_conn.execute(text(f"ALTER TABLE resume ADD COLUMN active_template_id {varchar_255} DEFAULT ''"))
        if "updated_at" not in cols:
            sync_conn.execute(text("ALTER TABLE resume ADD COLUMN updated_at DATETIME"))
            if dialect_name == "mysql":
                sync_conn.execute(text("UPDATE resume SET updated_at = COALESCE(updated_at, created_at, NOW())"))
            else:
                sync_conn.execute(text("UPDATE resume SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
    if "emailotpcode" not in tables:
        # create_all usually handles this; this guard helps when metadata drift happens.
        SQLModel.metadata.tables["emailotpcode"].create(bind=sync_conn, checkfirst=True)
    else:
        cols = {c["name"] for c in insp.get_columns("emailotpcode")}
        if "purpose" not in cols:
            sync_conn.execute(text(f"ALTER TABLE emailotpcode ADD COLUMN purpose {varchar_255} DEFAULT 'register'"))
        if "created_at" not in cols:
            sync_conn.execute(text("ALTER TABLE emailotpcode ADD COLUMN created_at DATETIME"))
            if dialect_name == "mysql":
                sync_conn.execute(text("UPDATE emailotpcode SET created_at = COALESCE(created_at, expires_at, NOW())"))
            else:
                sync_conn.execute(
                    text("UPDATE emailotpcode SET created_at = COALESCE(created_at, expires_at, CURRENT_TIMESTAMP)")
                )

    # MySQL: SQLModel default str columns were VARCHAR(255); widen for JDs and scraped listings.
    if dialect_name == "mysql":
        if "jdanalysis" in tables:
            sync_conn.execute(text("ALTER TABLE jdanalysis MODIFY COLUMN raw_jd MEDIUMTEXT"))
        if "joblisting" in tables:
            sync_conn.execute(text("ALTER TABLE joblisting MODIFY COLUMN description MEDIUMTEXT"))


async def get_session():
    async with async_session_factory() as session:
        yield session

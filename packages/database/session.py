import os
import ssl
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from packages.database.models import Base

MONOREPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = MONOREPO_ROOT / "empire_state.db"


def _normalize_async_db_url(raw_url: str) -> tuple[str, dict]:
    url = (raw_url or "").strip().strip("'").strip('"')
    if url.startswith("psql "):
        # Caso o utilizador cole o comando "psql 'postgresql://...'" inteiro do Neon
        for token in url.split():
            t_clean = token.strip("'").strip('"')
            if t_clean.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
                url = t_clean
                break

    if not url:
        return f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH}", {"timeout": 20}

    if url.startswith("sqlite"):
        return url, {"timeout": 20}

    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]

    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    need_ssl = False
    clean_pairs = []
    for k, v in query_pairs:
        kl = k.lower()
        if kl in ("sslmode", "ssl"):
            if v.lower() not in ("disable", "false", "0"):
                need_ssl = True
            continue
        if kl in ("channel_binding", "options"):
            continue
        clean_pairs.append((k, v))

    if "neon.tech" in (parts.hostname or "") or "render.com" in (parts.hostname or "") or "supabase" in (parts.hostname or ""):
        need_ssl = True

    clean_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(clean_pairs), parts.fragment))
    connect_args: dict = {}
    if need_ssl:
        ctx = ssl.create_default_context()
        connect_args["ssl"] = ctx
    if "pooler" in (parts.hostname or ""):
        connect_args["statement_cache_size"] = 0
    return clean_url, connect_args


RAW_DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_URL, _CONNECT_ARGS = _normalize_async_db_url(RAW_DATABASE_URL)
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=not IS_SQLITE,
    pool_recycle=240 if not IS_SQLITE else -1,
    connect_args=_CONNECT_ARGS,
)

if IS_SQLITE:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=15000;")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

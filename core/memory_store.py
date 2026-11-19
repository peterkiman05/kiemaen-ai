"""Per-account rolling conversation history stored in the configured DATABASE_URL.

The browser account/session database remains separate. This store adds only
conversation_messages and never migrates or rewrites existing account data.
"""
from __future__ import annotations

import asyncio
import logging
import os
import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, Index, Integer, String, Text, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
logger = logging.getLogger(__name__)

Base = declarative_base()


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("ix_conversation_messages_user_key_id", "user_key", "id"),
    )

    id = Column(Integer, primary_key=True)
    user_key = Column(String(160), nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


def normalise_database_url(raw_url: str) -> tuple[str, dict]:
    """Convert common Render/Aiven PostgreSQL URLs to SQLAlchemy asyncpg URLs."""
    parsed = urlsplit((raw_url or "").strip())
    scheme = parsed.scheme
    if scheme in {"postgres", "postgresql", "postgresql+psycopg2"}:
        scheme = "postgresql+asyncpg"
    elif scheme == "sqlite":
        scheme = "sqlite+aiosqlite"

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    retained = []
    sslmode = None
    sslrootcert = None
    for key, value in query_items:
        if key == "sslmode":
            sslmode = value.lower()
        elif key == "sslrootcert":
            sslrootcert = value
        else:
            retained.append((key, value))

    connect_args = {}
    if scheme == "postgresql+asyncpg":
        if sslmode == "disable":
            connect_args["ssl"] = False
        elif sslmode in {"allow", "prefer", "require"}:
            connect_args["ssl"] = sslmode
        elif sslmode in {"verify-ca", "verify-full"}:
            context = ssl.create_default_context(cafile=sslrootcert or None)
            if sslmode == "verify-ca":
                context.check_hostname = False
            connect_args["ssl"] = context
        elif sslrootcert:
            connect_args["ssl"] = ssl.create_default_context(cafile=sslrootcert)

    if scheme.startswith("sqlite"):
        normalised = f"{scheme}://{parsed.path}"
        if retained:
            normalised += "?" + urlencode(retained)
    else:
        normalised = urlunsplit((
            scheme,
            parsed.netloc,
            parsed.path,
            urlencode(retained),
            parsed.fragment,
        ))
    return normalised, connect_args


class ConversationMemoryStore:
    """Async conversation store; unavailable storage never blocks ordinary chat."""

    MAX_STORED_MESSAGES = 200
    MAX_MESSAGE_CHARS = 12000

    def __init__(self, database_url: str | None):
        self.configured = bool((database_url or "").strip())
        self.engine = None
        self.sessions = None
        self._ready = False
        self._status = "not_configured" if not self.configured else "unavailable"
        self._init_lock = asyncio.Lock()

        if self.configured:
            try:
                url, connect_args = normalise_database_url(database_url or "")
                options = {"echo": False, "pool_pre_ping": True}
                if connect_args:
                    options["connect_args"] = connect_args
                self.engine = create_async_engine(url, **options)
                self.sessions = sessionmaker(
                    self.engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )
            except Exception:
                logger.exception("Could not configure Kiemaen conversation memory database")
                self._status = "unavailable"

    @property
    def status(self) -> str:
        return self._status

    async def initialize(self) -> bool:
        if not self.configured or self.engine is None:
            return False
        if self._ready:
            return True

        async with self._init_lock:
            if self._ready:
                return True
            try:
                async with self.engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                self._ready = True
                self._status = "connected"
                return True
            except Exception:
                self._status = "unavailable"
                logger.exception("Kiemaen conversation memory database is unavailable")
                return False

    async def get_recent_history(self, user_key: str, limit: int = 12) -> list[dict[str, str]]:
        key = (user_key or "").strip()
        if not key or not await self.initialize() or self.sessions is None:
            return []
        try:
            async with self.sessions() as session:
                result = await session.execute(
                    select(ConversationMessage)
                    .where(ConversationMessage.user_key == key)
                    .order_by(ConversationMessage.id.desc())
                    .limit(max(1, min(int(limit), 24)))
                )
                rows = list(result.scalars().all())
                rows.reverse()
                return [
                    {"role": row.role, "content": row.content}
                    for row in rows
                    if row.role in {"user", "assistant"}
                ]
        except Exception:
            self._status = "unavailable"
            logger.exception("Could not load Kiemaen conversation history")
            return []

    async def save_turn(self, user_key: str, user_content: str, assistant_content: str) -> bool:
        key = (user_key or "").strip()
        user_text = (user_content or "").strip()[: self.MAX_MESSAGE_CHARS]
        assistant_text = (assistant_content or "").strip()[: self.MAX_MESSAGE_CHARS]
        if not key or not user_text or not assistant_text:
            return False
        if not await self.initialize() or self.sessions is None:
            return False

        try:
            async with self.sessions() as session:
                session.add_all([
                    ConversationMessage(user_key=key, role="user", content=user_text),
                    ConversationMessage(user_key=key, role="assistant", content=assistant_text),
                ])
                await session.flush()

                recent_ids = (
                    select(ConversationMessage.id)
                    .where(ConversationMessage.user_key == key)
                    .order_by(ConversationMessage.id.desc())
                    .limit(self.MAX_STORED_MESSAGES)
                )
                await session.execute(
                    delete(ConversationMessage).where(
                        ConversationMessage.user_key == key,
                        ~ConversationMessage.id.in_(recent_ids),
                    )
                )
                await session.commit()
            self._status = "connected"
            return True
        except Exception:
            self._status = "unavailable"
            logger.exception("Could not save Kiemaen conversation turn")
            return False

    async def clear_history(self, user_key: str) -> int:
        key = (user_key or "").strip()
        if not key or not await self.initialize() or self.sessions is None:
            return 0
        try:
            async with self.sessions() as session:
                result = await session.execute(
                    delete(ConversationMessage).where(ConversationMessage.user_key == key)
                )
                await session.commit()
                self._status = "connected"
                return int(result.rowcount or 0)
        except Exception:
            self._status = "unavailable"
            logger.exception("Could not clear Kiemaen conversation history")
            return 0

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
        self._ready = False


conversation_store = ConversationMemoryStore(os.getenv("DATABASE_URL", ""))


async def init_memory_store() -> bool:
    return await conversation_store.initialize()


async def close_memory_store() -> None:
    await conversation_store.close()


async def get_conversation_history(user_key: str, limit: int = 12) -> list[dict[str, str]]:
    return await conversation_store.get_recent_history(user_key, limit)


async def save_conversation_turn(user_key: str, user_content: str, assistant_content: str) -> bool:
    return await conversation_store.save_turn(user_key, user_content, assistant_content)


async def clear_conversation_history(user_key: str) -> int:
    return await conversation_store.clear_history(user_key)


def memory_store_status() -> str:
    return conversation_store.status


def memory_store_configured() -> bool:
    return conversation_store.configured

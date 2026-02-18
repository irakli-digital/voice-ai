"""Postgres conversation logging for Voice AI sessions."""

import os
import time
import logging

import asyncpg

logger = logging.getLogger("voice-ai-db")

DATABASE_URL = os.environ.get("DATABASE_URL")


class ConversationDB:
    def __init__(self):
        self._pool: asyncpg.Pool | None = None

    async def init(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set — conversation logging disabled")
            return
        self._pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at DOUBLE PRECISION NOT NULL,
                    ended_at DOUBLE PRECISION,
                    metadata TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id),
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL,
                    latency_ms DOUBLE PRECISION
                )
            """)
        logger.info("Database initialized (Postgres)")

    async def start_session(self, session_id: str, metadata: str = ""):
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO sessions (session_id, started_at, metadata)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (session_id) DO NOTHING""",
                session_id, time.time(), metadata,
            )

    async def end_session(self, session_id: str):
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE sessions SET ended_at = $1 WHERE session_id = $2",
                time.time(), session_id,
            )

    async def log_message(
        self, session_id: str, role: str, text: str, latency_ms: float | None = None
    ):
        if not self._pool:
            return
        await self.start_session(session_id)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO messages (session_id, role, text, created_at, latency_ms)
                   VALUES ($1, $2, $3, $4, $5)""",
                session_id, role, text, time.time(), latency_ms,
            )
        logger.debug(f"[{session_id}] {role}: {text[:80]}...")

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

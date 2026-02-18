"""SQLite conversation logging for Voice AI sessions."""

import os
import time
import logging
import aiosqlite

logger = logging.getLogger("voice-ai-db")

DB_PATH = os.path.join(os.path.dirname(__file__), "conversations.db")


class ConversationDB:
    def __init__(self, db_path: str = DB_PATH):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                started_at REAL NOT NULL,
                ended_at REAL,
                metadata TEXT
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at REAL NOT NULL,
                latency_ms REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        await self._db.commit()
        logger.info(f"Database initialized at {self._db_path}")

    async def start_session(self, session_id: str, metadata: str = ""):
        if not self._db:
            return
        await self._db.execute(
            "INSERT OR IGNORE INTO sessions (session_id, started_at, metadata) VALUES (?, ?, ?)",
            (session_id, time.time(), metadata),
        )
        await self._db.commit()

    async def end_session(self, session_id: str):
        if not self._db:
            return
        await self._db.execute(
            "UPDATE sessions SET ended_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        await self._db.commit()

    async def log_message(
        self, session_id: str, role: str, text: str, latency_ms: float | None = None
    ):
        if not self._db:
            return
        # Ensure session exists
        await self.start_session(session_id)
        await self._db.execute(
            "INSERT INTO messages (session_id, role, text, created_at, latency_ms) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, text, time.time(), latency_ms),
        )
        await self._db.commit()
        logger.debug(f"[{session_id}] {role}: {text[:80]}...")

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import settings


class DbPool:
    """Minimal async connection pool based on asyncio.Queue (no extra dependencies)."""

    def __init__(self, conninfo: str, min_size: int = 1, max_size: int = 5) -> None:
        self._conninfo = conninfo
        self._max_size = max_size
        self._queue: asyncio.Queue[psycopg.AsyncConnection] = asyncio.Queue(maxsize=max_size)
        self._size = 0
        self._lock = asyncio.Lock()

    async def _create(self) -> psycopg.AsyncConnection:
        async with self._lock:
            self._size += 1
        try:
            return await psycopg.AsyncConnection.connect(
                self._conninfo,
                autocommit=True,
                row_factory=dict_row,
            )
        except Exception:
            async with self._lock:
                self._size -= 1
            raise

    async def acquire(self) -> psycopg.AsyncConnection:
        if self._queue.empty() and self._size < self._max_size:
            return await self._create()
        return await self._queue.get()

    def release(self, conn: psycopg.AsyncConnection) -> None:
        try:
            self._queue.put_nowait(conn)
        except asyncio.QueueFull:  # pragma: no cover - pool full safety path
            self._schedule_close(conn)

    def _schedule_close(self, conn: psycopg.AsyncConnection) -> None:
        async def _closer() -> None:
            async with self._lock:
                self._size -= 1
            await conn.close()

        asyncio.create_task(_closer())

    async def close(self) -> None:
        while not self._queue.empty():
            conn = self._queue.get_nowait()
            await conn.close()
        async with self._lock:
            self._size = 0

    @asynccontextmanager
    async def cursor(self) -> Any:
        conn = await self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)


pool = DbPool(settings.database_url)


async def fetch_all(sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    async with pool.cursor() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()


async def fetch_one(sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    rows = await fetch_all(sql, params)
    return rows[0] if rows else None


async def execute(sql: str, params: tuple[Any, ...] | None = None) -> None:
    async with pool.cursor() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)


async def close_pool() -> None:
    await pool.close()

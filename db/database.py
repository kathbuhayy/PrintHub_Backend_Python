import asyncpg
from typing import Any

_pool: asyncpg.Pool | None = None


async def create_pool(dsn: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10, statement_cache_size=0)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool


async def fetch_one(query: str, *args) -> dict | None:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_all(query: str, *args) -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def execute(query: str, *args) -> str:
    async with get_pool().acquire() as conn:
        return await conn.execute(query, *args)


async def fetch_val(query: str, *args) -> Any:
    async with get_pool().acquire() as conn:
        return await conn.fetchval(query, *args)

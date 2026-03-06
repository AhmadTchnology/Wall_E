import json
import asyncpg
from config import get_settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Create the connection pool (called at app startup)."""
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
    )

    # Register pgvector type so asyncpg can handle vector columns
    async with _pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    return _pool


async def close_pool() -> None:
    """Drain and close the pool (called at app shutdown)."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def search_similar(
    embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Cosine-similarity search against the documents table.
    Returns the top_k closest rows ordered by distance (ascending).
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized")

    settings = get_settings()

    # Format vector as pgvector literal: '[0.1,0.2,...]'
    vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"

    query = f"""
        SELECT
            {settings.content_column}  AS content,
            1 - ({settings.embedding_column} <=> $1::vector) AS score,
            {settings.metadata_column}  AS metadata
        FROM {settings.table_name}
        ORDER BY {settings.embedding_column} <=> $1::vector
        LIMIT $2
    """

    async with _pool.acquire() as conn:
        rows = await conn.fetch(query, vec_literal, top_k)

    results = []
    for row in rows:
        meta = row["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {"raw": meta}
        elif meta is None:
            meta = {}

        results.append({
            "content": row["content"],
            "score": float(row["score"]),
            "metadata": meta,
        })

    return results

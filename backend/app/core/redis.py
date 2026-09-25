# app/core/redis.py
from redis.asyncio import Redis, ConnectionPool
from contextlib import asynccontextmanager
from app.config import settings


class RedisClient:
    def __init__(self):
        self.pool: ConnectionPool | None = None
        self.client: Redis | None = None

    async def connect(self):
        self.pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=50,
            decode_responses=True,
        )
        self.client = Redis(connection_pool=self.pool)

    async def disconnect(self):
        if self.client:
            await self.client.aclose()
        if self.pool:
            await self.pool.aclose()

    def get_client(self) -> Redis:
        return self.client

    # ---- thin async wrappers (used by session_store) ----
    async def get(self, key: str):
        if self.client is None:
            return None
        return await self.client.get(key)

    async def set(self, key: str, value, ex: int | None = None):
        if self.client is None:
            raise RuntimeError("Redis not connected")
        return await self.client.set(key, value, ex=ex)

    async def delete(self, *keys: str):
        if self.client is None:
            return 0
        return await self.client.delete(*keys)

    async def expire(self, key: str, seconds: int):
        if self.client is None:
            return False
        return await self.client.expire(key, seconds)


redis_client = RedisClient()


@asynccontextmanager
async def lifespan(app):
    await redis_client.connect()
    yield
    await redis_client.disconnect()
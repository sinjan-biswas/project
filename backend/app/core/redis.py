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

redis_client = RedisClient()

@asynccontextmanager
async def lifespan(app):
    await redis_client.connect()
    yield
    await redis_client.disconnect()
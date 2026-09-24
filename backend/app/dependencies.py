# app/dependencies.py
from fastapi import Depends
from redis.asyncio import Redis
from app.core.redis import redis_client

async def get_redis() -> Redis:
    return redis_client.get_client()
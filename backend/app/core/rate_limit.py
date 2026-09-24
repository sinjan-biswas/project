# app/core/rate_limit.py
from fastapi import Request, HTTPException
from redis.asyncio import Redis

async def rate_limit(
    request: Request,
    redis: Redis,
    max_requests: int = 30,
    window_seconds: int = 60,
):
    """Simple sliding-window rate limiter per client IP."""
    client_ip = request.client.host
    key = f"ratelimit:{client_ip}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    if current > max_requests:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
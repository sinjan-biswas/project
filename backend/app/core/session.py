# app/core/session.py
import json
from datetime import datetime, timedelta
from redis.asyncio import Redis
from app.models.session import Session
from app.config import settings

SESSION_KEY_PREFIX = "liveness:session:"

class SessionStore:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _key(self, session_id: str) -> str:
        return f"{SESSION_KEY_PREFIX}{session_id}"

    async def create(self, session: Session) -> None:
        await self.redis.setex(
            self._key(session.session_id),
            settings.SESSION_TTL_SECONDS,
            session.model_dump_json(),
        )

    async def get(self, session_id: str) -> Session | None:
        data = await self.redis.get(self._key(session_id))
        if not data:
            return None
        return Session.model_validate_json(data)

    async def update(self, session: Session) -> None:
        session.updated_at = datetime.utcnow()
        await self.redis.setex(
            self._key(session.session_id),
            settings.SESSION_TTL_SECONDS,  # sliding TTL
            session.model_dump_json(),
        )

    async def delete(self, session_id: str) -> None:
        await self.redis.delete(self._key(session_id))
import json
import time
import uuid
import shutil
from pathlib import Path
from typing import Optional

from app.core.redis import redis_client
from app.schemas.session import ScreeningSession

SESSION_ROOT = Path(__file__).resolve().parent.parent.parent / ".sessions"
SESSION_ROOT.mkdir(exist_ok=True)

DEFAULT_TTL_SECONDS = 30 * 60
REDIS_PREFIX = "screening:session:"


class ScreeningSessionStore:
    """
    Screening-flow session storage.

    - Metadata (session + file refs) lives in Redis with a sliding TTL.
    - Raw bytes (original + enhanced images) live on disk under .sessions/{sid}/.
    - Distinct from app/core/session.py (liveness sessions, prefix liveness:session:).
    """

    # ---- lifecycle ----------------------------------------------------

    async def create(self, ttl: int = DEFAULT_TTL_SECONDS) -> ScreeningSession:
        sid = f"sess_{uuid.uuid4().hex[:12]}"
        now = time.time()
        session = ScreeningSession(
            session_id=sid,
            created_at=now,
            expires_at=now + ttl,
        )
        (SESSION_ROOT / sid).mkdir(parents=True, exist_ok=True)
        await self._save(session, ttl)
        return session

    async def get(self, sid: str) -> Optional[ScreeningSession]:
        raw = await redis_client.get(REDIS_PREFIX + sid)
        if not raw:
            return None
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode()
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return ScreeningSession(**data)

    async def save(self, session: ScreeningSession,
                   ttl: int = DEFAULT_TTL_SECONDS) -> None:
        session.expires_at = time.time() + ttl
        await self._save(session, ttl)

    async def delete(self, sid: str) -> None:
        try:
            await redis_client.delete(REDIS_PREFIX + sid)
        except Exception:
            pass
        shutil.rmtree(SESSION_ROOT / sid, ignore_errors=True)

    async def _save(self, session: ScreeningSession, ttl: int) -> None:
        await redis_client.set(
            REDIS_PREFIX + session.session_id,
            session.model_dump_json(),
            ex=ttl,
        )

    # ---- filesystem ---------------------------------------------------

    def session_dir(self, sid: str) -> Path:
        d = SESSION_ROOT / sid
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_file(self, sid: str, index: int, suffix: str, data: bytes) -> str:
        path = self.session_dir(sid) / f"orig_{index}{suffix or '.jpg'}"
        path.write_bytes(data)
        return str(path)

    def write_enhanced(self, sid: str, index: int, data: bytes) -> str:
        path = self.session_dir(sid) / f"enhanced_{index}.jpg"
        path.write_bytes(data)
        return str(path)

    # ---- garbage collection ------------------------------------------

    def sweep_stale(self, max_age_seconds: int = 2 * DEFAULT_TTL_SECONDS) -> int:
        """Delete on-disk session dirs older than max_age_seconds."""
        now = time.time()
        removed = 0
        for d in SESSION_ROOT.iterdir():
            if not d.is_dir():
                continue
            try:
                if now - d.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
            except OSError:
                pass
        return removed


screening_session_store = ScreeningSessionStore()
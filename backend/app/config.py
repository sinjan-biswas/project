# app/config.py
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    SESSION_TTL_SECONDS: int = 90  # 60-90s per spec
    BLINK_TARGET_MIN: int = 2
    BLINK_TARGET_MAX: int = 3
    EAR_THRESHOLD: float = 0.15
    EAR_CONSEC_FRAMES: int = 3
    FACE_MATCH_THRESHOLD: float = 0.6
    PAD_MODEL_PATH: str = "models/anti_spoof.onnx"
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"

settings = Settings()
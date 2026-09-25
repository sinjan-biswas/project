from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal


class SessionFileMeta(BaseModel):
    index: int
    filename: str
    disk_path: str                        # original bytes on disk
    enhanced_path: Optional[str] = None   # enhanced bytes on disk (if any)
    quality: Dict[str, Any] = Field(default_factory=dict)
    doc_type: Optional[str] = None
    doc_confidence: float = 0.0
    blocked: bool = False
    block_reason: Optional[str] = None


class ScreeningSession(BaseModel):
    session_id: str
    created_at: float
    expires_at: float
    stage: Literal["validated", "ocr_done", "final"] = "validated"
    files: List[SessionFileMeta] = Field(default_factory=list)
    ocr_results: Optional[Dict[str, Any]] = None
    final_result: Optional[Dict[str, Any]] = None
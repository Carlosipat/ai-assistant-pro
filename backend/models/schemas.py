from pydantic import BaseModel, Field
from typing import Optional, Literal
import uuid
import time


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: Optional[float] = None


class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stream: bool = False
    max_tokens: int = 512


class ChatResponse(BaseModel):
    response: str
    session_id: str
    message_count: int
    timestamp: float = Field(default_factory=time.time)


class ToolRunRequest(BaseModel):
    tool_name: str
    params: dict = {}


class SessionInfo(BaseModel):
    session_id: str
    message_count: int
    created_at: Optional[float]
    updated_at: Optional[float]
    preview: str

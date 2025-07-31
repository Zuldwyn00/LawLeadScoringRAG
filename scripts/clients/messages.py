from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from enum import Enum

class MessageType(str, Enum):
    SYSTEM = "system"       # Intructions to the Ai
    USER = "user"           # Human messages  
    ASSISTANT = "assistant" # Responses from the AI
    TOOL = "tool"           # Responses from tools


class BaseMessage(BaseModel):
    content: str = Field(..., description="Message content")
    type: MessageType = Field(..., description="Message type")

    @field_validator('content')
    @classmethod
    def content_not_empty(cls, value):
        if not value or value.strip():
            raise ValueError("Message content cannot be empty")
        return value.strip()


class SystemMessage(BaseMessage):
    type = MessageType = Field(default=MessageType.SYSTEM, description='System message')

    @field_validator
    @classmethod
    def validate_system_content():
        pass
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ParseRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Share link or share text.")
    mode: Literal["auto", "native", "third_party"] = Field(
        default="auto",
        description="解析方式: auto=自动(先自有解析，失败时尝试第三方), native=仅自有解析, third_party=仅第三方API",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("分享文案或链接不能为空。")
        return cleaned

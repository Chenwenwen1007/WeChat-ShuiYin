from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ParsePayload(BaseModel):
    platform: str
    platform_label: str
    title: str
    author: str = ""
    cover_url: str = ""
    video_url: str
    preview_cover_url: str = ""
    preview_video_url: str
    download_url: str
    watermark_video_url: str = ""
    watermark_preview_video_url: str = ""
    watermark_download_url: str = ""
    no_watermark_video_url: str = ""
    no_watermark_preview_video_url: str = ""
    no_watermark_download_url: str = ""
    no_watermark_note: str = ""
    raw_url: str
    resolved_url: str
    # 新增：解析来源标识
    parse_source: Literal["native", "third_party", "fallback"] = "native"
    # 新增：无水印验证状态
    no_watermark_verified: bool = False


class DirectLinkPayload(BaseModel):
    title: str
    source_url: str
    preview_url: str
    download_url: str


class DownloadPayload(BaseModel):
    platforms: List[str]
    notes: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    detail: Optional[ErrorPayload] = Field(default=None)

from __future__ import annotations

import base64
import json
from urllib.parse import quote

import httpx
from fastapi import Request

from server.config import get_settings
from server.parsers.base import ParsedVideo
from server.utils.exceptions import ParseError
from server.utils.http_client import stream_remote_file


class DownloadService:
    def _base_url(self, request: Request) -> str:
        settings = get_settings()
        request_base = str(request.base_url).rstrip("/")
        return settings.app_base_url.rstrip("/") or request_base

    def build_download_url(self, video: ParsedVideo, request: Request) -> str:
        return self.build_download_url_from_resource(video.title, video.video_url, request)

    def build_preview_video_url(self, video: ParsedVideo, request: Request) -> str:
        return self.build_media_url(video.title, video.video_url, "video", request)

    def build_preview_cover_url(self, video: ParsedVideo, request: Request) -> str:
        if not video.cover_url:
            return ""
        return self.build_media_url(video.title, video.cover_url, "image", request)

    def build_download_url_from_resource(self, title: str, resource_url: str, request: Request) -> str:
        if not resource_url:
            return ""
        token = self.encode_token(
            {
                "title": title,
                "resource_url": resource_url,
                "resource_type": "video",
            }
        )
        return f"{self._base_url(request)}/api/download?token={token}"

    def build_media_url(self, title: str, resource_url: str, resource_type: str, request: Request) -> str:
        if not resource_url:
            return ""
        token = self.encode_token(
            {
                "title": title,
                "resource_url": resource_url,
                "resource_type": resource_type,
            }
        )
        return f"{self._base_url(request)}/api/media?token={token}"

    def encode_token(self, payload: dict) -> str:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8")

    def decode_token(self, token: str) -> dict:
        try:
            raw = base64.urlsafe_b64decode(token.encode("utf-8"))
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ParseError(
                code="INVALID_TOKEN",
                message="访问令牌无效，请重新解析视频。",
                status_code=422,
            ) from exc

        if not payload.get("resource_url"):
            raise ParseError(
                code="INVALID_TOKEN",
                message="访问令牌缺少资源地址，请重新解析视频。",
                status_code=422,
            )
        return payload

    async def build_stream(self, payload: dict) -> tuple:
        try:
            stream, response = await stream_remote_file(payload["resource_url"])
        except httpx.HTTPStatusError as exc:
            raise ParseError(
                code="RESOURCE_FETCH_FAILED",
                message="视频资源拉取失败，可能地址已过期，请重新解析后再试。",
                status_code=502,
                details={"status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise ParseError(
                code="RESOURCE_FETCH_FAILED",
                message="下载视频时网络异常，请稍后再试。",
                status_code=502,
            ) from exc

        filename = quote(f'{payload.get("title", "video")}.mp4')
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
        content_length = response.headers.get("content-length")
        if content_length:
            headers["Content-Length"] = content_length
        media_type = response.headers.get("content-type", "video/mp4").split(";")[0]
        return stream, headers, media_type

    async def build_media_stream(self, payload: dict) -> tuple:
        try:
            stream, response = await stream_remote_file(payload["resource_url"])
        except httpx.HTTPStatusError as exc:
            raise ParseError(
                code="RESOURCE_FETCH_FAILED",
                message="预览资源拉取失败，可能地址已过期，请重新解析后再试。",
                status_code=502,
                details={"status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise ParseError(
                code="RESOURCE_FETCH_FAILED",
                message="预览资源请求异常，请稍后再试。",
                status_code=502,
            ) from exc

        headers = {}
        content_length = response.headers.get("content-length")
        if content_length:
            headers["Content-Length"] = content_length

        default_type = "image/jpeg" if payload.get("resource_type") == "image" else "video/mp4"
        media_type = response.headers.get("content-type", default_type).split(";")[0]
        return stream, headers, media_type

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup

from server.utils.exceptions import ParseError
from server.utils.http_client import build_client
from server.utils.text_extractor import clean_title, match_first, unescape_text


@dataclass
class ParsedVideo:
    platform: str
    platform_label: str
    title: str
    author: str
    cover_url: str
    video_url: str
    raw_url: str
    resolved_url: str
    watermark_video_url: str = ""
    no_watermark_video_url: str = ""


class BaseParser:
    platform_name = ""
    platform_label = ""

    async def fetch_html(self, url: str, headers: dict | None = None) -> str:
        async with build_client() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    def extract_meta(self, html: str, property_name: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        node = soup.find("meta", attrs={"property": property_name}) or soup.find(
            "meta", attrs={"name": property_name}
        )
        if not node:
            return ""
        return (node.get("content") or "").strip()

    def pick_best_url(self, html: str, patterns: Iterable[str], fallback_meta: tuple[str, ...] = ()) -> str:
        url = match_first(html, list(patterns))
        if url:
            return unescape_text(url)

        for property_name in fallback_meta:
            url = self.extract_meta(html, property_name)
            if url:
                return unescape_text(url)

        return ""

    def ensure_result(
        self,
        video_url: str,
        raw_url: str,
        resolved_url: str,
        title: str,
        author: str,
        cover_url: str,
        watermark_video_url: str = "",
        no_watermark_video_url: str = "",
    ):
        primary_video_url = (video_url or no_watermark_video_url or watermark_video_url).strip()
        if not primary_video_url:
            raise ParseError(
                code="VIDEO_NOT_FOUND",
                message=f"{self.platform_label} 页面结构已变化，暂时未提取到可播放视频地址。",
                status_code=422,
                details={"resolved_url": resolved_url},
            )

        return ParsedVideo(
            platform=self.platform_name,
            platform_label=self.platform_label,
            title=clean_title(title or f"{self.platform_label} 视频"),
            author=author.strip(),
            cover_url=cover_url.strip(),
            video_url=primary_video_url,
            raw_url=raw_url,
            resolved_url=resolved_url,
            watermark_video_url=(watermark_video_url or primary_video_url).strip(),
            no_watermark_video_url=(no_watermark_video_url or primary_video_url).strip(),
        )

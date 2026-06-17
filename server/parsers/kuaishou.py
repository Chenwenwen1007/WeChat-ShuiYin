import logging
import re

from server.parsers.base import BaseParser, ParsedVideo
from server.utils.exceptions import ParseError
from server.utils.text_extractor import match_first

logger = logging.getLogger(__name__)


class KuaishouParser(BaseParser):
    """快手视频解析器，区分有水印和无水印地址"""
    platform_name = "kuaishou"
    platform_label = "快手"

    async def parse(self, raw_url: str, resolved_url: str) -> ParsedVideo:
        """
        解析快手视频，提取有水印和无水印地址

        快手页面中：
        - srcNoMark: 无水印视频地址
        - photoUrl: 有水印视频地址
        """
        # 快手需要PC端UA才能获取完整页面数据
        html = await self.fetch_html(resolved_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Referer": "https://www.kuaishou.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

        title = self.extract_meta(html, "og:title") or match_first(
            html,
            [
                r'"caption"\s*:\s*"([^"]+)"',
                r'"title"\s*:\s*"([^"]+)"',
            ],
        )
        author = match_first(
            html,
            [
                r'"authorName"\s*:\s*"([^"]+)"',
                r'"user_name"\s*:\s*"([^"]+)"',
                r'"name"\s*:\s*"([^"]+)"',
            ],
        )
        cover_url = self.extract_meta(html, "og:image") or match_first(
            html,
            [
                r'"poster"\s*:\s*"([^"]+)"',
                r'"coverUrl"\s*:\s*"([^"]+)"',
            ],
        )

        # 无水印地址：优先 srcNoMark
        no_watermark_url = match_first(
            html,
            [
                r'"srcNoMark"\s*:\s*"([^"]+)"',
                r'"noMarkUrl"\s*:\s*"([^"]+)"',
            ],
        )

        # 有水印地址：photoUrl 或 mainMvUrls
        watermark_url = match_first(
            html,
            [
                r'"photoUrl"\s*:\s*"([^"]+)"',
                r'"mainMvUrls"\s*:\s*\[\s*"([^"]+)"',
                r'"hevc"\s*:\s*\{.*?"url"\s*:\s*"([^"]+)"',
            ],
        )

        # 如果没有找到无水印地址，尝试从所有视频URL中选取
        if not no_watermark_url:
            no_watermark_url = self.pick_best_url(
                html,
                patterns=[
                    r'"srcNoMark"\s*:\s*"([^"]+)"',
                    r'"photoUrl"\s*:\s*"([^"]+)"',
                    r'"mainMvUrls"\s*:\s*\[\s*"([^"]+)"',
                    r'"hevc"\s*:\s*\{.*?"url"\s*:\s*"([^"]+)"',
                ],
                fallback_meta=("og:video", "twitter:player:stream"),
            )

        # 如果没有找到有水印地址，使用无水印地址作为兜底
        if not watermark_url:
            watermark_url = no_watermark_url

        # 确保至少有一个可用地址
        primary_video_url = no_watermark_url or watermark_url
        if not primary_video_url:
            raise ParseError(
                code="VIDEO_NOT_FOUND",
                message="快手页面结构已变化，暂时未提取到可播放视频地址。",
                status_code=422,
                details={"resolved_url": resolved_url},
            )

        return ParsedVideo(
            platform=self.platform_name,
            platform_label=self.platform_label,
            title=title or "快手视频",
            author=author.strip(),
            cover_url=cover_url.strip(),
            video_url=primary_video_url,
            raw_url=raw_url,
            resolved_url=resolved_url,
            watermark_video_url=watermark_url.strip(),
            no_watermark_video_url=no_watermark_url.strip(),
        )

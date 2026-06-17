import logging
import re

from server.parsers.base import BaseParser, ParsedVideo
from server.utils.exceptions import ParseError
from server.utils.text_extractor import match_first

logger = logging.getLogger(__name__)


class XiaoHongShuParser(BaseParser):
    """小红书视频解析器，提取无水印视频地址"""
    platform_name = "xiaohongshu"
    platform_label = "小红书"

    async def parse(self, raw_url: str, resolved_url: str) -> ParsedVideo:
        """
        解析小红书视频，提取无水印地址

        小红书页面中：
        - masterUrl: 无水印视频地址（原始上传视频）
        - backupUrls: 备用视频地址列表
        - 小红书视频通常没有平台水印，masterUrl即为无水印版本
        """
        # 小红书需要PC端UA和Cookie才能获取完整页面数据
        html = await self.fetch_html(resolved_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

        title = self.extract_meta(html, "og:title") or match_first(
            html,
            [
                r'"title"\s*:\s*"([^"]+)"',
                r'"noteTitle"\s*:\s*"([^"]+)"',
            ],
        )
        author = match_first(
            html,
            [
                r'"nickname"\s*:\s*"([^"]+)"',
                r'"userName"\s*:\s*"([^"]+)"',
            ],
        )
        cover_url = self.extract_meta(html, "og:image") or match_first(
            html,
            [
                r'"imageList"\s*:\s*\[\s*\{.*?"urlDefault"\s*:\s*"([^"]+)"',
                r'"poster"\s*:\s*"([^"]+)"',
            ],
        )

        # 无水印地址：masterUrl 是原始视频地址，通常无平台水印
        no_watermark_url = match_first(
            html,
            [
                r'"masterUrl"\s*:\s*"([^"]+)"',
                r'"h264"\s*:\s*\[\s*\{[^}]*?"masterUrl"\s*:\s*"([^"]+)"',
                r'"originVideoKey"\s*:\s*"([^"]+)"',
            ],
        )

        # 如果 masterUrl 未找到，尝试 backupUrls 和其他字段
        if not no_watermark_url:
            no_watermark_url = match_first(
                html,
                [
                    r'"backupUrls"\s*:\s*\[\s*"([^"]+)"',
                    r'"videoUrl"\s*:\s*"([^"]+)"',
                    r'"url"\s*:\s*"(https?://[^"]*video[^"]*)"',
                ],
            )

        # 有水印地址：小红书一般没有单独的有水印版本，使用 meta og:video 兜底
        watermark_url = self.extract_meta(html, "og:video") or self.extract_meta(html, "twitter:player:stream")

        # 如果没有找到有水印地址，使用无水印地址
        if not watermark_url:
            watermark_url = no_watermark_url

        # 确保至少有一个可用地址
        if not no_watermark_url:
            # 最后尝试从 meta 标签提取
            no_watermark_url = self.pick_best_url(
                html,
                patterns=[
                    r'"masterUrl"\s*:\s*"([^"]+)"',
                    r'"backupUrls"\s*:\s*\[\s*"([^"]+)"',
                    r'"videoUrl"\s*:\s*"([^"]+)"',
                ],
                fallback_meta=("og:video", "twitter:player:stream"),
            )
            watermark_url = watermark_url or no_watermark_url

        if not no_watermark_url:
            raise ParseError(
                code="VIDEO_NOT_FOUND",
                message="小红书页面结构已变化，暂时未提取到可播放视频地址。",
                status_code=422,
                details={"resolved_url": resolved_url},
            )

        return ParsedVideo(
            platform=self.platform_name,
            platform_label=self.platform_label,
            title=title or "小红书视频",
            author=author.strip(),
            cover_url=cover_url.strip(),
            video_url=no_watermark_url,
            raw_url=raw_url,
            resolved_url=resolved_url,
            watermark_video_url=watermark_url.strip(),
            no_watermark_video_url=no_watermark_url.strip(),
        )

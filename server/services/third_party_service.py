import logging
from typing import Any

import httpx

from server.config import get_settings
from server.parsers.base import ParsedVideo
from server.utils.exceptions import ParseError
from server.utils.http_client import build_client

logger = logging.getLogger(__name__)


class ThirdPartyService:
    """
    第三方去水印API服务
    当自有解析失败或用户主动选择时，调用外部去水印API获取视频
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_configured(self) -> bool:
        """检查是否已配置第三方API"""
        return bool(self.settings.third_party_api_url) or bool(self.settings.bugpk_api_enabled)

    async def parse(self, source_url: str) -> ParsedVideo | None:
        """
        调用第三方API解析视频

        Args:
            source_url: 原始分享链接

        Returns:
            ParsedVideo: 解析结果，若未配置或解析失败则返回None
        """
        if not self.is_configured():
            logger.info("第三方API未配置，跳过")
            return None

        try:
            # 优先使用自定义配置的API
            if self.settings.third_party_api_url:
                result = await self._call_custom_api(source_url)
            else:
                # 默认使用bugpk.com免费API
                result = await self._call_bugpk_api(source_url)
            if result:
                logger.info("第三方API解析成功")
            return result
        except Exception as exc:
            logger.warning("第三方API解析失败: %s", exc)
            return None

    async def _call_bugpk_api(self, source_url: str) -> ParsedVideo | None:
        """
        调用bugpk.com免费API
        """
        async with build_client(timeout=30.0) as client:
            response = await client.get(
                "https://api.bugpk.com/api/douyin",
                params={"url": source_url},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                    "Referer": "https://api.bugpk.com/doc-douyin.html",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            response.raise_for_status()
            data = response.json()

        return self._adapt_bugpk_response(data, source_url)

    def _adapt_response(self, data: dict[str, Any], source_url: str) -> ParsedVideo | None:
        """
        将第三方API响应转换为ParsedVideo
        支持两种常见格式：
        1. {data: {video_url, title, author, cover_url, ...}}
        2. {video_url, title, author, cover_url, ...}
        """
        # 尝试从嵌套的data字段或顶层提取
        result = data.get("data") if isinstance(data.get("data"), dict) else data

        if not isinstance(result, dict):
            logger.warning("第三方API返回格式异常")
            return None

        video_url = result.get("video_url") or result.get("url") or ""
        if not video_url:
            logger.warning("第三方API返回中未找到视频地址")
            return None

        title = result.get("title", "")
        author = result.get("author", "")
        cover_url = result.get("cover_url") or result.get("cover", "")

        return ParsedVideo(
            platform="douyin",
            platform_label="抖音",
            title=title or "抖音视频",
            author=author,
            cover_url=cover_url,
            video_url=video_url,
            raw_url=source_url,
            resolved_url=source_url,
            watermark_video_url=video_url,
            no_watermark_video_url=video_url,
        )

    def _adapt_bugpk_response(self, data: dict[str, Any], source_url: str) -> ParsedVideo | None:
        """
        适配bugpk.com API响应格式
        """
        if data.get("code") != 200:
            logger.warning("bugpk API返回错误: %s", data.get("msg"))
            return None

        result = data.get("data")
        if not isinstance(result, dict):
            logger.warning("bugpk API返回格式异常")
            return None

        video_url = result.get("url") or ""
        if not video_url:
            logger.warning("bugpk API返回中未找到视频地址")
            return None

        title = result.get("title", "") or result.get("desc", "")
        author_info = result.get("author", {})
        if isinstance(author_info, dict):
            author = author_info.get("name", "")
        else:
            author = str(author_info) if author_info else ""
        cover_url = result.get("cover", "")

        return ParsedVideo(
            platform="douyin",
            platform_label="抖音",
            title=title or "抖音视频",
            author=author,
            cover_url=cover_url,
            video_url=video_url,
            raw_url=source_url,
            resolved_url=source_url,
            watermark_video_url=video_url,
            no_watermark_video_url=video_url,
        )

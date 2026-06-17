import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from server.config import get_settings
from server.parsers.base import ParsedVideo
from server.utils.exceptions import ParseError
from server.utils.http_client import build_client

logger = logging.getLogger(__name__)

# bugpk.com 各平台API端点配置
BUGPK_API_ENDPOINTS = {
    "douyin": {
        "url": "https://api.bugpk.com/api/douyin",
        "referer": "https://api.bugpk.com/doc-douyin.html",
        "label": "抖音",
    },
    "kuaishou": {
        "url": "https://api.bugpk.com/api/kuaishou",
        "referer": "https://api.bugpk.com/doc-kuaishou.html",
        "label": "快手",
    },
    "xiaohongshu": {
        "url": "https://api.bugpk.com/api/xiaohongshu",
        "referer": "https://api.bugpk.com/doc-xiaohongshu.html",
        "label": "小红书",
    },
}


class ThirdPartyService:
    """
    第三方去水印API服务
    当自有解析失败或用户主动选择时，调用bugpk.com免费API获取无水印视频
    支持抖音、快手、小红书三个平台
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_configured(self) -> bool:
        """检查是否已配置第三方API"""
        return bool(self.settings.third_party_api_url) or bool(self.settings.bugpk_api_enabled)

    def _detect_platform(self, source_url: str) -> str:
        """根据URL检测平台类型"""
        domain = (urlparse(source_url).hostname or "").lower()
        if "douyin" in domain or "iesdouyin" in domain:
            return "douyin"
        if "kuaishou" in domain or "chenzhongtech" in domain or "gifshow" in domain:
            return "kuaishou"
        if "xiaohongshu" in domain or "xhslink" in domain:
            return "xiaohongshu"
        return "douyin"

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
                # 根据平台选择对应的bugpk.com API端点
                platform = self._detect_platform(source_url)
                result = await self._call_bugpk_api(source_url, platform)
            if result:
                logger.info("第三方API解析成功")
            return result
        except Exception as exc:
            logger.warning("第三方API解析失败: %s", exc)
            return None

    async def _call_bugpk_api(self, source_url: str, platform: str = "douyin") -> ParsedVideo | None:
        """
        调用bugpk.com免费API
        根据平台自动选择对应的API端点
        """
        endpoint = BUGPK_API_ENDPOINTS.get(platform, BUGPK_API_ENDPOINTS["douyin"])
        api_url = endpoint["url"]
        referer = endpoint["referer"]
        platform_label = endpoint["label"]

        async with build_client(timeout=30.0) as client:
            response = await client.get(
                api_url,
                params={"url": source_url},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                    "Referer": referer,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            response.raise_for_status()
            data = response.json()

        return self._adapt_bugpk_response(data, source_url, platform, platform_label)

    async def _call_custom_api(self, source_url: str) -> ParsedVideo | None:
        """调用自定义配置的第三方API"""
        async with build_client(timeout=self.settings.third_party_api_timeout) as client:
            response = await client.get(
                self.settings.third_party_api_url,
                params={"url": source_url},
                headers={
                    "Authorization": f"Bearer {self.settings.third_party_api_key}" if self.settings.third_party_api_key else "",
                },
            )
            response.raise_for_status()
            data = response.json()

        return self._adapt_response(data, source_url)

    def _adapt_response(self, data: dict[str, Any], source_url: str) -> ParsedVideo | None:
        """
        将自定义第三方API响应转换为ParsedVideo
        """
        result = data.get("data") if isinstance(data.get("data"), dict) else data

        if not isinstance(result, dict):
            logger.warning("第三方API返回格式异常")
            return None

        video_url = result.get("video_url") or result.get("url") or ""
        if not video_url:
            logger.warning("第三方API返回中未找到视频地址")
            return None

        platform = self._detect_platform(source_url)
        platform_labels = {"douyin": "抖音", "kuaishou": "快手", "xiaohongshu": "小红书"}

        title = result.get("title", "")
        author = result.get("author", "")
        cover_url = result.get("cover_url") or result.get("cover", "")

        return ParsedVideo(
            platform=platform,
            platform_label=platform_labels.get(platform, "视频"),
            title=title or f"{platform_labels.get(platform, '')}视频",
            author=author,
            cover_url=cover_url,
            video_url=video_url,
            raw_url=source_url,
            resolved_url=source_url,
            watermark_video_url=video_url,
            no_watermark_video_url=video_url,
        )

    def _adapt_bugpk_response(
        self, data: dict[str, Any], source_url: str, platform: str = "douyin", platform_label: str = "抖音"
    ) -> ParsedVideo | None:
        """
        适配bugpk.com API响应格式
        所有平台返回格式统一：{code, msg, data: {title, cover, url, ...}}
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
            # 尝试从 video_backup 获取
            backup = result.get("video_backup")
            if isinstance(backup, list) and backup:
                video_url = backup[0] if isinstance(backup[0], str) else backup[0].get("url", "")
            elif isinstance(backup, str):
                video_url = backup

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
            platform=platform,
            platform_label=platform_label,
            title=title or f"{platform_label}视频",
            author=author,
            cover_url=cover_url,
            video_url=video_url,
            raw_url=source_url,
            resolved_url=source_url,
            watermark_video_url=video_url,
            no_watermark_video_url=video_url,
        )

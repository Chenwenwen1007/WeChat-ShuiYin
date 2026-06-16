import logging

from server.parsers.base import BaseParser, ParsedVideo
from server.utils.http_client import build_client
from server.utils.text_extractor import match_first

logger = logging.getLogger(__name__)


class DouyinParser(BaseParser):
    platform_name = "douyin"
    platform_label = "抖音"

    def normalize_play_url(self, video_url: str) -> str:
        """将有水印URL中的playwm替换为play，获取无水印版本"""
        if "/playwm/" in video_url:
            return video_url.replace("/playwm/", "/play/")
        return video_url

    async def resolve_final_video_url(self, video_url: str) -> str:
        """跟随重定向获取最终视频地址"""
        async with build_client(follow_redirects=False) as client:
            response = await client.get(video_url)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if location:
                    return location
            return str(response.url)

    async def verify_no_watermark(self, video_url: str) -> bool:
        """
        验证视频地址是否为无水印版本
        通过发送HEAD请求检查响应，若被重定向回带水印地址则返回False
        """
        if not video_url:
            return False
        try:
            async with build_client(follow_redirects=True, timeout=10.0) as client:
                response = await client.head(video_url)
                final_url = str(response.url)
                # 如果最终URL包含playwm，说明被重定向回带水印版本
                if "/playwm/" in final_url:
                    logger.warning("无水印地址被重定向回带水印版本: %s -> %s", video_url, final_url)
                    return False
                return True
        except Exception as exc:
            logger.warning("验证无水印地址时出错: %s", exc)
            # 验证出错时保守处理，认为无水印有效（让用户自己尝试）
            return True

    async def parse(self, raw_url: str, resolved_url: str) -> ParsedVideo:
        html = await self.fetch_html(resolved_url)
        title = self.extract_meta(html, "og:title") or match_first(
            html,
            [
                r'"desc"\s*:\s*"([^"]+)"',
                r'"share_info"\s*:\s*\{.*?"share_title"\s*:\s*"([^"]+)"',
            ],
        )
        author = match_first(
            html,
            [
                r'"nickname"\s*:\s*"([^"]+)"',
                r'"authorName"\s*:\s*"([^"]+)"',
            ],
        )
        cover_url = self.extract_meta(html, "og:image") or match_first(
            html,
            [
                r'"cover"\s*:\s*\{.*?"url_list"\s*:\s*\["([^"]+)"',
                r'"dynamic_cover"\s*:\s*\{.*?"url_list"\s*:\s*\["([^"]+)"',
            ],
        )
        watermark_video_url = self.pick_best_url(
            html,
            patterns=[
                r'"playAddr"\s*:\s*"([^"]+)"',
                r'"play_api"\s*:\s*"([^"]+)"',
                r'"url_list"\s*:\s*\["(https:[^"]*play[^"]+)"',
                r'"bitRateList"\s*:\s*\[.*?"playAddr"\s*:\s*"([^"]+)"',
            ],
            fallback_meta=("og:video", "twitter:player:stream"),
        )

        no_watermark_video_url = self.normalize_play_url(watermark_video_url)

        if watermark_video_url:
            watermark_video_url = await self.resolve_final_video_url(watermark_video_url)
        if no_watermark_video_url:
            no_watermark_video_url = await self.resolve_final_video_url(no_watermark_video_url)

        # 验证无水印地址是否有效
        is_no_watermark_valid = await self.verify_no_watermark(no_watermark_video_url)

        # 如果无水印验证失败，则回退到有水印地址
        if not is_no_watermark_valid and watermark_video_url:
            logger.info("无水印地址验证失败，回退到有水印地址")
            no_watermark_video_url = watermark_video_url

        return self.ensure_result(
            video_url=no_watermark_video_url or watermark_video_url,
            raw_url=raw_url,
            resolved_url=resolved_url,
            title=title,
            author=author,
            cover_url=cover_url,
            watermark_video_url=watermark_video_url,
            no_watermark_video_url=no_watermark_video_url,
        )

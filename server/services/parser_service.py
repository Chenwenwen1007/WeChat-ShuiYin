import logging

import httpx
from fastapi import Request

from server.parsers.douyin_api import DouyinApiParser
from server.parsers.kuaishou import KuaishouParser
from server.parsers.xiaohongshu import XiaoHongShuParser
from server.schemas.response import ParsePayload
from server.services.downloader_service import DownloadService
from server.services.third_party_service import ThirdPartyService
from server.services.url_service import UrlService
from server.utils.exceptions import AppError, ParseError

logger = logging.getLogger(__name__)


class ParserService:
    def __init__(self) -> None:
        self.url_service = UrlService()
        self.download_service = DownloadService()
        self.third_party_service = ThirdPartyService()
        self.parsers = {
            "douyin": DouyinApiParser(),
            "kuaishou": KuaishouParser(),
            "xiaohongshu": XiaoHongShuParser(),
        }

    async def parse(
        self, text: str, request: Request, mode: str = "auto"
    ) -> ParsePayload:
        """
        解析视频

        Args:
            text: 分享文案或链接
            request: FastAPI请求对象
            mode: 解析方式，auto/native/third_party
        """
        try:
            raw_url, resolved_url = await self.url_service.extract_and_resolve(text)
            platform = self.url_service.detect_platform(resolved_url)

            # 根据mode选择解析方式
            parsed_video = None
            parse_source = "native"
            no_watermark_verified = False

            if mode == "third_party":
                # 仅使用第三方API
                parsed_video = await self.third_party_service.parse(raw_url)
                parse_source = "third_party"
                if parsed_video:
                    no_watermark_verified = True
            elif mode == "auto":
                # 先尝试自有解析
                parsed_video = await self.parsers[platform].parse(raw_url, resolved_url)
                # 抖音平台：官方API返回的play_addr即为无水印地址，直接信任
                if platform == "douyin" and parsed_video:
                    no_watermark_verified = True
                    # 若自有解析未获取到无水印地址，尝试第三方兜底
                    if not parsed_video.no_watermark_video_url and self.third_party_service.is_configured():
                        logger.info("自有解析未获取无水印地址，尝试第三方API兜底")
                        third_party_result = await self.third_party_service.parse(raw_url)
                        if third_party_result:
                            parsed_video = third_party_result
                            parse_source = "fallback"
                elif platform in ("kuaishou", "xiaohongshu") and parsed_video:
                    # 快手/小红书：自有解析已提取无水印地址，标记为已验证
                    if parsed_video.no_watermark_video_url:
                        no_watermark_verified = True
                    # 若自有解析未获取到无水印地址，尝试第三方API兜底
                    elif self.third_party_service.is_configured():
                        logger.info("%s自有解析未获取无水印地址，尝试第三方API兜底", platform)
                        third_party_result = await self.third_party_service.parse(raw_url)
                        if third_party_result:
                            parsed_video = third_party_result
                            parse_source = "fallback"
                            no_watermark_verified = True
            else:
                # native模式：仅使用自有解析
                parsed_video = await self.parsers[platform].parse(raw_url, resolved_url)
                if platform == "douyin" and parsed_video:
                    no_watermark_verified = True
                elif platform in ("kuaishou", "xiaohongshu") and parsed_video:
                    no_watermark_verified = bool(parsed_video.no_watermark_video_url)

            if not parsed_video:
                raise ParseError(
                    code="PARSE_FAILED",
                    message="视频解析失败，请检查链接是否有效或尝试切换解析方式。",
                    status_code=422,
                )

            preview_cover_url = self.download_service.build_preview_cover_url(parsed_video, request)
            watermark_download_url = self.download_service.build_download_url_from_resource(
                parsed_video.title, parsed_video.watermark_video_url, request
            )
            watermark_preview_video_url = self.download_service.build_media_url(
                parsed_video.title, parsed_video.watermark_video_url, "video", request
            )
            no_watermark_download_url = self.download_service.build_download_url_from_resource(
                parsed_video.title, parsed_video.no_watermark_video_url, request
            )
            no_watermark_preview_video_url = self.download_service.build_media_url(
                parsed_video.title, parsed_video.no_watermark_video_url, "video", request
            )

            # 根据解析来源和无水印验证状态生成提示语
            if parse_source == "third_party":
                no_watermark_note = "当前使用第三方API解析，去水印效果更稳定。"
            elif parse_source == "fallback":
                no_watermark_note = "自有解析无水印链路失效，已自动切换至第三方API获取无水印视频。"
            elif no_watermark_verified:
                no_watermark_note = "无水印地址已验证通过，可直接下载。"
            else:
                no_watermark_note = (
                    "无水印为实验性链路，部分视频仍可能被平台重定向回带水印版本，请以实际下载结果为准。"
                )

            return ParsePayload(
                platform=parsed_video.platform,
                platform_label=parsed_video.platform_label,
                title=parsed_video.title,
                author=parsed_video.author,
                cover_url=parsed_video.cover_url,
                video_url=parsed_video.watermark_video_url,
                preview_cover_url=preview_cover_url,
                preview_video_url=watermark_preview_video_url,
                download_url=watermark_download_url,
                watermark_video_url=parsed_video.watermark_video_url,
                watermark_preview_video_url=watermark_preview_video_url,
                watermark_download_url=watermark_download_url,
                no_watermark_video_url=parsed_video.no_watermark_video_url,
                no_watermark_preview_video_url=no_watermark_preview_video_url,
                no_watermark_download_url=no_watermark_download_url,
                no_watermark_note=no_watermark_note,
                raw_url=parsed_video.raw_url,
                resolved_url=parsed_video.resolved_url,
                parse_source=parse_source,
                no_watermark_verified=no_watermark_verified,
            )
        except AppError:
            raise
        except httpx.HTTPStatusError as exc:
            logger.exception("Remote service returned an invalid status")
            raise ParseError(
                code="REMOTE_HTTP_ERROR",
                message="远程平台返回异常状态，请稍后重试或更换分享链接。",
                status_code=502,
                details={"status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("Network failure while parsing a share link")
            raise ParseError(
                code="NETWORK_ERROR",
                message="无法连接远程平台，请检查本机网络后重试。",
                status_code=502,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected parse failure")
            raise ParseError(
                code="UNKNOWN_ERROR",
                message="解析时发生未预期错误，请查看后端日志排查。",
                status_code=500,
            ) from exc

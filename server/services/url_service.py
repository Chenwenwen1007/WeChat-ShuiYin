from urllib.parse import urlparse

from server.utils.exceptions import ParseError, UnsupportedPlatformError
from server.utils.http_client import build_client
from server.utils.text_extractor import extract_first_url, normalize_domain


class UrlService:
    async def extract_and_resolve(self, text: str) -> tuple[str, str]:
        try:
            raw_url = extract_first_url(text)
        except ValueError as exc:
            raise ParseError("LINK_NOT_FOUND", str(exc), status_code=422) from exc

        async with build_client() as client:
            response = await client.get(raw_url)
            response.raise_for_status()
            return raw_url, str(response.url)

    def detect_platform(self, url: str) -> str:
        domain = normalize_domain(url)
        platform_map = {
            "douyin": ("douyin.com", "iesdouyin.com"),
            "kuaishou": ("kuaishou.com", "chenzhongtech.com", "gifshow.com"),
            "xiaohongshu": ("xiaohongshu.com", "xhslink.com"),
        }

        for platform, domains in platform_map.items():
            if any(item in domain for item in domains):
                return platform

        parsed = urlparse(url)
        raise UnsupportedPlatformError(
            code="UNSUPPORTED_PLATFORM",
            message="当前仅支持抖音、快手、小红书链接解析。",
            status_code=422,
            details={"domain": parsed.hostname or ""},
        )

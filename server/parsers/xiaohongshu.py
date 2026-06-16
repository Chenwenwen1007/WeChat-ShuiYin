from server.parsers.base import BaseParser, ParsedVideo
from server.utils.text_extractor import match_first


class XiaoHongShuParser(BaseParser):
    platform_name = "xiaohongshu"
    platform_label = "小红书"

    async def parse(self, raw_url: str, resolved_url: str) -> ParsedVideo:
        html = await self.fetch_html(resolved_url)
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
        video_url = self.pick_best_url(
            html,
            patterns=[
                r'"masterUrl"\s*:\s*"([^"]+)"',
                r'"h264"\s*:\s*"([^"]+)"',
                r'"originVideoKey"\s*:\s*"([^"]+)"',
                r'"videoUrl"\s*:\s*"([^"]+)"',
            ],
            fallback_meta=("og:video", "twitter:player:stream"),
        )
        return self.ensure_result(video_url, raw_url, resolved_url, title, author, cover_url)

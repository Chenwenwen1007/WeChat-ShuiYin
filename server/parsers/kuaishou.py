from server.parsers.base import BaseParser, ParsedVideo
from server.utils.text_extractor import match_first


class KuaishouParser(BaseParser):
    platform_name = "kuaishou"
    platform_label = "快手"

    async def parse(self, raw_url: str, resolved_url: str) -> ParsedVideo:
        html = await self.fetch_html(resolved_url)
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
            ],
        )
        cover_url = self.extract_meta(html, "og:image") or match_first(
            html,
            [
                r'"poster"\s*:\s*"([^"]+)"',
                r'"coverUrl"\s*:\s*"([^"]+)"',
            ],
        )
        video_url = self.pick_best_url(
            html,
            patterns=[
                r'"srcNoMark"\s*:\s*"([^"]+)"',
                r'"photoUrl"\s*:\s*"([^"]+)"',
                r'"mainMvUrls"\s*:\s*\[\s*"([^"]+)"',
                r'"hevc"\s*:\s*\{.*?"url"\s*:\s*"([^"]+)"',
            ],
            fallback_meta=("og:video", "twitter:player:stream"),
        )
        return self.ensure_result(video_url, raw_url, resolved_url, title, author, cover_url)

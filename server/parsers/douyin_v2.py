import json
import logging
import re

from server.parsers.base import BaseParser, ParsedVideo
from server.utils.http_client import build_client
from server.utils.text_extractor import match_first

logger = logging.getLogger(__name__)


class DouyinV2Parser(BaseParser):
    """
    抖音解析器V2（基于开源项目jiuhunwl/short_videos的No Cookie方案优化）
    原理：
    1. 通过iesdouyin.com的分享页面获取视频元数据（无需Cookie和签名）
    2. 优先选择v3-web域名的视频地址（本身无水印）
    3. 回退到playwm替换方案
    """

    platform_name = "douyin"
    platform_label = "抖音"

    async def extract_video_id(self, url: str) -> str | None:
        """
        从URL中提取视频ID（aweme_id）
        支持短链、长链、modal_id等多种格式
        """
        # 先跟随重定向获取真实URL
        resolved = await self._resolve_url(url)
        if not resolved:
            resolved = url

        # 尝试从URL参数中提取
        patterns = [
            r"[?&]modal_id=(\d+)",
            r"[?&]vid=(\d+)",
            r"[?&]id=(\d+)",
            r"/video/(\d+)",
            r"/note/(\d+)",
            r"/share/video/(\d+)",
            r"/share/slides/(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, resolved)
            if match:
                return match.group(1)

        # 尝试匹配纯数字
        match = re.search(r"/(\d{19,20})", resolved)
        if match:
            return match.group(1)

        return None

    async def _resolve_url(self, url: str) -> str | None:
        """跟随重定向获取最终URL"""
        try:
            async with build_client(follow_redirects=False) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
                    },
                )
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if location:
                        return location
        except Exception as exc:
            logger.warning("解析短链失败: %s", exc)
        return None

    async def _fetch_video_page(self, video_id: str) -> str:
        """
        获取iesdouyin分享页面的HTML内容
        使用iPhone UA模拟移动端访问
        """
        url = f"https://www.iesdouyin.com/share/video/{video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        return await self.fetch_html(url, headers=headers)

    def _extract_router_data(self, html: str) -> dict | None:
        """
        从HTML中提取window._ROUTER_DATA JSON数据
        这是iesdouyin页面嵌入的视频元数据
        """
        # 方案1：匹配 window._ROUTER_DATA
        pattern = r"window\._ROUTER_DATA\s*=\s*(.*?)</script>"
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                if data and "loaderData" in data:
                    return data
            except json.JSONDecodeError:
                pass

        # 方案2：匹配 <script id="RENDER_DATA">
        pattern2 = r'<script id="RENDER_DATA" type="application/json">(.*?)</script>'
        match2 = re.search(pattern2, html, re.DOTALL)
        if match2:
            try:
                json_str = match2.group(1).strip()
                # 抖音的RENDER_DATA通常经过URL编码
                import urllib.parse
                json_str = urllib.parse.unquote(json_str)
                data = json.loads(json_str)
                if data:
                    return data
            except (json.JSONDecodeError, Exception):
                pass

        return None

    def _extract_video_detail(self, router_data: dict) -> dict | None:
        """
        从ROUTER_DATA中提取视频详情
        支持多种数据结构
        """
        if not router_data:
            return None

        # 方案1：loaderData结构（iesdouyin/share/video页面）
        loader_data = router_data.get("loaderData")
        if loader_data and isinstance(loader_data, dict):
            for key, value in loader_data.items():
                if not isinstance(value, dict):
                    continue
                if key.startswith("video_") or key.startswith("note_"):
                    video_info_res = value.get("videoInfoRes")
                    if isinstance(video_info_res, dict):
                        item_list = video_info_res.get("item_list", [])
                        if isinstance(item_list, list) and item_list:
                            return item_list[0]

        # 方案2：app.videoDetail结构（RENDER_DATA）
        app = router_data.get("app")
        if app and "videoDetail" in app:
            return app["videoDetail"]

        # 方案3：直接查找item_list
        if "item_list" in router_data:
            item_list = router_data.get("item_list", [])
            if item_list:
                return item_list[0]

        return None

    def _extract_best_video_url(self, detail: dict) -> tuple[str, list[str]]:
        """
        从视频详情中提取最佳视频地址
        优先策略：
        1. v3-web域名（本身无水印，最稳定）
        2. v26-web域名（替换为v26-luna.douyinvod.com）
        3. playwm替换为play
        4. 其他可用链接

        Returns:
            (主视频URL, 备用URL列表)
        """
        video = detail.get("video", {})
        if not video:
            return "", []

        url = ""
        backup = []

        # 方案1：从bitRateList/bit_rate中提取（最高画质）
        bit_rate_list = video.get("bitRateList") or video.get("bit_rate") or []
        if bit_rate_list:
            # 按码率降序排序
            bit_rate_list = sorted(
                bit_rate_list,
                key=lambda x: x.get("bitRate", x.get("bit_rate", 0)) if isinstance(x, dict) else 0,
                reverse=True,
            )

            for rate_item in bit_rate_list:
                if not isinstance(rate_item, dict):
                    continue

                candidates = []
                # 尝试playAddr数组结构
                play_addrs = rate_item.get("playAddr", [])
                if play_addrs and isinstance(play_addrs, list):
                    for pa in play_addrs:
                        if isinstance(pa, dict) and "src" in pa:
                            candidates.append(pa["src"])

                # 尝试play_addr.url_list字符串数组
                if not candidates:
                    url_list = rate_item.get("play_addr", {}).get("url_list", [])
                    if url_list and isinstance(url_list, list):
                        candidates = [u for u in url_list if isinstance(u, str)]

                if not candidates:
                    continue

                # 优先选择v3-web域名（无水印）
                v3_link = None
                v26_link = None
                for candidate in candidates:
                    if "v3-web" in candidate:
                        v3_link = candidate
                        break
                    if "v26-web" in candidate and not v26_link:
                        v26_link = candidate

                current_best = v3_link
                if not current_best and v26_link:
                    # v26-web替换为v26-luna.douyinvod.com
                    current_best = re.sub(r"://([^/]+)", "://v26-luna.douyinvod.com", v26_link)
                if not current_best:
                    current_best = candidates[0]

                if not url:
                    url = current_best

                # 收集备用链接
                for candidate in candidates:
                    if "v26-web" in candidate:
                        candidate = re.sub(r"://([^/]+)", "://v26-luna.douyinvod.com", candidate)
                    if candidate != url and candidate not in backup:
                        backup.append(candidate)

                if url and backup:
                    break

        # 方案2：从play_addr.url_list提取
        if not url:
            play_addr = video.get("play_addr", {})
            url_list = play_addr.get("url_list", [])
            if url_list and isinstance(url_list, list):
                # 优先找v3-web
                for candidate in url_list:
                    if isinstance(candidate, str) and "v3-web" in candidate:
                        url = candidate
                        break
                if not url:
                    url = url_list[0]

                # 收集备用
                for candidate in url_list[1:]:
                    if isinstance(candidate, str) and candidate != url and candidate not in backup:
                        backup.append(candidate)

        # 方案3：从playApi提取
        if not url:
            play_api = video.get("playApi")
            if play_api and isinstance(play_api, str):
                url = play_api

        # 统一替换playwm为play（去除水印标识）
        if url:
            url = url.replace("playwm", "play")
        backup = [b.replace("playwm", "play") for b in backup]

        return url, backup

    def _extract_cover(self, detail: dict) -> str:
        """从视频详情中提取封面图"""
        video = detail.get("video", {})

        # 优先originCover（原图封面）
        for key in ["originCover", "origin_cover"]:
            oc = video.get(key)
            if isinstance(oc, dict):
                for k in ["urlList", "url_list"]:
                    ul = oc.get(k)
                    if isinstance(ul, list) and ul:
                        return str(ul[0])
            elif isinstance(oc, str) and oc:
                return oc

        # 普通cover
        cover = video.get("cover")
        if isinstance(cover, dict):
            for k in ["urlList", "url_list"]:
                ul = cover.get(k)
                if isinstance(ul, list) and ul:
                    return str(ul[0])
        elif isinstance(cover, str) and cover:
            return cover

        # dynamicCover
        for key in ["dynamicCover", "dynamic_cover"]:
            dc = video.get(key)
            if isinstance(dc, dict):
                for k in ["urlList", "url_list"]:
                    ul = dc.get(k)
                    if isinstance(ul, list) and ul:
                        return str(ul[0])

        return ""

    async def parse(self, raw_url: str, resolved_url: str) -> ParsedVideo:
        """
        解析抖音视频
        使用iesdouyin分享页面方案（无需Cookie和签名）
        """
        # 1. 提取视频ID
        video_id = await self.extract_video_id(resolved_url)
        if not video_id:
            video_id = await self.extract_video_id(raw_url)
        if not video_id:
            raise ValueError(f"无法从链接中提取视频ID: {resolved_url}")

        logger.info("提取到视频ID: %s", video_id)

        # 2. 获取iesdouyin分享页面
        html = await self._fetch_video_page(video_id)
        if not html:
            raise ValueError("获取分享页面失败")

        # 3. 提取ROUTER_DATA
        router_data = self._extract_router_data(html)
        if not router_data:
            # 尝试回退到旧的HTML解析（当前方案）
            logger.warning("无法从iesdouyin提取数据，回退到旧方案")
            from server.parsers.douyin import DouyinParser
            return await DouyinParser().parse(raw_url, resolved_url)

        # 4. 提取视频详情
        detail = self._extract_video_detail(router_data)
        if not detail:
            raise ValueError("无法从页面数据中提取视频详情")

        # 5. 提取基本信息
        title = detail.get("desc", "")
        author = detail.get("author", {})
        author_name = ""
        if isinstance(author, dict):
            author_name = author.get("nickname", "")

        cover_url = self._extract_cover(detail)

        # 6. 提取视频地址
        video_url, backup_urls = self._extract_best_video_url(detail)

        if not video_url:
            raise ValueError("无法提取视频地址")

        # 7. 构建结果
        # 主视频地址（优先无水印）
        main_video_url = video_url

        # 有水印版本（如果有playwm标识则保留原始，否则和主地址相同）
        watermark_video_url = video_url.replace("play", "playwm") if "playwm" in video_url else video_url

        return self.ensure_result(
            video_url=main_video_url,
            raw_url=raw_url,
            resolved_url=resolved_url,
            title=title or "抖音视频",
            author=author_name,
            cover_url=cover_url,
            watermark_video_url=watermark_video_url,
            no_watermark_video_url=main_video_url,
        )

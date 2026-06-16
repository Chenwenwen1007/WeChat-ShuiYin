import json
import logging
import re

from server.parsers.base import BaseParser, ParsedVideo
from server.utils.douyin_sign import generate_a_bogus
from server.utils.http_client import build_client

logger = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"


class DouyinApiParser(BaseParser):
    """
    抖音官方API解析器（基于Workers签名算法）
    通过生成合法的a_bogus签名，调用抖音官方Web API获取视频详情
    从中提取v3-web/v26-web域名的真正无水印视频地址
    """

    platform_name = "douyin"
    platform_label = "抖音"

    async def extract_video_id(self, url: str) -> str | None:
        """从URL中提取视频ID"""
        # 先跟随重定向获取真实URL
        resolved = await self._resolve_url(url)
        if not resolved:
            resolved = url

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
                    headers={"User-Agent": DEFAULT_UA},
                )
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if location:
                        return location
        except Exception as exc:
            logger.warning("解析短链失败: %s", exc)
        return None

    async def _get_ttwid(self) -> str | None:
        """获取ttwid Cookie"""
        try:
            async with build_client() as client:
                response = await client.post(
                    "https://ttwid.bytedance.com/ttwid/union/register/",
                    json={
                        "region": "cn",
                        "aid": 6383,
                        "need_t": 1,
                        "service": "www.douyin.com",
                        "migrate_priority": 0,
                        "cb_url_protocol": "https",
                        "domain": ".douyin.com",
                    },
                    headers={
                        "content-type": "application/json",
                        "user-agent": DEFAULT_UA,
                    },
                )
                set_cookie = response.headers.get("set-cookie", "")
                match = re.search(r"(?:^|,\s*)ttwid=([^;\s]+)", set_cookie, re.I)
                if match:
                    from urllib.parse import unquote
                    return unquote(match.group(1))
        except Exception as exc:
            logger.warning("获取ttwid失败: %s", exc)
        return None

    async def _fetch_aweme_detail(self, aweme_id: str) -> dict | None:
        """
        调用抖音官方API获取视频详情
        需要生成合法的a_bogus签名
        """
        referer_base = f"https://www.douyin.com/video/{aweme_id}"

        # 先访问视频页面获取必要的上下文
        try:
            async with build_client() as client:
                await client.get(
                    f"{referer_base}?previous_page=web_code_link",
                    headers={
                        "user-agent": DEFAULT_UA,
                        "accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                        "accept-language": "zh-CN,zh;q=0.9",
                    },
                )
        except Exception:
            pass

        last_failure = ""

        for attempt in range(2):
            ttwid = await self._get_ttwid()
            if not ttwid:
                ttwid = "1%7CvDWCB8tYdKPbdOlqwNTkDPhizBaV9i91KjYLKJbqurg%7C1723536402%7C314e63000decb79f46b8ff255560b29f4d8c57352dad465b41977db4830b4c7e"

            # 生成msToken
            base = "ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789="
            ms_token = "".join(base[__import__("random").randint(0, len(base) - 1)] for _ in range(107))

            # 构造查询参数
            params = {
                "device_platform": "webapp",
                "aid": "6383",
                "channel": "channel_pc_web",
                "aweme_id": aweme_id,
                "msToken": ms_token,
            }
            query = "&".join(f"{k}={v}" for k, v in params.items())

            # 生成a_bogus签名
            a_bogus = generate_a_bogus(query, DEFAULT_UA)
            if not a_bogus:
                return None

            final_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?{query}&a_bogus={a_bogus}"

            try:
                async with build_client() as client:
                    response = await client.get(
                        final_url,
                        headers={
                            "accept": "application/json, text/plain, */*",
                            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
                            "referer": f"{referer_base}?previous_page=web_code_link",
                            "user-agent": DEFAULT_UA,
                            "sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
                            "sec-ch-ua-mobile": "?0",
                            "sec-ch-ua-platform": '"Windows"',
                            "sec-fetch-dest": "empty",
                            "sec-fetch-mode": "cors",
                            "sec-fetch-site": "same-origin",
                            "cookie": f"ttwid={ttwid}",
                        },
                    )
                    response.raise_for_status()
                    body = response.text
            except Exception as exc:
                last_failure = str(exc)
                continue

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                last_failure = "详情接口返回非JSON"
                continue

            if not data or not data.get("aweme_detail"):
                api_msg = data.get("status_msg") or data.get("statusMsg") or ""
                if api_msg:
                    last_failure = api_msg
                elif "status_code" in data:
                    last_failure = f"status_code={data['status_code']}，无aweme_detail"
                else:
                    last_failure = "接口未返回aweme_detail"
                continue

            return data

        logger.warning("抖音官方API请求失败: %s", last_failure)
        return None

    def _extract_best_video_url(self, detail: dict) -> tuple[str, list[str]]:
        """
        从官方API返回的视频详情中提取最佳无水印视频地址
        优先策略：
        1. v3-web域名（本身无水印）
        2. v26-web域名（替换为v26-luna.douyinvod.com）
        3. playwm替换为play
        """
        video = detail.get("video", {})
        if not video:
            return "", []

        url = ""
        backup = []

        # 方案1：从bitRateList/bit_rate中提取（最高画质）
        bit_rate_list = video.get("bitRateList") or video.get("bit_rate") or []
        if bit_rate_list:
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
                    current_best = re.sub(r"://([^/]+)", "://v26-luna.douyinvod.com", v26_link)
                if not current_best:
                    current_best = candidates[0]

                if not url:
                    url = current_best

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
                for candidate in url_list:
                    if isinstance(candidate, str) and "v3-web" in candidate:
                        url = candidate
                        break
                if not url:
                    url = url_list[0]

                for candidate in url_list[1:]:
                    if isinstance(candidate, str) and candidate != url and candidate not in backup:
                        backup.append(candidate)

        # 统一替换playwm为play
        if url:
            url = url.replace("playwm", "play")
        backup = [b.replace("playwm", "play") for b in backup]

        return url, backup

    async def verify_no_watermark(self, video_url: str) -> bool:
        """验证视频地址是否为无水印版本"""
        if not video_url:
            return False
        try:
            async with build_client(follow_redirects=True, timeout=10.0) as client:
                response = await client.head(video_url)
                final_url = str(response.url)
                if "/playwm/" in final_url:
                    logger.warning("无水印地址被重定向回带水印版本: %s -> %s", video_url, final_url)
                    return False
                return True
        except Exception as exc:
            logger.warning("验证无水印地址时出错: %s", exc)
            return True

    def _extract_cover(self, detail: dict) -> str:
        """提取封面图"""
        video = detail.get("video", {})

        for key in ["originCover", "origin_cover"]:
            oc = video.get(key)
            if isinstance(oc, dict):
                for k in ["urlList", "url_list"]:
                    ul = oc.get(k)
                    if isinstance(ul, list) and ul:
                        return str(ul[0])
            elif isinstance(oc, str) and oc:
                return oc

        cover = video.get("cover")
        if isinstance(cover, dict):
            for k in ["urlList", "url_list"]:
                ul = cover.get(k)
                if isinstance(ul, list) and ul:
                    return str(ul[0])
        elif isinstance(cover, str) and cover:
            return cover

        return ""

    async def parse(self, raw_url: str, resolved_url: str) -> ParsedVideo:
        """
        解析抖音视频
        使用官方API + a_bogus签名方案
        """
        # 1. 提取视频ID
        video_id = await self.extract_video_id(resolved_url)
        if not video_id:
            video_id = await self.extract_video_id(raw_url)
        if not video_id:
            raise ValueError(f"无法从链接中提取视频ID: {resolved_url}")

        logger.info("使用官方API解析，视频ID: %s", video_id)

        # 2. 调用官方API
        api_result = await self._fetch_aweme_detail(video_id)
        if not api_result:
            # 回退到V2方案
            logger.warning("官方API解析失败，回退到iesdouyin方案")
            from server.parsers.douyin_v2 import DouyinV2Parser
            return await DouyinV2Parser().parse(raw_url, resolved_url)

        detail = api_result.get("aweme_detail", {})

        # 3. 提取基本信息
        title = detail.get("desc", "")
        author = detail.get("author", {})
        author_name = ""
        if isinstance(author, dict):
            author_name = author.get("nickname", "")

        cover_url = self._extract_cover(detail)

        # 4. 提取视频地址
        video = detail.get("video", {})
        
        # 有水印地址：优先从 download_addr 获取（这是APP保存本地的带水印版本）
        watermark_url = ""
        download_addr = video.get("download_addr", {})
        if isinstance(download_addr, dict):
            ul = download_addr.get("url_list", [])
            if ul and isinstance(ul, list) and ul:
                watermark_url = ul[0]
        
        # 无水印地址：从 bit_rate 或 play_addr 获取（播放地址通常无水印）
        no_watermark_url, _ = self._extract_best_video_url(detail)

        if not no_watermark_url:
            raise ValueError("无法从官方API提取视频地址")

        # 确保有水印地址不为空（回退到无水印地址）
        if not watermark_url:
            watermark_url = no_watermark_url

        return self.ensure_result(
            video_url=no_watermark_url,
            raw_url=raw_url,
            resolved_url=resolved_url,
            title=title or "抖音视频",
            author=author_name,
            cover_url=cover_url,
            watermark_video_url=watermark_url,
            no_watermark_video_url=no_watermark_url,
        )

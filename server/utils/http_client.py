from __future__ import annotations

from typing import AsyncIterator

import httpx

from server.config import get_settings

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def build_client(follow_redirects: bool = True, timeout: float | None = None) -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=timeout or settings.http_timeout,
        headers=DEFAULT_HEADERS,
        follow_redirects=follow_redirects,
    )


async def stream_remote_file(url: str) -> tuple[AsyncIterator[bytes], httpx.Response]:
    settings = get_settings()
    client = build_client(timeout=settings.download_timeout)
    
    headers = {}
    if "douyin" in url.lower():
        headers["Referer"] = "https://www.douyin.com/"
    elif "kuaishou" in url.lower():
        headers["Referer"] = "https://www.kuaishou.com/"
    elif "xiaohongshu" in url.lower():
        headers["Referer"] = "https://www.xiaohongshu.com/"
    
    request = client.build_request("GET", url, headers=headers)
    response = await client.send(request, stream=True)
    response.raise_for_status()

    async def iterator() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return iterator(), response

import re
from html import unescape
from urllib.parse import urlparse

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def extract_first_url(text: str) -> str:
    match = URL_PATTERN.search(text)
    if not match:
        raise ValueError("未在输入内容中识别到链接。")
    return match.group(0).rstrip("。,，；;）)]}>\"'")


def unescape_text(value: str) -> str:
    return unescape(value.replace("\\/", "/").replace("\\u002F", "/").strip())


def clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip() or "未命名视频"


def match_first(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        matched = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if matched:
            return unescape_text(matched.group(1))
    return ""


def normalize_domain(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    return hostname.lower()

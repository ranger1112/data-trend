import re

import httpx


CHARSET_PATTERN = re.compile(rb"charset\s*=\s*['\"]?([a-zA-Z0-9_\-]+)", re.IGNORECASE)
CHINESE_CHARSETS = {"gb2312", "gbk", "gb18030"}


class HtmlFetcher:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return decode_html(response)


def decode_html(response: httpx.Response) -> str:
    encoding = _normalize_encoding(_extract_charset(response.content) or response.encoding)
    if not encoding:
        encoding = _normalize_encoding(response.charset_encoding) or "utf-8"
    return response.content.decode(encoding, errors="replace")


def _extract_charset(content: bytes) -> str | None:
    head = content[:4096]
    match = CHARSET_PATTERN.search(head)
    if not match:
        return None
    return match.group(1).decode("ascii", errors="ignore")


def _normalize_encoding(encoding: str | None) -> str | None:
    if not encoding:
        return None
    encoding = encoding.strip().lower()
    return "gb18030" if encoding in CHINESE_CHARSETS else encoding

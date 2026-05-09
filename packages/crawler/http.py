import httpx


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
            response.encoding = response.encoding or "utf-8"
            return response.text


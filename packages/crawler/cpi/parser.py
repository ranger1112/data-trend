import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from packages.crawler.cpi.dto import CpiRecord


class CpiHtmlParser:
    def parse(self, html: str, source_url: str) -> list[CpiRecord]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        title = self._title(soup, text)
        period = self._period(title, text)
        published_at = self._published_at(text)

        yoy = self._extract_percent(text, r"全国居民消费价格同比(?P<verb>上涨|下降)(?P<value>\d+(?:\.\d+)?)%")
        mom = self._extract_percent(text, r"全国居民消费价格环比(?P<verb>上涨|下降)(?P<value>\d+(?:\.\d+)?)%")
        avg = self._extract_percent(
            text,
            r"\d+—\d+月平均，全国居民消费价格比上年同期(?P<verb>上涨|下降)(?P<value>\d+(?:\.\d+)?)%",
            required=False,
        )

        return [
            CpiRecord(
                region_name="全国",
                period=period,
                year_on_year=yoy,
                month_on_month=mom,
                cumulative_average=avg,
                source_title=title,
                source_url=source_url,
                published_at=published_at,
                raw={"title": title},
            )
        ]

    def _title(self, soup: BeautifulSoup, text: str) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        for line in text.splitlines():
            if "居民消费价格" in line:
                return line.strip()
        return "居民消费价格数据"

    def _period(self, title: str, text: str) -> date:
        match = re.search(r"(?P<year>20\d{2})年(?P<month>\d{1,2})月份居民消费价格", f"{title}\n{text}")
        if not match:
            raise ValueError("CPI period not found")
        return date(int(match.group("year")), int(match.group("month")), 1)

    def _published_at(self, text: str) -> datetime | None:
        match = re.search(r"(20\d{2})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})", text)
        if not match:
            return None
        year, month, day, hour, minute = [int(part) for part in match.groups()]
        return datetime(year, month, day, hour, minute)

    def _extract_percent(self, text: str, pattern: str, required: bool = True) -> float | None:
        match = re.search(pattern, text)
        if not match:
            if required:
                raise ValueError(f"CPI value not found: {pattern}")
            return None
        value = float(match.group("value"))
        return -value if match.group("verb") == "下降" else value

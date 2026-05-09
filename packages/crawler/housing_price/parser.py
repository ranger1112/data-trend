import re
from datetime import date, datetime

from bs4 import BeautifulSoup, Tag

from packages.crawler.housing_price.dto import HousingPriceRecord


TABLE_NAMES = [
    ("70个大中城市新建商品住宅销售价格指数", "new_house", "none"),
    ("70个大中城市二手住宅销售价格指数", "second_hand", "none"),
    ("70个大中城市新建商品住宅销售价格分类指数（一）", "new_house", "classified"),
    ("70个大中城市新建商品住宅销售价格分类指数（二）", "new_house", "classified"),
    ("70个大中城市二手住宅销售价格分类指数（一）", "second_hand", "classified"),
    ("70个大中城市二手住宅销售价格分类指数（二）", "second_hand", "classified"),
]


class HousingPriceHtmlParser:
    def parse(self, html: str, source_url: str) -> list[HousingPriceRecord]:
        soup = BeautifulSoup(html, "html.parser")
        title = self._extract_title(soup)
        period = self._extract_period(title)
        published_at = self._extract_published_at(soup)
        records: list[HousingPriceRecord] = []

        for index, table in enumerate(soup.find_all("table")[:6]):
            table_name, house_type, table_area_mode = TABLE_NAMES[index]
            for row in self._parse_table(table, table_area_mode):
                records.append(
                    HousingPriceRecord(
                        city_name=row["city_name"],
                        period=period,
                        house_type=house_type,
                        area_type=row["area_type"],
                        month_on_month=row["mom"],
                        year_on_year=row["yoy"],
                        ytd_average=row["ytd"],
                        source_title=title or table_name,
                        source_url=source_url,
                        published_at=published_at,
                        raw={"table_name": table_name},
                    )
                )

        return records

    def _parse_table(self, table: Tag, area_mode: str) -> list[dict]:
        parsed: list[dict] = []
        rows = table.find_all("tr")[2:]
        for row in rows:
            cells = [self._clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
            cells = [cell for cell in cells if cell]
            if len(cells) < 4 or self._is_header_row(cells):
                continue

            if area_mode == "classified" and len(cells) == 10:
                self._append_row(parsed, cells[0], cells[1], cells[2], cells[3], "under_90")
                self._append_row(parsed, cells[0], cells[4], cells[5], cells[6], "between_90_144")
                self._append_row(parsed, cells[0], cells[7], cells[8], cells[9], "over_144")
            elif len(cells) == 8:
                self._append_row(parsed, cells[0], cells[1], cells[2], cells[3], "none")
                self._append_row(parsed, cells[4], cells[5], cells[6], cells[7], "none")
            elif len(cells) == 7:
                self._append_row(parsed, cells[0], cells[1], cells[2], "100", "under_90")
                self._append_row(parsed, cells[0], cells[3], cells[4], "100", "between_90_144")
                self._append_row(parsed, cells[0], cells[5], cells[6], "100", "over_144")
            elif len(cells) == 6:
                self._append_row(parsed, cells[0], cells[1], cells[2], "100", "none")
                self._append_row(parsed, cells[3], cells[4], cells[5], "100", "none")
        return parsed

    def _append_row(
        self,
        rows: list[dict],
        city_name: str,
        mom: str,
        yoy: str,
        ytd: str,
        area_type: str,
    ) -> None:
        clean_city = self._normalize_city(city_name)
        if not clean_city:
            return
        rows.append(
            {
                "city_name": clean_city,
                "mom": self._to_float(mom),
                "yoy": self._to_float(yoy),
                "ytd": self._to_float(ytd),
                "area_type": area_type,
            }
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        heading = soup.find(["h1", "h2"])
        return heading.get_text(strip=True) if heading else "商品住宅销售价格数据"

    def _extract_period(self, title: str) -> date:
        match = re.search(r"(\d{4})年(\d{1,2})月", title)
        if not match:
            today = date.today()
            return date(today.year, today.month, 1)
        return date(int(match.group(1)), int(match.group(2)), 1)

    def _extract_published_at(self, soup: BeautifulSoup) -> datetime | None:
        meta = soup.find("meta", attrs={"name": "PubDate"})
        if not meta or not meta.get("content"):
            return None
        value = meta["content"].replace("/", "-")
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def _is_header_row(self, cells: list[str]) -> bool:
        text = " ".join(cells[:2])
        return any(keyword in text for keyword in ["上年同月", "上年同期", "上月", "环比", "同比", "=100"])

    def _normalize_city(self, value: str) -> str:
        return re.sub(r"[\s\u3000]+", "", value)

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _to_float(self, value: str) -> float:
        value = value.replace("%", "").replace(",", "").strip()
        return float(value or 0)


from urllib.parse import urljoin

from bs4 import BeautifulSoup

from packages.crawler.housing_price.dto import GovStatsArticle


class GovStatsListParser:
    def parse(self, html: str, base_url: str) -> list[GovStatsArticle]:
        soup = BeautifulSoup(html, "html.parser")
        articles: list[GovStatsArticle] = []

        for item in soup.select(".list-content li"):
            link = item.select_one("a.fl.pc_1600") or item.find("a")
            if not link:
                continue
            title = link.get_text(strip=True)
            if "商品住宅销售价格" not in title:
                continue
            href = link.get("href")
            if not href:
                continue
            date_node = item.find("span")
            articles.append(
                GovStatsArticle(
                    title=title,
                    url=urljoin(base_url, href),
                    publish_date=date_node.get_text(strip=True) if date_node else None,
                )
            )

        if not articles and "商品住宅销售价格" in soup.get_text(" ", strip=True):
            title = soup.title.get_text(strip=True) if soup.title else "商品住宅销售价格数据"
            articles.append(GovStatsArticle(title=title, url=base_url))

        return articles


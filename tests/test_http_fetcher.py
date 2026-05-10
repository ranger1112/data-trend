import httpx

from packages.crawler.http import decode_html


def test_decode_html_uses_meta_charset_for_gb2312():
    html = (
        '<html><head><meta charset="gb2312"></head>'
        "<body>北京 商品住宅销售价格</body></html>"
    ).encode("gb2312")
    response = httpx.Response(200, content=html)

    assert "北京" in decode_html(response)

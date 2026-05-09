from packages.crawler.housing_price.parser import HousingPriceHtmlParser


def test_parse_basic_housing_price_table():
    html = """
    <html>
      <head><title>2025年10月份70个大中城市商品住宅销售价格变动情况</title></head>
      <body>
        <table>
          <tr><td>header</td></tr>
          <tr><td>header</td></tr>
          <tr>
            <td>北　　京</td><td>100.2</td><td>101.1</td><td>99.8</td>
            <td>上　　海</td><td>100.5</td><td>102.0</td><td>100.0</td>
          </tr>
        </table>
      </body>
    </html>
    """

    records = HousingPriceHtmlParser().parse(html, "https://example.test/article.html")

    assert len(records) == 2
    assert records[0].city_name == "北京"
    assert records[0].period.isoformat() == "2025-10-01"
    assert records[0].house_type == "new_house"
    assert records[0].area_type == "none"
    assert records[0].month_on_month == 100.2


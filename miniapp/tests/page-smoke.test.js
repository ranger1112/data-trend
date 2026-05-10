const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");

function loadPage(relativePath, wxMock) {
  let pageConfig;
  global.getApp = () => ({ globalData: { apiBase: "https://api.example.test" } });
  global.wx = wxMock;
  global.Page = (config) => {
    pageConfig = {
      ...config,
      data: JSON.parse(JSON.stringify(config.data || {})),
      setData(patch) {
        this.data = { ...this.data, ...patch };
      },
    };
  };

  const fullPath = path.join(root, relativePath);
  delete require.cache[require.resolve(fullPath)];
  require(fullPath);
  assert.ok(pageConfig, `Page was not registered for ${relativePath}`);
  return pageConfig;
}

function createWxMock(fixtures = {}) {
  const storage = new Map();
  const requests = [];
  const navigations = [];
  return {
    requests,
    navigations,
    getStorageSync(key) {
      return storage.get(key);
    },
    setStorageSync(key, value) {
      storage.set(key, value);
    },
    navigateTo(payload) {
      navigations.push(payload.url);
    },
    request(options) {
      const url = new URL(options.url);
      const pathWithQuery = `${url.pathname}${url.search}`;
      requests.push(pathWithQuery);
      const response = fixtures[pathWithQuery] || fixtures[url.pathname] || {};
      options.success({ statusCode: 200, data: response });
    },
  };
}

const fixtures = {
  "/mini/dashboard/overview": {
    regions: 2,
    indicators: 2,
    published_values: 4,
    latest_period: "2026-03-01",
    cache_ttl_seconds: 300,
  },
  "/mini/regions": [
    { id: 1, name: "北京", normalized_name: "beijing", level: "city", parent_id: null },
    { id: 2, name: "全国", normalized_name: "country", level: "country", parent_id: null },
  ],
  "/mini/indicators": [
    { id: 1, code: "housing_price_mom", name: "房价环比", display_name: "住宅价格环比", category: "housing_price" },
    { id: 2, code: "cpi_yoy", name: "CPI 同比", display_name: "CPI 同比", category: "cpi" },
  ],
  "/mini/indicator-groups": [
    {
      category: "housing_price",
      name: "房价指标",
      items: [{ id: 1, code: "housing_price_mom", name: "房价环比", display_name: "住宅价格环比" }],
    },
    {
      category: "cpi",
      name: "居民消费价格",
      items: [{ id: 2, code: "cpi_yoy", name: "CPI 同比", display_name: "CPI 同比" }],
    },
  ],
  "/mini/home/recommendations": {
    recommended_indicators: [{ id: 1, code: "housing_price_mom", name: "房价环比", display_name: "住宅价格环比" }],
    recommended_regions: [{ id: 1, name: "北京", level: "city" }],
    ranking_indicator: "housing_price_mom",
    default_trend_indicator: "housing_price_mom",
    cache_ttl_seconds: 300,
  },
  "/mini/regions/1/detail": {
    region: { id: 1, name: "北京", normalized_name: "beijing", level: "city", parent_id: null },
    indicator_cards: [
      {
        region_id: 1,
        region: "北京",
        period: "2026-03-01",
        value: 101.2,
        indicator: {
          id: 1,
          code: "housing_price_mom",
          name: "房价环比",
          display_name: "住宅价格环比",
          category: "housing_price",
          unit: "%",
          description: "住宅销售价格较上月变化幅度。",
        },
      },
    ],
    cache_ttl_seconds: 300,
  },
  "/mini/stat-values/latest?indicator_code=housing_price_mom": {
    items: [{ region_id: 1, region: "北京", period: "2026-03-01", value: 101.2 }],
    cache_ttl_seconds: 300,
  },
  "/mini/rankings?indicator_code=housing_price_mom": {
    top: [{ region_id: 1, region: "北京", period: "2026-03-01", value: 101.2 }],
    bottom: [{ region_id: 2, region: "全国", period: "2026-03-01", value: -0.1 }],
    cache_ttl_seconds: 300,
  },
  "/mini/rankings?indicator_code=cpi_yoy": {
    top: [{ region_id: 2, region: "全国", period: "2026-03-01", value: -0.1 }],
    bottom: [{ region_id: 1, region: "北京", period: "2026-03-01", value: -0.2 }],
    cache_ttl_seconds: 300,
  },
  "/mini/stat-values/trend?region_id=1&indicator_code=housing_price_mom": {
    items: [{ period: "2026-03-01", value: 101.2 }],
    cache_ttl_seconds: 300,
  },
  "/mini/stat-values/trend?region_id=1&indicator_code=cpi_yoy": {
    items: [{ period: "2026-03-01", value: -0.1 }],
    cache_ttl_seconds: 300,
  },
  "/mini/stat-values/compare?region_ids=1,2&indicator_code=housing_price_mom": {
    series: [
      { region_id: 1, region: "北京", items: [{ period: "2026-03-01", value: 101.2 }] },
      { region_id: 2, region: "全国", items: [{ period: "2026-03-01", value: -0.1 }] },
    ],
    cache_ttl_seconds: 300,
  },
  "/mini/stat-values/compare?region_ids=2,1&indicator_code=housing_price_mom": {
    series: [
      { region_id: 2, region: "全国", items: [{ period: "2026-03-01", value: -0.1 }] },
      { region_id: 1, region: "北京", items: [{ period: "2026-03-01", value: 101.2 }] },
    ],
    cache_ttl_seconds: 300,
  },
};

test("index page supports loading, caching, favorite city and navigation", async () => {
  const wxMock = createWxMock(fixtures);
  const page = loadPage("pages/index/index.js", wxMock);

  await page.loadPage();
  assert.equal(page.data.currentRegion.name, "北京");
  assert.equal(page.data.currentIndicator.code, "housing_price_mom");
  assert.equal(page.data.latestValues.length, 1);
  assert.equal(page.data.trend.length, 1);
  assert.equal(page.data.indicatorGroups.length, 2);
  assert.equal(page.data.homeRecommendations.recommended_indicators[0].code, "housing_price_mom");

  page.toggleFavoriteCity();
  assert.equal(page.data.favoriteCities[0].name, "北京");
  page.toggleFavoriteCombo();
  assert.equal(page.data.favoriteCombos[0].indicator_code, "housing_price_mom");

  page.goCityDetail();
  page.goTrendPage();
  page.goRankingPage();
  assert.deepEqual(wxMock.navigations, [
    "/pages/city/city?region_id=1&region_name=%E5%8C%97%E4%BA%AC",
    "/pages/trend/trend",
    "/pages/ranking/ranking",
  ]);

  await page.request("/mini/dashboard/overview");
  assert.equal(wxMock.requests.filter((item) => item === "/mini/dashboard/overview").length, 1);
});

test("trend and ranking pages load and switch core state", async () => {
  const trendPage = loadPage("pages/trend/trend.js", createWxMock(fixtures));
  await trendPage.loadBase();
  assert.equal(trendPage.data.trend[0].value, 101.2);
  trendPage.onIndicatorChange({ detail: { value: 1 } });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(trendPage.data.currentIndicator.code, "cpi_yoy");
  trendPage.onIndicatorChange({ detail: { value: 0 } });
  await new Promise((resolve) => setImmediate(resolve));
  trendPage.toggleCompareRegion({ detail: { value: 0 } });
  trendPage.toggleCompareRegion({ detail: { value: 1 } });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(trendPage.data.comparison.length, 2);

  const rankingPage = loadPage("pages/ranking/ranking.js", createWxMock(fixtures));
  await rankingPage.loadBase();
  assert.equal(rankingPage.data.rankings.top[0].region, "北京");
  rankingPage.switchMode({ currentTarget: { dataset: { mode: "bottom" } } });
  assert.equal(rankingPage.data.mode, "bottom");
});

test("city page loads indicator cards from route options", async () => {
  const cityPage = loadPage("pages/city/city.js", createWxMock(fixtures));
  await cityPage.onLoad({ region_id: "1", region_name: encodeURIComponent("北京") });

  assert.equal(cityPage.data.regionName, "北京");
  assert.equal(cityPage.data.cards.length, 1);
  assert.equal(cityPage.data.cards[0].latest.value, 101.2);
  assert.equal(cityPage.data.cards[0].indicator.display_name, "住宅价格环比");
});

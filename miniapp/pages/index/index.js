const app = getApp();

Page({
  data: {
    regions: [],
    indicators: [],
    currentRegion: {},
    currentIndicator: {},
    overview: {},
    latestValues: [],
    trend: [],
    rankings: { top: [], bottom: [] },
    cityKeyword: "",
    filteredRegions: [],
    favoriteCities: [],
    houseTypes: [
      { label: "全部住宅", value: "" },
      { label: "新建商品住宅", value: "new_house" },
      { label: "二手住宅", value: "second_hand" }
    ],
    areaTypes: [
      { label: "全部面积", value: "" },
      { label: "90㎡以下", value: "under_90" },
      { label: "90-144㎡", value: "between_90_144" },
      { label: "144㎡以上", value: "over_144" }
    ],
    currentHouseType: { label: "全部住宅", value: "" },
    currentAreaType: { label: "全部面积", value: "" },
    loading: false,
    error: ""
  },

  onLoad() {
    this.loadPage();
  },

  loadPage() {
    this.setData({ loading: true, error: "" });
    Promise.all([
      this.request("/mini/dashboard/overview"),
      this.request("/mini/regions"),
      this.request("/mini/indicators"),
      this.loadLatestValues(),
      this.loadRankings()
    ])
      .then(([overview, regions, indicators, latestValues, rankings]) => {
        const favoriteCities = wx.getStorageSync("favoriteCities") || [];
        this.setData({
          overview,
          regions,
          filteredRegions: regions,
          indicators,
          latestValues,
          rankings,
          favoriteCities,
          currentRegion: regions[0] || {},
          currentIndicator: indicators[0] || {}
        });
        return this.loadTrend();
      })
      .catch(() => {
        this.setData({ error: "数据加载失败，请稍后重试" });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },

  loadLatestValues() {
    const { currentIndicator, currentHouseType, currentAreaType } = this.data;
    const params = [`indicator_code=${currentIndicator.code || "housing_price_mom"}`];
    if (currentHouseType.value) params.push(`house_type=${currentHouseType.value}`);
    if (currentAreaType.value) params.push(`area_type=${currentAreaType.value}`);
    return this.request(`/mini/stat-values/latest?${params.join("&")}`);
  },

  loadRankings() {
    const { currentIndicator, currentHouseType, currentAreaType } = this.data;
    const params = [`indicator_code=${currentIndicator.code || "housing_price_mom"}`];
    if (currentHouseType.value) params.push(`house_type=${currentHouseType.value}`);
    if (currentAreaType.value) params.push(`area_type=${currentAreaType.value}`);
    return this.request(`/mini/rankings?${params.join("&")}`);
  },

  loadTrend() {
    const { currentRegion, currentIndicator, currentHouseType, currentAreaType } = this.data;
    if (!currentRegion.id || !currentIndicator.code) {
      this.setData({ trend: [] });
      return Promise.resolve();
    }
    const params = [
      `region_id=${currentRegion.id}`,
      `indicator_code=${currentIndicator.code}`
    ];
    if (currentHouseType.value) params.push(`house_type=${currentHouseType.value}`);
    if (currentAreaType.value) params.push(`area_type=${currentAreaType.value}`);
    const path = `/mini/stat-values/trend?${params.join("&")}`;
    return this.request(path).then((res) => {
      this.setData({ trend: res.items || [] });
    });
  },

  onRegionChange(event) {
    this.setData({ currentRegion: this.data.filteredRegions[event.detail.value], loading: true });
    this.loadTrend()
      .catch(() => this.setData({ error: "趋势数据加载失败" }))
      .finally(() => this.setData({ loading: false }));
  },

  onIndicatorChange(event) {
    const indicator = this.data.indicators[event.detail.value];
    this.setData({ currentIndicator: indicator, loading: true });
    Promise.all([
      this.loadTrend(),
      this.loadLatestValues().then((latestValues) => {
        this.setData({ latestValues });
      }),
      this.loadRankings().then((rankings) => {
        this.setData({ rankings });
      })
    ])
      .catch(() => this.setData({ error: "指标数据加载失败" }))
      .finally(() => this.setData({ loading: false }));
  },

  onHouseTypeChange(event) {
    this.setData({ currentHouseType: this.data.houseTypes[event.detail.value], loading: true });
    this.reloadDataForFilters();
  },

  onAreaTypeChange(event) {
    this.setData({ currentAreaType: this.data.areaTypes[event.detail.value], loading: true });
    this.reloadDataForFilters();
  },

  reloadDataForFilters() {
    Promise.all([
      this.loadTrend(),
      this.loadLatestValues().then((latestValues) => {
        this.setData({ latestValues });
      }),
      this.loadRankings().then((rankings) => {
        this.setData({ rankings });
      })
    ])
      .catch(() => this.setData({ error: "筛选数据加载失败" }))
      .finally(() => this.setData({ loading: false }));
  },

  onCitySearch(event) {
    const cityKeyword = event.detail.value;
    const filteredRegions = this.data.regions.filter((region) => region.name.indexOf(cityKeyword) >= 0);
    this.setData({
      cityKeyword,
      filteredRegions,
      currentRegion: filteredRegions[0] || {}
    });
    this.loadTrend().catch(() => this.setData({ error: "趋势数据加载失败" }));
  },

  toggleFavoriteCity() {
    const currentRegion = this.data.currentRegion;
    if (!currentRegion.id) return;
    const exists = this.data.favoriteCities.some((city) => city.id === currentRegion.id);
    const favoriteCities = exists
      ? this.data.favoriteCities.filter((city) => city.id !== currentRegion.id)
      : [currentRegion, ...this.data.favoriteCities].slice(0, 8);
    wx.setStorageSync("favoriteCities", favoriteCities);
    this.setData({ favoriteCities });
  },

  request(path) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${app.globalData.apiBase}${path}`,
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data);
          } else {
            reject(new Error(`HTTP ${res.statusCode}`));
          }
        },
        fail: reject
      });
    });
  }
});

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
      this.request("/mini/stat-values/latest")
    ])
      .then(([overview, regions, indicators, latestValues]) => {
        this.setData({
          overview,
          regions,
          indicators,
          latestValues,
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

  loadTrend() {
    const { currentRegion, currentIndicator } = this.data;
    if (!currentRegion.id || !currentIndicator.code) {
      this.setData({ trend: [] });
      return Promise.resolve();
    }
    const path = `/mini/stat-values/trend?region_id=${currentRegion.id}&indicator_code=${currentIndicator.code}`;
    return this.request(path).then((res) => {
      this.setData({ trend: res.items || [] });
    });
  },

  onRegionChange(event) {
    this.setData({ currentRegion: this.data.regions[event.detail.value], loading: true });
    this.loadTrend()
      .catch(() => this.setData({ error: "趋势数据加载失败" }))
      .finally(() => this.setData({ loading: false }));
  },

  onIndicatorChange(event) {
    const indicator = this.data.indicators[event.detail.value];
    this.setData({ currentIndicator: indicator, loading: true });
    Promise.all([
      this.loadTrend(),
      this.request(`/mini/stat-values/latest?indicator_code=${indicator.code}`).then((latestValues) => {
        this.setData({ latestValues });
      })
    ])
      .catch(() => this.setData({ error: "指标数据加载失败" }))
      .finally(() => this.setData({ loading: false }));
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

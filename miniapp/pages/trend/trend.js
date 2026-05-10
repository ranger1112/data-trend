const app = getApp();

Page({
  data: {
    regions: [],
    indicators: [],
    currentRegion: {},
    currentIndicator: {},
    trend: [],
    loading: false,
    error: ""
  },

  onLoad() {
    return this.loadBase();
  },

  loadBase() {
    this.setData({ loading: true, error: "" });
    return Promise.all([this.request("/mini/regions"), this.request("/mini/indicators")])
      .then(([regions, indicators]) => {
        this.setData({
          regions,
          indicators,
          currentRegion: regions[0] || {},
          currentIndicator: indicators[0] || {}
        });
        return this.loadTrend();
      })
      .catch(() => this.setData({ error: "趋势基础数据加载失败" }))
      .finally(() => this.setData({ loading: false }));
  },

  onRegionChange(event) {
    this.setData({ currentRegion: this.data.regions[event.detail.value] });
    this.loadTrend();
  },

  onIndicatorChange(event) {
    this.setData({ currentIndicator: this.data.indicators[event.detail.value] });
    this.loadTrend();
  },

  loadTrend() {
    const { currentRegion, currentIndicator } = this.data;
    if (!currentRegion.id || !currentIndicator.code) return Promise.resolve();
    this.setData({ loading: true });
    return this.request(
      `/mini/stat-values/trend?region_id=${currentRegion.id}&indicator_code=${currentIndicator.code}`
    )
      .then((res) => this.setData({ trend: res.items || [] }))
      .catch(() => this.setData({ error: "趋势数据加载失败" }))
      .finally(() => this.setData({ loading: false }));
  },

  request(path) {
    const cached = wx.getStorageSync(`cache:${path}`);
    if (cached && cached.expireAt > Date.now()) return Promise.resolve(cached.data);
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${app.globalData.apiBase}${path}`,
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            const ttl = res.data && res.data.cache_ttl_seconds;
            if (ttl) wx.setStorageSync(`cache:${path}`, { data: res.data, expireAt: Date.now() + ttl * 1000 });
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

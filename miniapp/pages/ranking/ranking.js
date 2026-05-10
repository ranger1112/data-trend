const app = getApp();

Page({
  data: {
    indicators: [],
    currentIndicator: {},
    mode: "top",
    rankings: { top: [], bottom: [] },
    loading: false,
    error: ""
  },

  onLoad() {
    return this.loadBase();
  },

  loadBase() {
    this.setData({ loading: true, error: "" });
    return this.request("/mini/indicators")
      .then((indicators) => {
        this.setData({ indicators, currentIndicator: indicators[0] || {} });
        return this.loadRankings();
      })
      .catch(() => this.setData({ error: "排行榜加载失败" }))
      .finally(() => this.setData({ loading: false }));
  },

  onIndicatorChange(event) {
    this.setData({ currentIndicator: this.data.indicators[event.detail.value] });
    this.loadRankings();
  },

  switchMode(event) {
    this.setData({ mode: event.currentTarget.dataset.mode });
  },

  loadRankings() {
    if (!this.data.currentIndicator.code) return Promise.resolve();
    this.setData({ loading: true });
    return this.request(`/mini/rankings?indicator_code=${this.data.currentIndicator.code}`)
      .then((rankings) => this.setData({ rankings }))
      .catch(() => this.setData({ error: "排行榜数据加载失败" }))
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

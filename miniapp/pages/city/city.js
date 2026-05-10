const app = getApp();

Page({
  data: {
    regionId: "",
    regionName: "",
    region: {},
    cards: [],
    loading: false,
    error: ""
  },

  onLoad(options) {
    this.setData({
      regionId: options.region_id || "",
      regionName: decodeURIComponent(options.region_name || "城市详情")
    });
    return this.loadPage();
  },

  loadPage() {
    this.setData({ loading: true, error: "" });
    return this.request(`/mini/regions/${this.data.regionId}/detail`)
      .then((detail) => {
        this.setData({
          region: detail.region || {},
          regionName: (detail.region && detail.region.name) || this.data.regionName,
          cards: (detail.indicator_cards || []).map((card) => ({
            indicator: card.indicator,
            latest: card,
            points: []
          }))
        });
      })
      .catch(() => this.setData({ error: "城市数据加载失败" }))
      .finally(() => this.setData({ loading: false }));
  },

  request(path) {
    const cached = wx.getStorageSync(`cache:${path}`);
    if (cached && cached.expireAt > Date.now()) {
      return Promise.resolve(cached.data);
    }
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${app.globalData.apiBase}${path}`,
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            const ttl = res.data && res.data.cache_ttl_seconds;
            if (ttl) {
              wx.setStorageSync(`cache:${path}`, {
                data: res.data,
                expireAt: Date.now() + ttl * 1000
              });
            }
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

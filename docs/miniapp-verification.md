# 小程序验证说明

## 已完成的静态与接口验证

- 小程序页面已登记在 `miniapp/app.json`：
  - `pages/index/index`
  - `pages/city/city`
  - `pages/trend/trend`
  - `pages/ranking/ranking`
- 已补充 `miniapp/project.config.json`，用于微信开发者工具识别项目。
- 后端接口测试覆盖：
  - 首页概览。
  - 最新值。
  - 趋势。
  - 排行。
  - CPI 第二数据源指标查询。
- 小程序静态检查已通过：
  - 所有 `miniapp/**/*.json` 均可被 JSON parser 解析。
  - 所有 `miniapp/**/*.js` 均通过 `node --check`。
- 小程序页面交互 smoke test 已补充：
  - `node --test miniapp/tests/page-smoke.test.js`
  - 覆盖首页加载、接口缓存、收藏城市、页面跳转、趋势页切换、排行榜切换和城市详情加载。
  - 该测试使用 Node mock `wx`/`Page`/`getApp`，只能证明页面交互代码路径可执行，不能替代真实设备或微信开发者工具验收。

## 本机开发者工具验证阻塞

本机存在微信开发者工具 CLI：

`C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat`

已尝试：

```powershell
cli.bat preview --project D:\Code\data-trend\miniapp --disable-gpu
cli.bat auto --project D:\Code\data-trend\miniapp --trust-project --disable-gpu
cli.bat open --project D:\Code\data-trend\miniapp --port 18342 --disable-gpu
node.exe code\package.nw\js\common\cli\index.js preview --project D:\Code\data-trend\miniapp --disable-gpu
wechatdevtools.exe --project D:\Code\data-trend\miniapp --remote-debugging-port=18343 --disable-gpu
cli.bat islogin --port 18344 --disable-gpu
cli.bat quit --port 18344 --disable-gpu
cli.bat preview --project D:\Code\data-trend\miniapp --disable-gpu --qr-format terminal --info-output D:\Code\data-trend\.tools\miniapp-preview-info.json
```

结果：外层和内层 `preview`、`auto` 在 124 秒后超时，`open` 在 64 秒后超时。直接启动 `wechatdevtools.exe` 可以拉起开发者工具进程，并能看到 `127.0.0.1:18343` 监听，但该端口是 remote debugging 参数，不是可用的 CLI HTTP service；访问 `/json/version`、`/json/list` 和 `/` 均被拒绝。按 `cli.bat --help` 使用 `--port 18344` 启动 HTTP service 后，`islogin` 仍在 64 秒后超时，`quit --port 18344` 同样超时。再次检查后未发现 `18342`、`18343`、`18344`、`18345` 监听，CLI preview 无法产出 `info-output`，因此没有可用的编译/预览结果。`launch.log` 路径可定位，但近期文件为空。

当前判断：阻塞点在本机微信开发者工具 CLI/自动化服务未正常响应，不能作为小程序代码缺陷处理。

## 手工验收清单

在微信开发者工具中打开 `miniapp` 目录后，检查：

1. 首页可以加载概览、城市、指标、最新值、趋势和排行。
2. 首页可以跳转城市详情、趋势分析和排行榜。
3. 城市详情页能展示当前城市的多个指标卡片。
4. 趋势页可以切换城市和指标。
5. 排行页可以切换指标和 top/bottom。
6. 网络失败时页面显示错误态。
7. 无数据时页面显示空态。
8. 重复打开页面时缓存不破坏数据刷新。

完成手工验收后，可将本文件中的阻塞状态更新为已验证。

## 验收记录模板

完成真实设备或微信开发者工具验收后，按下面格式补充记录：

```text
验收时间：
验收环境：微信开发者工具 / 真机设备
验收人：
项目路径：D:\Code\data-trend\miniapp
后端 API 地址：

结果：
- [ ] 首页加载概览、城市、指标、最新值、趋势和排行。
- [ ] 首页跳转城市详情、趋势分析和排行榜。
- [ ] 城市详情页展示当前城市的多个指标卡片。
- [ ] 趋势页切换城市和指标。
- [ ] 排行页切换指标和 top/bottom。
- [ ] 网络失败时显示错误态。
- [ ] 无数据时显示空态。
- [ ] 重复打开页面时缓存不破坏数据刷新。

结论：通过 / 不通过
问题记录：
```

## 开发者工具验证辅助命令

如果微信开发者工具已登录、已信任项目且 CLI/服务端口可用，可以运行：

```powershell
.\scripts\verify-miniapp-devtools.ps1
```

脚本会执行：

1. `cli.bat islogin --port 18344 --disable-gpu`
2. `cli.bat preview --project miniapp --port 18344 --disable-gpu --qr-format terminal --info-output .tools\miniapp-preview-info.json`
3. 输出 `.tools\miniapp-preview-info.json` 内容作为开发者工具预览证据。

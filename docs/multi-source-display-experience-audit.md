# 多数据源接入与展示体验实施审计

## 审计目标

对 `docs/multi-source-display-experience-plan.md` 的四个工作项做实施核对：

1. 接入第二个真实数据源。
2. 管理端数据源配置产品化。
3. 小程序页面从 MVP 变成可用展示。
4. 数据质量规则升级。

## 工作项一：第二真实数据源

状态：已实现。

证据：

- CPI 数据源已实现于 `packages/crawler/cpi/`。
- `packages/domain/constants.py` 已新增 `CPI_SOURCE_TYPE` 和 `cpi_yoy`、`cpi_mom`、`cpi_avg` 指标。
- `packages/pipeline/importers.py` 提供 importer registry，CPI importer 已注册。
- `apps/api/routers/admin.py` 提供 `/admin/data-source-types`，测试确认返回 `cpi`。
- `tests/test_cpi_importer.py` 覆盖 CPI parser、importer、统一统计值写入和质量报告。
- `tests/test_admin_api.py` 覆盖 mini API 查询 CPI 最新值和排行。

## 工作项二：管理端数据源配置产品化

状态：已实现。

证据：

- 管理端数据源类型使用 `/admin/data-source-types` 下拉。
- 管理端提供 CPI 和房价模板。
- `/admin/data-sources/health` 汇总数据源最近任务状态、错误类型和成功率。
- 管理端展示数据源健康状态、任务调度、取消任务和质量报告。
- 停用数据源、停用调度、取消任务均有确认提示。
- `admin-web` 构建通过。

## 工作项三：小程序展示

状态：代码侧已实现，真实设备或微信开发者工具验收未完成。

证据：

- `miniapp/app.json` 已登记：
  - `pages/index/index`
  - `pages/city/city`
  - `pages/trend/trend`
  - `pages/ranking/ranking`
- 首页支持概览、城市、指标、最新值、趋势、排行、收藏城市和页面跳转。
- 城市详情、趋势分析、排行榜页面已实现。
- 请求层使用接口返回的 `cache_ttl_seconds`。
- `miniapp/tests/page-smoke.test.js` 使用 Node mock `wx`/`Page`/`getApp` 覆盖主要交互代码路径。
- 静态检查覆盖所有小程序 JSON 和 JS。

阻塞：

- 计划要求“小程序端主要交互完成真实设备或开发者工具验证”。
- 本机微信开发者工具 CLI/HTTP service 多次超时，无法生成 preview 或 `info-output`。
- 详细阻塞记录见 `docs/miniapp-verification.md`。
- `scripts/verify-miniapp-devtools.ps1` 已提供可复用的开发者工具 preview 验证命令，待微信开发者工具登录、信任项目且 CLI 服务可用后执行。

## 工作项四：数据质量规则升级

状态：已实现。

证据：

- `packages/pipeline/quality.py` 已提供按 `source_type` 选择的 `QUALITY_RULES`。
- 房价和 CPI 使用不同区域数、指标数、维度、数值范围和 warning 阈值。
- 质量报告区分 `errors` 和 `warnings`。
- `quality_failed` 数据不会进入发布结果，mini API 排行只使用 published 数据。
- `quality_reports.details` 记录规则、严重等级、指标、区域、周期、数值和维度。
- `migrations/versions/20260510_0003_quality_report_details.py` 补充质量明细字段迁移。
- `tests/test_admin_api.py::test_quality_report_details_locate_failed_values` 覆盖明细定位。

## 已运行验证

- `.\scripts\verify-multi-source-display.ps1`：统一执行本阶段自动化验证。
- `.\scripts\verify-miniapp-devtools.ps1`：用于生成微信开发者工具 preview 证据；当前环境因 CLI 服务超时未能完成。
- `.\.venv\Scripts\python.exe -m pytest`：21 passed。
- `.\.venv\Scripts\python.exe -m ruff check apps packages tests migrations`：passed。
- `cd admin-web; npm run build`：passed。
- `node --test miniapp/tests/page-smoke.test.js`：3 passed。
- 小程序 JSON parse 和 JS `node --check`：passed。
- Alembic `upgrade head` / `current`：已验证到 `20260510_0003`。

## 结论

计划的代码实现、自动化测试和文档同步已完成。唯一未满足的验收项是小程序真实设备或微信开发者工具验证；该项需要在可用的微信开发者工具环境中手工完成，或由项目负责人明确放宽验收标准。

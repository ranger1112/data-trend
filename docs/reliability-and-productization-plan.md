# 管理与采集可靠性增强计划

## 背景

项目已经完成部署基线、worker loop、运行监控和数据库迁移规范化。下一阶段应从“能稳定跑”推进到“可安全管理、可扩展采集、可支撑小程序产品化展示”。

本阶段围绕四个方向展开：

1. 管理端认证与权限。
2. 采集任务可靠性。
3. 数据源扩展机制。
4. 小程序展示 API 固化。

## 阶段目标

- 管理端操作具备基础身份认证和权限边界。
- 采集任务失败可重试、卡住可恢复、异常可追踪。
- 新增数据源时不需要复制整套 housing price 逻辑。
- 小程序端接口契约稳定，便于后续页面迭代和缓存优化。

## 工作项一：管理端认证与权限

### 目标

为管理端和 `/admin/*` API 增加基础访问控制，避免部署后任何人都能触发采集、审核发布或查看运维状态。

### 实施内容

- 新增管理员账号模型或最小可用的配置型管理员凭据。
- 新增登录接口，返回访问 token。
- 为 `/admin/*` API 增加鉴权依赖。
- 管理端增加登录页和 token 保存逻辑。
- 区分基础权限：
  - `readonly`：只能查看数据、任务和监控状态。
  - `reviewer`：可以审核、发布、驳回数据。
  - `operator`：可以触发采集、修改数据源、管理调度。
- 对高风险操作增加权限校验，例如发布、驳回、取消任务、修改调度。

### 建议交付物

- `apps/api/security.py`
- `apps/api/routers/auth.py`
- `packages/storage/models.py` 中的管理员或 token 相关模型
- 管理端登录视图与 API request 鉴权封装
- `docs/auth.md`

### 验收标准

- 未登录访问 `/admin/*` 返回 401。
- 登录成功后可访问对应权限范围内的接口。
- 低权限账号无法执行发布、调度修改等高风险操作。
- 管理端刷新后仍能维持登录态。
- 测试覆盖登录、未授权、权限不足和正常访问路径。

## 工作项二：采集任务可靠性

### 目标

提升 worker 长期运行时的自恢复能力，避免网络抖动、进程重启或异常退出导致任务永久卡住。

### 实施内容

- 为 `crawl_jobs` 增加重试策略字段：
  - `max_retries`
  - `next_retry_at`
  - `timeout_seconds`
  - `locked_at`
  - `locked_by`
- worker 执行任务前写入锁信息，结束后释放或写入终态。
- 对 `running` 超时任务执行 stale recovery，标记为 failed 或重新排队。
- 失败任务按错误类型决定是否自动重试。
- 增加最大重试次数，避免无限失败循环。
- 对单个任务增加执行超时控制。
- 继续保留同一 target 的 active job 保护，避免同一 schedule 并发执行。
- 结构化日志补充 retry、lock、timeout、recovery 字段。

### 建议交付物

- `packages/pipeline/scheduler.py` 调度与重试策略
- `apps/worker/run_housing_price_import.py` worker 执行锁和超时逻辑
- migration：新增任务可靠性字段
- worker 单元测试与集成测试
- `docs/worker-reliability.md`

### 验收标准

- 失败任务在未超过最大重试次数时会进入下一次重试。
- 超过最大重试次数后任务进入最终 failed 状态。
- 超时 running 任务不会永久卡住。
- worker 重启后可以继续处理可恢复任务。
- 同一 schedule 不会并发创建多个 active job。

## 工作项三：数据源扩展机制

### 目标

把当前 housing price 专用导入链路抽象为可注册的数据源类型，后续新增统计数据源时只需要实现对应 crawler/importer。

### 实施内容

- 定义 crawler/importer 统一接口。
- 新增 importer registry，根据 `data_source.type` 路由到对应导入器。
- 将 housing price 导入器注册为 `housing_price`。
- 调整管理端数据源配置，明确数据源类型、入口 URL、调度策略。
- 为不同数据源保留独立质量校验策略。
- 新增不支持类型的错误处理和可观测日志。

### 建议交付物

- `packages/pipeline/importers.py`
- `packages/crawler/housing_price` 注册适配
- `packages/pipeline/quality.py` 支持按数据源类型选择校验器
- 管理端数据源类型配置优化
- `docs/data-source-extension.md`

### 验收标准

- housing price 仍按原行为正常采集。
- 新增一个示例 importer 不需要改 worker 主流程。
- 不支持的数据源类型会给出明确错误。
- 管理端可以看到数据源类型和调度策略。
- 测试覆盖 registry 路由、未知类型、housing price 兼容路径。

## 工作项四：小程序展示 API 固化

### 目标

稳定小程序端接口契约，明确首页、趋势页、排行页所需数据结构，降低后续页面迭代时的接口变更风险。

### 实施内容

- 梳理小程序当前页面所需接口。
- 明确核心 API：
  - 首页概览。
  - 城市列表。
  - 指标列表。
  - 最新指标值。
  - 趋势数据。
  - 排行数据。
- 为列表接口补充分页参数。
- 为筛选项补充稳定字段，例如 `house_type`、`area_type`、`period`。
- 增加缓存友好字段，例如 `updated_at`、`latest_period`、`cache_ttl_seconds`。
- 输出小程序 API 文档。
- 补充小程序端错误态和空态处理约定。

### 建议交付物

- `docs/miniapp-api.md`
- `apps/api/routers/mini.py` 契约整理
- `apps/api/schemas.py` 小程序响应模型
- 小程序端请求层与页面字段适配
- mini API 测试

### 验收标准

- `docs/miniapp-api.md` 覆盖小程序首页、趋势页、排行页接口。
- 小程序端不直接依赖临时字段或后端内部模型。
- API 返回结构具备稳定 schema。
- 分页、筛选、空数据都有明确响应。
- 测试覆盖主要展示接口。

## 推荐里程碑

### 里程碑一：安全管理入口

优先完成管理端认证与权限。

交付物：

- 登录接口与登录页
- `/admin/*` 鉴权
- 基础角色权限
- 鉴权测试

### 里程碑二：稳定采集执行

在管理入口具备权限后，增强 worker 任务可靠性。

交付物：

- retry 字段 migration
- stale job recovery
- worker 锁和超时
- worker 可靠性测试

### 里程碑三：采集能力扩展

在 worker 稳定后抽象数据源扩展机制。

交付物：

- importer registry
- housing price 适配迁移
- 数据源类型配置
- registry 测试

### 里程碑四：展示契约固化

最后固化小程序 API，避免展示端继续跟后端内部结构耦合。

交付物：

- `docs/miniapp-api.md`
- mini API schema
- 小程序端字段适配
- mini API 测试

## 推荐执行顺序

1. 管理端认证与权限。
2. 采集任务可靠性。
3. 数据源扩展机制。
4. 小程序展示 API 固化。

优先级理由：先保护管理入口，再提升长期运行可靠性；采集扩展依赖稳定 worker；小程序 API 固化放在最后，可以吸收前面数据源类型和展示字段的调整。

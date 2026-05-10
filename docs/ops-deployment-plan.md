# 部署与运行监控计划

## 背景

当前项目已经具备数据抓取、质量校验、审核发布和小程序展示闭环。下一阶段需要把系统从“开发机可运行”推进到“可部署、可观测、可恢复”的运行形态，降低人工启动和排障成本。

## 阶段目标

本阶段围绕部署基线、调度守护、运行监控和数据库迁移规范化展开。

成功标准：

- 项目可以用统一命令启动 API、worker 和数据库依赖。
- 调度任务可以长期运行，不依赖人工反复执行 CLI。
- 管理端或 API 可以快速看到任务失败、质量异常和待审核积压。
- 数据库结构变更有明确迁移流程，后续可以平滑迁到 PostgreSQL。

## 工作项一：服务部署基线

### 目标

为项目建立最小可用的部署基线，让本地、测试环境和后续服务器环境使用同一套启动约定。

### 实施内容

- 新增 `.env.example`，列出 API、数据库、CORS、worker 间隔等环境变量。
- 新增 `docker-compose.yml`，至少包含：
  - `api`：FastAPI 服务。
  - `worker`：调度 worker。
  - `db`：优先预留 PostgreSQL；如本阶段继续 SQLite，需要明确 volume 持久化位置。
- 新增 `Dockerfile` 或拆分 `apps/api`、`apps/worker` 共用镜像构建方式。
- 明确数据库初始化命令，例如 bootstrap 或 migration。
- 明确前端管理端构建和部署方式。
- 在 `docs/` 中补充部署说明，包括本地启动、生产启动、常见故障处理。

### 建议文件

- `.env.example`
- `Dockerfile`
- `docker-compose.yml`
- `docs/deployment.md`

### 验收标准

- 执行一条命令可以启动 API 和 worker。
- 新环境可以根据 `.env.example` 配置必要变量。
- API `/health` 可访问。
- worker 能连接数据库并执行到期调度扫描。
- 数据库文件或 PostgreSQL volume 不会因为容器重建丢失。

## 工作项二：调度运行守护

### 目标

把当前 `--run-due` 手动执行模式升级为长期运行的 worker loop，让调度中心具备持续执行能力。

### 实施内容

- 为 worker 增加 loop 模式，例如 `--loop`。
- 支持通过环境变量设置轮询间隔，例如 `WORKER_POLL_SECONDS=60`。
- 每轮执行：
  - 查询到期调度。
  - 创建到期任务。
  - 执行抓取。
  - 写入任务结果和质量报告。
- 捕获单个任务异常，避免一个调度失败导致整个 worker 退出。
- 支持优雅退出，处理 `SIGINT`、`SIGTERM`。
- 输出结构化日志，至少包含 job id、schedule id、target URL、status、error type。
- 防止重复执行同一调度，继续复用 active job 保护。

### 建议命令

```bash
python -m apps.worker.run_housing_price_import --run-due
python -m apps.worker.run_housing_price_import --loop
```

### 验收标准

- worker loop 可以持续运行多轮。
- 同一调度在已有 pending/running job 时不会重复创建任务。
- 单个任务失败后，worker 仍会继续下一轮扫描。
- 退出信号可以让 worker 正常停止。
- 日志能定位到失败任务和失败原因。

## 工作项三：运行监控与告警

### 目标

让系统运行状态可以被快速观察，优先覆盖失败任务、质量异常、待审核积压和调度健康。

### 实施内容

- 新增运行状态汇总接口，例如 `GET /admin/ops/summary`。
- 汇总指标包括：
  - 最近 24 小时任务数。
  - 最近 24 小时失败任务数。
  - 当前 pending/running 任务数。
  - 质量失败报告数。
  - 待审核数据量。
  - 最近一次成功抓取时间。
  - 下一个待运行调度时间。
- 管理端首页突出异常状态，例如失败任务、质量失败、待审核积压。
- 增加日志文件输出或 stdout 结构化日志约定。
- 预留 webhook 告警配置，例如任务连续失败、质量校验失败、worker 心跳超时。

### 建议接口

- `GET /admin/ops/summary`
- `GET /admin/ops/recent-failures`
- `POST /admin/ops/test-alert`，可选，用于验证告警配置。

### 验收标准

- 管理端首页可以看到运行状态摘要。
- API 能返回失败任务数、质量失败数和待审核数量。
- 最近一次成功抓取和下一次调度时间可见。
- 异常状态不需要查数据库就能定位。
- 告警配置即使暂不接真实渠道，也应有清晰扩展点。

## 工作项四：数据库迁移规范化

### 目标

把当前轻量 SQLite schema upgrade 过渡为可审计、可回滚、可持续演进的迁移体系。

### 实施内容

- 引入 Alembic。
- 初始化 `alembic.ini` 和 `migrations/` 目录。
- 把当前 SQLAlchemy 模型作为 migration autogenerate 的元数据来源。
- 为已有模型生成首个 baseline migration。
- 为后续新增表和字段生成显式 migration。
- 增加迁移执行命令文档。
- 在部署流程中明确先迁移数据库，再启动 API 和 worker。
- 评估 SQLite 到 PostgreSQL 的类型兼容性，尤其是 JSON、DateTime 和约束。

### 建议命令

```bash
alembic revision --autogenerate -m "baseline"
alembic upgrade head
alembic downgrade -1
```

### 验收标准

- 新库可以通过 `alembic upgrade head` 创建完整结构。
- 旧库可以通过迁移补齐新增字段和表。
- CI 或本地验证可以执行 migration 检查。
- 文档明确 SQLite 与 PostgreSQL 的差异和迁移注意事项。

## 推荐里程碑

### 里程碑一：可部署运行

优先完成部署基线和 worker loop。

交付物：

- `.env.example`
- `Dockerfile`
- `docker-compose.yml`
- worker `--loop`
- `docs/deployment.md`

### 里程碑二：可观测运行

在服务可以稳定启动后补监控入口。

交付物：

- `/admin/ops/summary`
- 管理端运行状态卡片
- 结构化日志字段约定
- 告警扩展点

### 里程碑三：迁移规范化

在部署和运行形态稳定后引入 Alembic。

交付物：

- Alembic 配置
- baseline migration
- migration 文档
- SQLite/PostgreSQL 兼容性说明

## 风险与注意事项

- 不要一开始把部署方案做得过重；先保证单机 Docker Compose 可运行，再考虑 Kubernetes 或云服务。
- worker loop 必须有异常隔离，否则一次网络错误会导致调度停止。
- 监控指标要从真实数据库聚合，不要只做前端展示假数据。
- Alembic 引入后，要避免继续在代码里随意写 schema upgrade；临时兼容逻辑应逐步收敛。
- 如果准备切 PostgreSQL，需要提前验证 JSON 字段、唯一约束和时区行为。

## 推荐执行顺序

1. 服务部署基线。
2. 调度运行守护。
3. 运行监控与告警。
4. 数据库迁移规范化。

优先级理由：先让系统有稳定启动和长期运行方式，再补监控；迁移规范化放在最后，是为了避免在运行方式未定时反复调整 migration。

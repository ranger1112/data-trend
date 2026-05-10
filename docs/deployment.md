# 部署说明

## 环境变量

复制 `.env.example` 为 `.env` 后按环境调整：

- `DATA_TREND_DATABASE_URL`：数据库连接，默认示例为 SQLite，Docker Compose 使用 PostgreSQL。
- `DATA_TREND_CORS_ORIGINS`：允许访问 API 的管理端来源。
- `DATA_TREND_WORKER_POLL_SECONDS`：worker loop 轮询间隔，默认 60 秒。
- `DATA_TREND_ALERT_WEBHOOK_URL`：告警 webhook 预留配置，未配置时 `/admin/ops/test-alert` 会返回未启用。
- `VITE_API_BASE`：管理端构建或开发时访问的 API 地址。

## 本地开发启动

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn apps.api.main:app --reload
```

管理端：

```bash
cd admin-web
npm install
npm run dev
```

管理端生产构建：

```bash
cd admin-web
npm install
npm run build
```

构建产物位于 `admin-web/dist`，可部署到 Nginx、对象存储静态网站或其他静态资源服务。部署前设置 `VITE_API_BASE` 指向 API 地址；如果运行时域名不同步，需要同步调整 `DATA_TREND_CORS_ORIGINS`。

worker 手动执行到期调度：

```bash
python -m apps.worker.run_housing_price_import --run-due
```

worker 长期守护：

```bash
python -m apps.worker.run_housing_price_import --loop
```

## Docker Compose 启动

```bash
docker compose up --build
```

该命令会启动：

- `db`：PostgreSQL 16，数据保存在 `postgres-data` volume。
- `api`：先执行 `alembic upgrade head`，再启动 FastAPI。
- `worker`：先执行 `alembic upgrade head`，再以 `--loop` 模式持续扫描到期调度。

启动后检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/admin/ops/summary
```

## 数据库迁移

新库初始化：

```bash
alembic upgrade head
```

生成后续迁移：

```bash
alembic revision --autogenerate -m "describe change"
```

回滚上一版：

```bash
alembic downgrade -1
```

部署顺序固定为：

1. 备份数据库。
2. 执行 `alembic upgrade head`。
3. 启动或重启 API。
4. 启动或重启 worker。
5. 检查 `/health` 和 `/admin/ops/summary`。

## SQLite 与 PostgreSQL 注意事项

- SQLite 适合本地开发；生产建议使用 PostgreSQL。
- JSON 字段使用 SQLAlchemy 通用 `JSON` 类型，PostgreSQL 会映射为原生 JSON 能力。
- DateTime 当前以应用侧 UTC 写入，跨时区展示应在前端或接口层统一转换。
- `stat_values.dimensions` 不建立数据库唯一约束，幂等逻辑由 repository 根据 `region_id`、`indicator_id`、`period` 和 `dimensions` 判断。
- 切换到 PostgreSQL 前，先在空库执行 `alembic upgrade head`，再跑 `python -m pytest`。

## 运行监控

管理端首页会读取 `/admin/ops/summary`，覆盖：

- 最近 24 小时任务数。
- 最近 24 小时失败任务数。
- pending/running 任务数。
- 质量失败报告数。
- 待审核数据量。
- 最近一次成功抓取时间。
- 下一次调度时间。

最近失败任务：

```bash
curl http://127.0.0.1:8000/admin/ops/recent-failures
```

告警配置自检：

```bash
curl -X POST http://127.0.0.1:8000/admin/ops/test-alert
```

## 常见故障

API 无法连接数据库：

- 检查 `DATA_TREND_DATABASE_URL`。
- Docker Compose 下确认 `db` healthcheck 已通过。
- 先执行 `alembic upgrade head`。

worker 没有执行任务：

- 确认存在 enabled schedule 且 `next_run_at` 已到期。
- 检查是否已有同 target 的 pending/running job。
- 查看 worker stdout JSON 日志中的 `due_jobs_created` 和 `job_finished`。

管理端看不到接口数据：

- 检查 `VITE_API_BASE` 是否指向当前 API。
- 检查 `DATA_TREND_CORS_ORIGINS` 是否包含管理端地址。

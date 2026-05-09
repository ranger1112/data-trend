# data-trend

数据趋势平台，面向政府统计数据的抓取、管理和展示。

## 模块

- `apps/api`: FastAPI 服务，提供管理端 API 和微信小程序展示 API。
- `apps/worker`: 抓取任务入口，供命令行或后续队列 worker 调用。
- `packages/crawler`: 数据源抓取、HTML 解析、标准化、导入。
- `packages/domain`: 领域常量与 DTO。
- `packages/storage`: SQLAlchemy 数据库模型、会话和仓储。
- `admin-web`: Web 管理端，可配置数据源、触发采集、查看任务、审核发布数据。
- `miniapp`: 微信小程序展示端，展示已发布的城市指标趋势和最新数据。

## 本地运行

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m apps.api.bootstrap
uvicorn apps.api.main:app --reload
```

默认使用 SQLite：`sqlite:///./data-trend.db`。可通过 `DATA_TREND_DATABASE_URL` 覆盖。

管理端：

```bash
cd admin-web
npm install
npm run dev
```

小程序端默认请求 `http://127.0.0.1:8000`，可在 `miniapp/app.js` 修改 `apiBase`。

## 抓取命令

```bash
python -m apps.worker.run_housing_price_import --url https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963320.html
```

也可以在管理端新增数据源后触发采集任务。API 会先创建 `pending` 任务，再通过 FastAPI
`BackgroundTasks` 后台执行抓取，任务状态会更新为 `running`、`success` 或 `failed`。

## 验证

```bash
python -m pytest
cd admin-web
npm run build
```

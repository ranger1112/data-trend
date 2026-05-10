# 数据源扩展机制

采集执行通过 importer registry 按 `data_sources.type` 路由。

## 已注册类型

- `housing_price`：国家统计局房价指数采集链路。

## 新增数据源

1. 实现 runner，方法签名保持：

```python
def run(self, url: str, job: CrawlJob | None = None, data_source: DataSource | None = None) -> CrawlJob:
    ...
```

2. 在模块加载时注册：

```python
register_importer("new_type", NewImportRunner)
```

3. 管理端创建数据源时填写对应 `type`。

worker 和管理端后台任务不需要改主流程。未知类型会把任务标记为 `unsupported_data_source_type`。

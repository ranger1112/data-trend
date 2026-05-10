# 采集任务可靠性

worker 现在对 `crawl_jobs` 增加锁、超时恢复和有限重试。

## 字段

- `max_retries`：最大自动重试次数。
- `next_retry_at`：下一次可重试时间。
- `timeout_seconds`：运行锁超时时间。
- `locked_at`：当前锁定时间。
- `locked_by`：当前执行 worker 标识。

## 执行流程

1. 每轮先恢复超时 `running` 任务。
2. 创建到期调度任务。
3. 拉取到期的 retryable failed 任务。
4. 执行前写入 `locked_at` 和 `locked_by`。
5. 成功后清锁；失败后按错误类型和次数决定是否写入 `next_retry_at`。

自动重试只覆盖网络、导入异常、worker 异常和超时；不支持的数据源类型会直接失败，不进入自动重试。

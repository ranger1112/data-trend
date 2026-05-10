# CPI 数据源接入说明

本阶段新增第二个真实数据源类型：`cpi`。

## 默认入口

示例入口使用国家统计局 CPI 发布稿：

`https://www.stats.gov.cn/sj/zxfb/202604/t20260413_1963263.html`

## 采集链路

- parser：`packages/crawler/cpi/parser.py`
- importer：`packages/crawler/cpi/importer.py`
- registry type：`cpi`
- 质量规则：`packages/pipeline/quality.py` 中的 `QUALITY_RULES["cpi"]`

## 指标

- `cpi_yoy`：居民消费价格同比。
- `cpi_mom`：居民消费价格环比。
- `cpi_avg`：居民消费价格累计平均同比。

## 维度

CPI 当前写入两个稳定维度：

- `source_type=cpi`
- `frequency=monthly`

## 验证路径

1. 管理端创建 `type=cpi` 的数据源。
2. 手动触发采集任务。
3. 任务成功后生成全国区域和 CPI 指标值。
4. 质量报告按 CPI 规则校验。
5. 小程序 API 可通过 `indicator_code=cpi_yoy` 查询最新值、趋势和排行。

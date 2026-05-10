# 小程序展示 API

小程序接口统一在 `/mini` 前缀下，返回稳定 schema，并带缓存辅助字段。

## 首页概览

`GET /mini/dashboard/overview`

返回：

- `regions`
- `indicators`
- `published_values`
- `latest_period`
- `updated_at`
- `cache_ttl_seconds`

## 城市列表

`GET /mini/regions`

返回城市数组：`id`、`name`、`normalized_name`、`level`。

## 指标列表

`GET /mini/indicators`

返回指标数组：`id`、`code`、`name`、`unit`、`description`。

## 最新指标值

`GET /mini/stat-values/latest?indicator_code=housing_price_mom&house_type=new_house&area_type=none`

返回：

- `items`：城市最新值列表。
- `latest_period`
- `updated_at`
- `cache_ttl_seconds`

## 趋势数据

`GET /mini/stat-values/trend?region_id=1&indicator_code=housing_price_mom&house_type=new_house&area_type=none`

返回：

- `region_id`
- `indicator_code`
- `items`
- `updated_at`
- `cache_ttl_seconds`

## 排行数据

`GET /mini/rankings?indicator_code=housing_price_mom&house_type=new_house&area_type=none&limit=10`

返回：

- `top`
- `bottom`
- `latest_period`
- `updated_at`
- `cache_ttl_seconds`

空数据时 `items`、`top`、`bottom` 返回空数组，分页类参数后续按同一 wrapper 扩展。

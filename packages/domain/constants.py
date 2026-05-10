HOUSING_PRICE_SOURCE_TYPE = "housing_price"
CPI_SOURCE_TYPE = "cpi"

INDICATORS = {
    "housing_price_mom": "住宅销售价格环比",
    "housing_price_yoy": "住宅销售价格同比",
    "housing_price_ytd": "住宅销售价格定基/累计平均",
    "cpi_yoy": "居民消费价格同比",
    "cpi_mom": "居民消费价格环比",
    "cpi_avg": "居民消费价格累计平均同比",
}

INDICATOR_METADATA = {
    "housing_price_mom": {
        "category": "housing_price",
        "display_name": "住宅价格环比",
        "unit": "%",
        "description": "住宅销售价格较上月变化幅度。",
        "methodology": "按国家统计局住宅销售价格指数口径，比较本月与上月价格水平变化。",
        "update_frequency": "月度",
        "usage_scenario": "适合观察城市住宅价格短期变化和市场热度。",
        "caveats": "环比更敏感，单月波动不宜直接解释为长期趋势。",
        "precision": 2,
        "sort_order": 10,
        "default_dimensions": {"house_type": "new_house", "area_type": "none"},
    },
    "housing_price_yoy": {
        "category": "housing_price",
        "display_name": "住宅价格同比",
        "unit": "%",
        "description": "住宅销售价格较上年同期变化幅度。",
        "methodology": "按国家统计局住宅销售价格指数口径，比较本月与上年同月价格水平变化。",
        "update_frequency": "月度",
        "usage_scenario": "适合观察城市住宅价格年度变化和长期方向。",
        "caveats": "同比受去年同期基数影响，需结合环比一起判断。",
        "precision": 2,
        "sort_order": 20,
        "default_dimensions": {"house_type": "new_house", "area_type": "none"},
    },
    "housing_price_ytd": {
        "category": "housing_price",
        "display_name": "住宅价格定基",
        "unit": "index",
        "description": "住宅销售价格定基或累计平均指数。",
        "methodology": "以固定基期或累计平均方式呈现住宅销售价格指数。",
        "update_frequency": "月度",
        "usage_scenario": "适合观察较长周期的价格水平变化。",
        "caveats": "不同数据源可能存在基期口径差异。",
        "precision": 2,
        "sort_order": 30,
        "default_dimensions": {"house_type": "new_house", "area_type": "none"},
    },
    "cpi_yoy": {
        "category": "cpi",
        "display_name": "CPI 同比",
        "unit": "%",
        "description": "居民消费价格较上年同期变化幅度。",
        "methodology": "按居民消费价格指数统计口径，比较本月与上年同月消费价格水平。",
        "update_frequency": "月度",
        "usage_scenario": "适合观察通胀水平和消费价格年度变化。",
        "caveats": "同比受基数影响，需结合环比和累计平均判断。",
        "precision": 2,
        "sort_order": 110,
        "default_dimensions": {"source_type": "cpi", "frequency": "monthly"},
    },
    "cpi_mom": {
        "category": "cpi",
        "display_name": "CPI 环比",
        "unit": "%",
        "description": "居民消费价格较上月变化幅度。",
        "methodology": "按居民消费价格指数统计口径，比较本月与上月消费价格水平。",
        "update_frequency": "月度",
        "usage_scenario": "适合观察消费价格短期变化。",
        "caveats": "节假日和季节性因素可能带来短期波动。",
        "precision": 2,
        "sort_order": 120,
        "default_dimensions": {"source_type": "cpi", "frequency": "monthly"},
    },
    "cpi_avg": {
        "category": "cpi",
        "display_name": "CPI 累计平均同比",
        "unit": "%",
        "description": "居民消费价格年内累计平均较上年同期变化幅度。",
        "methodology": "按年内累计平均 CPI 与上年同期累计平均水平比较。",
        "update_frequency": "月度",
        "usage_scenario": "适合观察年内整体通胀压力。",
        "caveats": "累计平均对最新单月变化不敏感。",
        "precision": 2,
        "sort_order": 130,
        "default_dimensions": {"source_type": "cpi", "frequency": "monthly"},
    },
}

DEFAULT_APP_CONFIGS = {
    "miniapp.home": {
        "recommended_indicators": ["housing_price_mom", "cpi_yoy"],
        "recommended_regions": ["北京", "上海", "全国"],
        "ranking_indicator": "housing_price_mom",
        "default_trend_indicator": "housing_price_mom",
    },
    "data_source.defaults": {
        "interval_minutes": 1440,
        "max_retries": 3,
        "timeout_seconds": 1800,
        "quality_rule_set": "default",
    },
    "quality.rules": {
        "housing_price": {
            "expected_regions": 70,
            "expected_indicators": 3,
            "min_values": 210,
            "value_min": 0,
            "value_max": 200,
            "warning_value_min": 80,
            "warning_value_max": 130,
        },
        "cpi": {
            "expected_regions": 1,
            "expected_indicators": 3,
            "min_values": 2,
            "value_min": -20,
            "value_max": 20,
            "warning_value_min": -10,
            "warning_value_max": 10,
        },
    },
}

HOUSE_TYPES = {
    "new_house": "新建商品住宅",
    "second_hand": "二手住宅",
}

AREA_TYPES = {
    "none": "不分类",
    "under_90": "90㎡及以下",
    "between_90_144": "90-144㎡",
    "over_144": "144㎡以上",
}

from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.routers import admin as admin_router
from packages.pipeline.quality import QualityChecker
from packages.storage import repositories as repo
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url, create_session_factory


def make_client(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'api.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    admin_router.SessionLocal = session_factory
    return TestClient(app), session_factory


def auth_headers(client: TestClient, username: str = "admin", password: str = "admin") -> dict[str, str]:
    response = client.post("/admin/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_data_source_update_and_job_creation(tmp_path):
    client, _ = make_client(tmp_path)
    headers = auth_headers(client)

    unauthorized = client.get("/admin/data-sources")
    assert unauthorized.status_code == 401

    types_response = client.get("/admin/data-source-types", headers=headers)
    assert types_response.status_code == 200
    assert "housing_price" in types_response.json()
    assert "cpi" in types_response.json()

    create_response = client.post(
        "/admin/data-sources",
        json={
            "name": "房价指数",
            "entry_url": "https://example.test/list.html",
            "source": "国家统计局",
            "type": "housing_price",
            "enabled": True,
        },
        headers=headers,
    )
    assert create_response.status_code == 200
    data_source = create_response.json()

    patch_response = client.patch(
        f"/admin/data-sources/{data_source['id']}",
        json={"enabled": False, "name": "房价指数停用"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["enabled"] is False
    assert patch_response.json()["name"] == "房价指数停用"

    job_response = client.post(
        "/admin/crawl-jobs",
        json={"data_source_id": data_source["id"], "run_now": False},
        headers=headers,
    )
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "pending"
    assert job_response.json()["target_url"] == "https://example.test/list.html"
    assert job_response.json()["max_retries"] == 3

    duplicate_response = client.post(
        "/admin/crawl-jobs",
        json={"data_source_id": data_source["id"], "run_now": False},
        headers=headers,
    )
    assert duplicate_response.status_code == 409

    filtered_jobs = client.get("/admin/crawl-jobs?status=pending", headers=headers)
    assert filtered_jobs.status_code == 200
    assert len(filtered_jobs.json()) == 1
    job_id = filtered_jobs.json()[0]["id"]

    job_detail_response = client.get(f"/admin/crawl-jobs/{job_id}/detail", headers=headers)
    assert job_detail_response.status_code == 200
    assert job_detail_response.json()["job"]["id"] == job_id
    assert job_detail_response.json()["retry_available"] is False

    health_response = client.get("/admin/data-sources/health", headers=headers)
    assert health_response.status_code == 200
    assert health_response.json()[0]["latest_job_status"] == "pending"

    detail_response = client.get(f"/admin/data-sources/{data_source['id']}/detail", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["data_source"]["id"] == data_source["id"]
    assert detail_response.json()["recent_jobs"][0]["status"] == "pending"
    assert "run" in detail_response.json()["available_actions"]

    app.dependency_overrides.clear()


def test_schedule_creates_due_jobs_and_supports_cancel(tmp_path):
    client, _ = make_client(tmp_path)
    headers = auth_headers(client)

    schedule_response = client.post(
        "/admin/schedules",
        json={
            "name": "每日房价抓取",
            "target_url": "https://example.test/list.html",
            "interval_minutes": 60,
            "enabled": True,
            "next_run_at": "2025-01-01T00:00:00",
        },
        headers=headers,
    )
    assert schedule_response.status_code == 200

    due_response = client.post("/admin/schedules/run-due", headers=headers)
    assert due_response.status_code == 200
    jobs = due_response.json()
    assert len(jobs) == 1
    assert jobs[0]["trigger"] == "schedule"

    duplicate_due_response = client.post("/admin/schedules/run-due", headers=headers)
    assert duplicate_due_response.status_code == 200
    assert duplicate_due_response.json() == []

    cancel_response = client.post(f"/admin/crawl-jobs/{jobs[0]['id']}/cancel", headers=headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    app.dependency_overrides.clear()


def test_schedule_uses_configured_default_interval(tmp_path):
    client, _ = make_client(tmp_path)
    headers = auth_headers(client)

    config_response = client.patch(
        "/admin/configs/data_source.defaults",
        json={"value": {"interval_minutes": 30, "max_retries": 3, "timeout_seconds": 1800}},
        headers=headers,
    )
    assert config_response.status_code == 200

    schedule_response = client.post(
        "/admin/schedules",
        json={
            "name": "默认间隔调度",
            "target_url": "https://example.test/default-interval.html",
            "enabled": True,
        },
        headers=headers,
    )
    assert schedule_response.status_code == 200
    assert schedule_response.json()["interval_minutes"] == 30

    app.dependency_overrides.clear()


def test_admin_stat_value_publish_flow(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    with session_factory() as db:
        from packages.storage import repositories as repo

        region = repo.get_or_create_region(db, "北京", "city")
        indicator = repo.get_or_create_indicator(db, "housing_price_mom")
        value = repo.upsert_stat_value(
            db,
            region_id=region.id,
            indicator_id=indicator.id,
            period=__import__("datetime").date(2025, 10, 1),
            value=100.2,
            source_id=None,
            dimensions={"house_type": "new_house", "area_type": "none"},
        )
        repo.upsert_crawl_record(
            db,
            data_source_id=repo.get_or_create_data_source(
                db,
                name="房价文章",
                entry_url="https://example.test/article.html",
                source="国家统计局",
                source_type="housing_price",
            ).id,
            title="2025年10月份70个大中城市商品住宅销售价格变动情况",
            url="https://example.test/article.html",
            published_at=__import__("datetime").datetime(2025, 11, 1, 9, 30),
        )
        db.commit()
        value.status = "ready_for_review"
        value.source_id = repo.get_or_create_data_source(
            db,
            name="筛选数据源",
            entry_url="https://example.test/source.html",
            source="国家统计局",
            source_type="housing_price",
        ).id
        db.commit()
        value_id = value.id
        source_id = value.source_id

    list_response = client.get(
        f"/admin/review-items?indicator_code=housing_price_mom&data_source_id={source_id}",
        headers=headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == value_id

    record_response = client.get(
        "/admin/crawl-records?keyword=10月份&published_from=2025-10-01",
        headers=headers,
    )
    assert record_response.status_code == 200
    assert record_response.json()[0]["title"].startswith("2025年10月份")

    patch_response = client.patch(
        f"/admin/stat-values/{value_id}",
        json={"value": 100.3, "reason": "人工复核"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["value"] == 100.3

    changes_response = client.get(f"/admin/stat-value-changes?stat_value_id={value_id}", headers=headers)
    assert changes_response.status_code == 200
    assert changes_response.json()[0]["reason"] == "人工复核"

    publish_response = client.post("/admin/review-batches/publish", json={"ids": [value_id]}, headers=headers)
    assert publish_response.status_code == 200
    assert publish_response.json()["published"] == 1

    batches_response = client.get("/admin/publish-batches", headers=headers)
    assert batches_response.status_code == 200
    assert batches_response.json()[0]["action"] == "publish"

    ops_response = client.get("/admin/ops/summary", headers=headers)
    assert ops_response.status_code == 200
    ops_body = ops_response.json()
    assert ops_body["review_pending_values"] == 0
    assert "failed_jobs_last_24h" in ops_body

    mini_response = client.get(
        "/mini/stat-values/latest?indicator_code=housing_price_mom&house_type=new_house"
    )
    assert mini_response.status_code == 200
    assert mini_response.json()["items"][0]["region"] == "北京"
    assert mini_response.json()["cache_ttl_seconds"] == 300

    overview_response = client.get("/mini/dashboard/overview")
    assert overview_response.status_code == 200
    assert overview_response.json()["published_values"] == 1
    assert overview_response.json()["latest_period"] == "2025-10-01"
    assert overview_response.json()["cache_ttl_seconds"] == 300

    empty_mini_response = client.get(
        "/mini/stat-values/latest?indicator_code=housing_price_mom&house_type=second_hand"
    )
    assert empty_mini_response.status_code == 200
    assert empty_mini_response.json()["items"] == []

    app.dependency_overrides.clear()


def test_indicator_config_and_quality_rules_are_configurable(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    with session_factory() as db:
        indicator = repo.get_or_create_indicator(db, "cpi_yoy")
        region = repo.get_or_create_region(db, "全国", "country")
        job = repo.create_crawl_job(db, target_url="https://example.test/cpi.html")
        repo.mark_job_running(db, job)
        value = repo.upsert_stat_value(
            db,
            region_id=region.id,
            indicator_id=indicator.id,
            period=__import__("datetime").date(2026, 3, 1),
            value=18.0,
            source_id=None,
            dimensions={"source_type": "cpi", "frequency": "monthly"},
        )
        db.commit()
        value_id = value.id

    patch_indicator = client.patch(
        "/admin/indicators/cpi_yoy",
        json={"display_name": "居民消费价格同比", "miniapp_visible": False, "sort_order": 999},
        headers=headers,
    )
    assert patch_indicator.status_code == 200
    assert patch_indicator.json()["display_name"] == "居民消费价格同比"
    indicators_response = client.get("/admin/indicators", headers=headers)
    assert indicators_response.status_code == 200
    assert any(item["code"] == "cpi_yoy" and item["miniapp_visible"] is False for item in indicators_response.json())

    defaults_response = client.patch(
        "/admin/configs/data_source.defaults",
        json={"value": {"max_retries": 5, "timeout_seconds": 90, "interval_minutes": 60}},
        headers=headers,
    )
    assert defaults_response.status_code == 200
    source_response = client.post(
        "/admin/data-sources",
        json={
            "name": "配置默认源",
            "entry_url": "https://example.test/default.html",
            "source": "test",
            "type": "unknown",
            "enabled": True,
        },
        headers=headers,
    )
    job_response = client.post(
        "/admin/crawl-jobs",
        json={"data_source_id": source_response.json()["id"], "run_now": False},
        headers=headers,
    )
    assert job_response.status_code == 200
    assert job_response.json()["max_retries"] == 5
    assert job_response.json()["timeout_seconds"] == 90

    quality_config = client.patch(
        "/admin/configs/quality.rules",
        json={
            "value": {
                "cpi": {
                    "expected_regions": 1,
                    "expected_indicators": 1,
                    "min_values": 1,
                    "required_dimensions": ["source_type", "frequency"],
                    "value_min": -30,
                    "value_max": 30,
                    "warning_value_min": -25,
                    "warning_value_max": 25,
                }
            }
        },
        headers=headers,
    )
    assert quality_config.status_code == 200

    logs_response = client.get("/admin/operation-logs", headers=headers)
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert logs[0]["action"] == "app_config.update"
    assert logs[0]["actor"] == "admin"
    assert logs[0]["target_type"] == "app_config"
    assert logs[0]["target_id"] == "quality.rules"
    assert logs[0]["before"]["value"] != logs[0]["after"]["value"]
    assert any(
        item["action"] == "indicator.update"
        and item["target_type"] == "indicator"
        and item["target_id"] == "cpi_yoy"
        for item in logs
    )

    with session_factory() as db:
        job = repo.list_crawl_jobs(db)[-1]
        QualityChecker(source_type="cpi").check_job(db, job)
        checked_value = repo.get_stat_value(db, value_id)
        assert checked_value.status == "ready_for_review"

    app.dependency_overrides.clear()


def test_ops_summary_reports_failures_and_schedule_health(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    with session_factory() as db:
        from packages.storage import repositories as repo

        repo.create_schedule(
            db,
            name="每日房价抓取",
            target_url="https://example.test/list.html",
            interval_minutes=60,
            next_run_at=__import__("datetime").datetime(2026, 1, 1, 0, 0),
        )
        failed_job = repo.create_crawl_job(db, target_url="https://example.test/list.html")
        repo.mark_job_finished(
            db,
            failed_job,
            status="failed",
            error_type="network_error",
            error_message="timeout",
        )

    summary_response = client.get("/admin/ops/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["jobs_last_24h"] == 1
    assert summary["failed_jobs_last_24h"] == 1
    assert summary["next_schedule_at"] == "2026-01-01T00:00:00"

    failures_response = client.get("/admin/ops/recent-failures", headers=headers)
    assert failures_response.status_code == 200
    assert failures_response.json()[0]["error_type"] == "network_error"

    alert_response = client.post("/admin/ops/test-alert", headers=headers)
    assert alert_response.status_code == 200
    assert alert_response.json()["configured"] is False

    app.dependency_overrides.clear()


def test_quality_failed_values_are_not_published_and_rankings_use_published_only(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    with session_factory() as db:
        from packages.storage import repositories as repo

        region = repo.get_or_create_region(db, "北京", "city")
        indicator = repo.get_or_create_indicator(db, "housing_price_mom")
        value = repo.upsert_stat_value(
            db,
            region_id=region.id,
            indicator_id=indicator.id,
            period=__import__("datetime").date(2025, 10, 1),
            value=100.2,
            source_id=None,
            dimensions={"house_type": "new_house", "area_type": "none"},
        )
        value.status = "quality_failed"
        db.commit()
        value_id = value.id

    publish_response = client.post("/admin/review-batches/publish", json={"ids": [value_id]}, headers=headers)
    assert publish_response.status_code == 200
    assert publish_response.json()["published"] == 0

    ranking_response = client.get("/mini/rankings?indicator_code=housing_price_mom")
    assert ranking_response.status_code == 200
    assert ranking_response.json()["top"] == []
    assert ranking_response.json()["bottom"] == []

    app.dependency_overrides.clear()


def test_operation_logs_capture_source_and_review_changes(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    source_response = client.post(
        "/admin/data-sources",
        json={
            "name": "审计数据源",
            "entry_url": "https://example.test/audit.html",
            "source": "国家统计局",
            "type": "housing_price",
            "enabled": True,
        },
        headers=headers,
    )
    assert source_response.status_code == 200
    source_id = source_response.json()["id"]

    patch_source = client.patch(
        f"/admin/data-sources/{source_id}",
        json={"enabled": False},
        headers=headers,
    )
    assert patch_source.status_code == 200

    with session_factory() as db:
        region = repo.get_or_create_region(db, "北京", "city")
        indicator = repo.get_or_create_indicator(db, "housing_price_mom")
        value = repo.upsert_stat_value(
            db,
            region_id=region.id,
            indicator_id=indicator.id,
            period=__import__("datetime").date(2025, 10, 1),
            value=100.2,
            source_id=source_id,
            dimensions={"house_type": "new_house", "area_type": "none"},
        )
        value.status = "ready_for_review"
        db.commit()
        value_id = value.id

    patch_value = client.patch(
        f"/admin/stat-values/{value_id}",
        json={"value": 100.4, "reason": "审计测试修正"},
        headers=headers,
    )
    assert patch_value.status_code == 200

    reject_response = client.post(
        "/admin/review-batches/reject",
        json={"ids": [value_id], "reason": "审计测试驳回"},
        headers=headers,
    )
    assert reject_response.status_code == 200

    logs_response = client.get("/admin/operation-logs", headers=headers)
    assert logs_response.status_code == 200
    logs = logs_response.json()
    actions = [item["action"] for item in logs]
    assert "data_source.create" in actions
    assert "data_source.update" in actions
    assert "stat_value.update" in actions
    assert "review_batch.reject" in actions
    reject_log = next(item for item in logs if item["action"] == "review_batch.reject")
    assert reject_log["reason"] == "审计测试驳回"
    assert reject_log["after"]["count"] == 1

    filtered_response = client.get("/admin/operation-logs?target_type=data_source", headers=headers)
    assert filtered_response.status_code == 200
    assert {item["action"] for item in filtered_response.json()} == {
        "data_source.create",
        "data_source.update",
    }

    app.dependency_overrides.clear()


def test_review_batch_preview_reports_impact_without_mutation(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    with session_factory() as db:
        beijing = repo.get_or_create_region(db, "北京", "city")
        shanghai = repo.get_or_create_region(db, "上海", "city")
        indicator = repo.get_or_create_indicator(db, "housing_price_mom")
        ready_value = repo.upsert_stat_value(
            db,
            region_id=beijing.id,
            indicator_id=indicator.id,
            period=__import__("datetime").date(2025, 10, 1),
            value=100.2,
            source_id=None,
            dimensions={"house_type": "new_house", "area_type": "none"},
        )
        ignored_value = repo.upsert_stat_value(
            db,
            region_id=shanghai.id,
            indicator_id=indicator.id,
            period=__import__("datetime").date(2025, 10, 1),
            value=99.8,
            source_id=None,
            dimensions={"house_type": "new_house", "area_type": "none"},
        )
        ready_value.status = "ready_for_review"
        ignored_value.status = "draft"
        db.commit()
        ready_id = ready_value.id
        ignored_id = ignored_value.id

    preview_response = client.post(
        "/admin/review-batches/publish/preview",
        json={"ids": [ready_id, ignored_id, 999999]},
        headers=headers,
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["requested_count"] == 3
    assert preview["matched_count"] == 2
    assert preview["affected_count"] == 1
    assert preview["ignored_count"] == 2
    assert preview["regions"] == ["北京"]
    assert preview["indicators"] == ["housing_price_mom"]
    assert preview["periods"] == ["2025-10-01"]

    with session_factory() as db:
        assert repo.get_stat_value(db, ready_id).status == "ready_for_review"
        assert repo.get_stat_value(db, ignored_id).status == "draft"
        assert repo.list_operation_logs(db) == []

    reject_preview_response = client.post(
        "/admin/review-batches/reject/preview",
        json={"ids": [ready_id, ignored_id]},
        headers=headers,
    )
    assert reject_preview_response.status_code == 200
    reject_preview = reject_preview_response.json()
    assert reject_preview["affected_count"] == 2
    assert reject_preview["region_count"] == 2
    assert reject_preview["statuses"] == ["draft", "ready_for_review"]

    app.dependency_overrides.clear()


def test_config_versions_preview_and_rollback(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    config_updates = {
        "miniapp.home": {
            "recommended_indicators": ["cpi_yoy"],
            "recommended_regions": ["全国"],
            "ranking_indicator": "cpi_yoy",
            "default_trend_indicator": "cpi_yoy",
        },
        "quality.rules": {
            "cpi": {
                "expected_regions": 1,
                "expected_indicators": 1,
                "min_values": 1,
                "required_dimensions": ["source_type", "frequency"],
                "value_min": -30,
                "value_max": 30,
            }
        },
        "data_source.defaults": {"max_retries": 4, "timeout_seconds": 120, "interval_minutes": 45},
    }
    first_version_ids = {}
    for key, value in config_updates.items():
        patch_response = client.patch(
            f"/admin/configs/{key}",
            json={"value": value, "description": f"{key} 测试配置", "reason": "版本测试"},
            headers=headers,
        )
        assert patch_response.status_code == 200
        versions_response = client.get(f"/admin/configs/{key}/versions", headers=headers)
        assert versions_response.status_code == 200
        versions = versions_response.json()
        assert versions[0]["key"] == key
        assert versions[0]["version"] == 1
        assert versions[0]["actor"] == "admin"
        assert versions[0]["reason"] == "版本测试"
        assert versions[0]["before_value"] != versions[0]["after_value"]
        first_version_ids[key] = versions[0]["id"]

    preview_response = client.post(
        "/admin/configs/miniapp.home/preview",
        json={
            "value": {
                "recommended_indicators": ["cpi_yoy", "housing_price_mom"],
                "ranking_indicator": "housing_price_mom",
            }
        },
        headers=headers,
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert {item["path"]: item["change_type"] for item in preview["diff"]} == {
        "default_trend_indicator": "removed",
        "ranking_indicator": "changed",
        "recommended_indicators": "changed",
        "recommended_regions": "removed",
    }
    assert preview["before_summary"]["recommended_regions"] == 1
    assert preview["after_summary"]["recommended_indicators"] == 2

    second_update = client.patch(
        "/admin/configs/miniapp.home",
        json={
            "value": {
                "recommended_indicators": ["housing_price_mom"],
                "recommended_regions": ["北京"],
                "ranking_indicator": "housing_price_mom",
                "default_trend_indicator": "housing_price_mom",
            },
            "reason": "误改测试",
        },
        headers=headers,
    )
    assert second_update.status_code == 200

    detail_response = client.get(
        f"/admin/configs/miniapp.home/versions/{first_version_ids['miniapp.home']}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["after_value"]["ranking_indicator"] == "cpi_yoy"

    rollback_response = client.post(
        "/admin/configs/miniapp.home/rollback",
        json={"version_id": first_version_ids["miniapp.home"], "reason": "回滚测试"},
        headers=headers,
    )
    assert rollback_response.status_code == 200
    assert rollback_response.json()["value"] == config_updates["miniapp.home"]

    missing_response = client.post(
        "/admin/configs/miniapp.home/rollback",
        json={"version_id": 999999},
        headers=headers,
    )
    assert missing_response.status_code == 404

    unknown_response = client.post(
        "/admin/configs/unknown.config/preview",
        json={"value": {}},
        headers=headers,
    )
    assert unknown_response.status_code == 404

    with session_factory() as db:
        versions = repo.list_config_versions(db, "miniapp.home")
        assert [version.version for version in versions] == [3, 2, 1]
        logs = repo.list_operation_logs(db, target_type="app_config")
        assert logs[0].action == "app_config.rollback"
        assert logs[0].reason == "回滚测试"
        assert logs[0].after["rollback_to_version"] == 1
        assert any(log.action == "app_config.preview" for log in logs)

    app.dependency_overrides.clear()


def test_quality_report_details_locate_failed_values(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    with session_factory() as db:
        job = repo.create_crawl_job(db, target_url="https://example.test/data.html")
        repo.mark_job_running(db, job)
        indicator = repo.get_or_create_indicator(db, "cpi_yoy")
        region = repo.get_or_create_region(db, "全国", "country")
        repo.upsert_stat_value(
            db,
            region_id=region.id,
            indicator_id=indicator.id,
            period=__import__("datetime").date(2026, 3, 1),
            value=30.0,
            source_id=None,
            dimensions={"source_type": "cpi"},
        )
        db.commit()
        QualityChecker(source_type="cpi").check_job(db, job)

    response = client.get("/admin/quality-reports", headers=headers)
    assert response.status_code == 200
    report = response.json()[0]
    assert report["status"] == "failed"
    value_detail = next(detail for detail in report["details"] if detail.get("rule") == "value_range")
    assert value_detail["indicator"] == "cpi_yoy"
    assert value_detail["region"] == "全国"
    assert value_detail["period"] == "2026-03-01"
    assert value_detail["dimensions"] == {"source_type": "cpi"}

    detail_response = client.get(f"/admin/quality-reports/{report['id']}", headers=headers)
    assert detail_response.status_code == 200
    assert any(detail["rule"] == "value_range" for detail in detail_response.json()["error_details"])
    assert "复核异常值" in detail_response.json()["suggested_actions"]

    app.dependency_overrides.clear()


def test_rankings_default_to_city_level_area(tmp_path):
    client, session_factory = make_client(tmp_path)

    with session_factory() as db:
        from packages.storage import repositories as repo

        indicator = repo.get_or_create_indicator(db, "housing_price_mom")
        beijing = repo.get_or_create_region(db, "北京", "city")
        shanghai = repo.get_or_create_region(db, "上海", "city")
        for region, none_value, classified_value in [
            (beijing, 101.2, 109.9),
            (shanghai, 99.8, 110.0),
        ]:
            for area_type, value in [("none", none_value), ("under_90", classified_value)]:
                stat_value = repo.upsert_stat_value(
                    db,
                    region_id=region.id,
                    indicator_id=indicator.id,
                    period=__import__("datetime").date(2025, 10, 1),
                    value=value,
                    source_id=None,
                    dimensions={"house_type": "new_house", "area_type": area_type},
                )
                stat_value.status = "published"
        db.commit()

    ranking_response = client.get(
        "/mini/rankings?indicator_code=housing_price_mom&house_type=new_house"
    )
    assert ranking_response.status_code == 200
    body = ranking_response.json()
    assert [item["region"] for item in body["top"]] == ["北京", "上海"]
    assert [item["value"] for item in body["top"]] == [101.2, 99.8]
    assert body["latest_period"] == "2025-10-01"

    app.dependency_overrides.clear()


def test_mini_api_exposes_cpi_values(tmp_path):
    client, session_factory = make_client(tmp_path)

    with session_factory() as db:
        indicator = repo.get_or_create_indicator(db, "cpi_yoy")
        region = repo.get_or_create_region(db, "全国", "country")
        value = repo.upsert_stat_value(
            db,
            region_id=region.id,
            indicator_id=indicator.id,
            period=__import__("datetime").date(2026, 3, 1),
            value=-0.1,
            source_id=None,
            dimensions={"source_type": "cpi", "frequency": "monthly"},
        )
        value.status = "published"
        db.commit()

    latest_response = client.get("/mini/stat-values/latest?indicator_code=cpi_yoy")
    assert latest_response.status_code == 200
    assert latest_response.json()["items"][0]["region"] == "全国"

    ranking_response = client.get("/mini/rankings?indicator_code=cpi_yoy")
    assert ranking_response.status_code == 200
    assert ranking_response.json()["top"][0]["value"] == -0.1

    app.dependency_overrides.clear()


def test_productized_metadata_config_and_mini_aggregates(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    with session_factory() as db:
        province = repo.get_or_create_region(db, "华北", "province")
        beijing = repo.get_or_create_region(db, "北京", "city", parent_id=province.id)
        shanghai = repo.get_or_create_region(db, "上海", "city")
        indicator = repo.get_or_create_indicator(db, "housing_price_mom")
        cpi_indicator = repo.get_or_create_indicator(db, "cpi_yoy")
        for region, first, second in [(beijing, 99.8, 101.2), (shanghai, 98.8, 100.2)]:
            for period, value in [
                (__import__("datetime").date(2025, 9, 1), first),
                (__import__("datetime").date(2025, 10, 1), second),
            ]:
                stat_value = repo.upsert_stat_value(
                    db,
                    region_id=region.id,
                    indicator_id=indicator.id,
                    period=period,
                    value=value,
                    source_id=None,
                    dimensions={"house_type": "new_house", "area_type": "none"},
                )
                stat_value.status = "published"
        cpi_value = repo.upsert_stat_value(
            db,
            region_id=province.id,
            indicator_id=cpi_indicator.id,
            period=__import__("datetime").date(2025, 10, 1),
            value=0.2,
            source_id=None,
            dimensions={"source_type": "cpi", "frequency": "monthly"},
        )
        cpi_value.status = "published"
        db.commit()
        beijing_id = beijing.id
        shanghai_id = shanghai.id

    groups_response = client.get("/mini/indicator-groups")
    assert groups_response.status_code == 200
    groups = groups_response.json()
    assert groups[0]["items"][0]["display_name"] == "住宅价格环比"
    assert {group["category"] for group in groups} >= {"housing_price", "cpi"}

    city_response = client.get(f"/mini/regions/{beijing_id}/detail")
    assert city_response.status_code == 200
    assert city_response.json()["region"]["parent_id"] is not None
    assert city_response.json()["indicator_cards"][0]["indicator"]["category"] == "housing_price"

    compare_response = client.get(
        f"/mini/stat-values/compare?region_ids={beijing_id},{shanghai_id}&indicator_code=housing_price_mom"
    )
    assert compare_response.status_code == 200
    assert [series["region"] for series in compare_response.json()["series"]] == ["北京", "上海"]
    assert len(compare_response.json()["series"][0]["items"]) == 2

    config_response = client.get("/admin/configs", headers=headers)
    assert config_response.status_code == 200
    assert any(item["key"] == "miniapp.home" for item in config_response.json())

    patch_response = client.patch(
        "/admin/configs/miniapp.home",
        json={
            "value": {
                "recommended_indicators": ["cpi_yoy"],
                "recommended_regions": ["华北"],
                "ranking_indicator": "cpi_yoy",
                "default_trend_indicator": "cpi_yoy",
            },
            "description": "测试首页配置",
        },
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["value"]["ranking_indicator"] == "cpi_yoy"

    recommendations_response = client.get("/mini/home/recommendations")
    assert recommendations_response.status_code == 200
    assert recommendations_response.json()["recommended_indicators"][0]["code"] == "cpi_yoy"
    assert recommendations_response.json()["recommended_regions"][0]["name"] == "华北"

    app.dependency_overrides.clear()


def test_admin_unknown_data_source_type_fails_job(tmp_path):
    client, session_factory = make_client(tmp_path)
    headers = auth_headers(client)

    source_response = client.post(
        "/admin/data-sources",
        json={
            "name": "未知源",
            "entry_url": "https://example.test/unknown.html",
            "source": "test",
            "type": "unknown",
            "enabled": True,
        },
        headers=headers,
    )
    assert source_response.status_code == 200

    job_response = client.post(
        "/admin/crawl-jobs",
        json={"data_source_id": source_response.json()["id"], "run_now": True},
        headers=headers,
    )
    assert job_response.status_code == 200

    with session_factory() as db:
        job = repo.list_crawl_jobs(db)[0]
        assert job.status == "failed"
        assert job.error_type == "unsupported_data_source_type"

    app.dependency_overrides.clear()


def test_reviewer_cannot_manage_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_TREND_ADMIN_ROLE", "reviewer")
    from apps.api.config import get_settings

    get_settings.cache_clear()
    client, _ = make_client(tmp_path)
    headers = auth_headers(client)

    response = client.post(
        "/admin/data-sources",
        json={
            "name": "房价指数",
            "entry_url": "https://example.test/list.html",
            "source": "国家统计局",
            "type": "housing_price",
            "enabled": True,
        },
        headers=headers,
    )
    assert response.status_code == 403

    monkeypatch.delenv("DATA_TREND_ADMIN_ROLE")
    get_settings.cache_clear()

    app.dependency_overrides.clear()

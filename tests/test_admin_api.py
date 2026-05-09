from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
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
    return TestClient(app), session_factory


def test_admin_data_source_update_and_job_creation(tmp_path):
    client, _ = make_client(tmp_path)

    create_response = client.post(
        "/admin/data-sources",
        json={
            "name": "房价指数",
            "entry_url": "https://example.test/list.html",
            "source": "国家统计局",
            "type": "housing_price",
            "enabled": True,
        },
    )
    assert create_response.status_code == 200
    data_source = create_response.json()

    patch_response = client.patch(
        f"/admin/data-sources/{data_source['id']}",
        json={"enabled": False, "name": "房价指数停用"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["enabled"] is False
    assert patch_response.json()["name"] == "房价指数停用"

    job_response = client.post(
        "/admin/crawl-jobs",
        json={"data_source_id": data_source["id"], "run_now": False},
    )
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "pending"

    app.dependency_overrides.clear()


def test_admin_stat_value_publish_flow(tmp_path):
    client, session_factory = make_client(tmp_path)

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
        db.commit()
        value_id = value.id

    list_response = client.get("/admin/stat-values?status=draft")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == value_id

    publish_response = client.post("/admin/stat-values/publish", json={"ids": [value_id]})
    assert publish_response.status_code == 200
    assert publish_response.json()["published"] == 1

    mini_response = client.get("/mini/stat-values/latest?indicator_code=housing_price_mom")
    assert mini_response.status_code == 200
    assert mini_response.json()[0]["region"] == "北京"

    app.dependency_overrides.clear()

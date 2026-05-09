from collections.abc import Generator

from apps.api.config import get_settings
from packages.storage.session import create_session_factory


SessionLocal = create_session_factory(get_settings().database_url)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


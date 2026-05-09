from apps.api.config import get_settings
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url


def bootstrap_database() -> None:
    engine = create_engine_from_url(get_settings().database_url)
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    bootstrap_database()


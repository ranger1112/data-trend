from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Session

from packages.storage.models import CrawlJob, DataSource


class ImportRunner(Protocol):
    def run(self, url: str, job: CrawlJob | None = None, data_source: DataSource | None = None) -> CrawlJob:
        ...


RunnerFactory = Callable[[Session], ImportRunner]
_REGISTRY: dict[str, RunnerFactory] = {}


def register_importer(source_type: str, factory: RunnerFactory) -> None:
    _REGISTRY[source_type] = factory


def get_import_runner(source_type: str, db: Session) -> ImportRunner:
    factory = _REGISTRY.get(source_type)
    if factory is None:
        raise UnsupportedDataSourceType(source_type)
    return factory(db)


def list_importer_types() -> list[str]:
    return sorted(_REGISTRY)


class UnsupportedDataSourceType(ValueError):
    def __init__(self, source_type: str) -> None:
        super().__init__(f"unsupported data source type: {source_type}")
        self.source_type = source_type

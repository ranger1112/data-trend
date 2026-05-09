from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_engine_from_url(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def create_session_factory(database_url: str):
    engine = create_engine_from_url(database_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


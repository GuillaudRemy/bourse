from sqlmodel import create_engine, Session
from sqlalchemy import event
from backend.core.config import config

engine = create_engine(config.db_url, echo=config.DEBUG)


@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


def get_session():
    with Session(engine) as session:
        yield session

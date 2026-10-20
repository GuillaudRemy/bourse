from sqlalchemy import event
from sqlmodel import Session, create_engine

from backend.core.config import config

engine = create_engine(config.db_url, echo=config.DEBUG)


@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")
    # Journal WAL : les lectures (interface) ne bloquent plus pendant une actualisation.
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")


def get_session():
    with Session(engine) as session:
        yield session

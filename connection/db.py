import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import sessionmaker

load_dotenv()

# MYSQL


def mysql_url(database: str | None = None) -> URL:
    return URL.create(
        drivername="mysql+pymysql",
        username=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ["MYSQL_PORT"]),
        database=database or os.environ["MYSQL_DATABASE"],
    )


# parametrizing session creating for the future required tests.
def create_source_sessionmaker(database: str | None = None) -> sessionmaker:
    engine = create_engine(mysql_url(database))
    return sessionmaker(bind=engine)


# SQLITE


def sqlite_url(path=None) -> URL:
    return URL.create(
        drivername="sqlite",
        database=path or os.environ["SQLITE_PATH"],
    )


# parametrizing session creating for the future required tests.
def create_target_sessionmaker(path: str | None = None) -> sessionmaker:
    engine = create_engine(sqlite_url(path))

    # When reviewing the code implemented, I found out that SQLite doesn't automaticaly verify foreign keys
    # So with the help of GenAI I found out about this event decorator the runs every time a new connection is opened.
    # This way, if the load try to write something before it's Dim, the DB refuses it.
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return sessionmaker(bind=engine)

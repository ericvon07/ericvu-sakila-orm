import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


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


def sqlite_url(path=None) -> URL:
    return URL.create(
        drivername="sqlite",
        database=path or os.environ["SQLITE_PATH"],
    )


# parametrizing session creating for the future required tests.
def create_target_sessionmaker(path: str | None = None) -> sessionmaker:
    engine = create_engine(sqlite_url(path))
    return sessionmaker(bind=engine)

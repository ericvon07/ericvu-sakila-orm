import os

import pytest
from sqlalchemy import create_engine, text

from connection.db import (
    create_source_sessionmaker,
    create_target_sessionmaker,
    mysql_url,
)
from models.source import SourceBase

MAIN_DATABASE = os.environ["MYSQL_DATABASE"]
TEST_DATABASE = os.environ["MYSQL_TEST_DATABASE"]

# Note for grading: I had never used @pytest.fixture before, so everything I used in here was based on:
# https://coderpad.io/blog/development/a-guide-to-database-unit-testing-with-pytest-and-sqlalchemy/

# This was specially useful when designing the real tests (from test_full_sync.py)
# Since I'd have to otherwise manually parametrize them, one by one.
# Although I had to pretty much adapt everything to the assignment context, it was really helpful and bought me a lot of time.


def reset_test_database() -> None:
    # Makes sakila_test an exact copy of sakila again
    assert TEST_DATABASE != MAIN_DATABASE, "refusing to reset the main database"

    engine = create_engine(mysql_url(TEST_DATABASE))
    with engine.begin() as connection:
        # Sakila triggers overwrite dates with NOW() on every insert
        for trigger in ["customer_create_date", "rental_date", "payment_date"]:
            connection.execute(text(f"DROP TRIGGER IF EXISTS {trigger}"))

        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        connection.execute(text("TRUNCATE TABLE film_text"))
        for model in SourceBase.__subclasses__():
            table = model.__tablename__
            connection.execute(text(f"TRUNCATE TABLE {table}"))
            connection.execute(
                text(f"INSERT INTO {table} SELECT * FROM {MAIN_DATABASE}.{table}")
            )
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    engine.dispose()


@pytest.fixture
def source():
    # Freshly reseted sakila_test
    reset_test_database()
    with create_source_sessionmaker(TEST_DATABASE)() as session:
        yield session


@pytest.fixture
def target(tmp_path):
    # Empty SQLite file that pytest deletes afterwards.
    with create_target_sessionmaker(str(tmp_path / "test.db"))() as session:
        yield session

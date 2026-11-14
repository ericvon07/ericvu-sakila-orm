import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.source import Payment, Rental, SourceBase
from models.target import SyncState, TargetBase
from sync.dates import build_dim_date

log = logging.getLogger("sync")

# Note for grading: I used generative AI to learn more about the
# logging library in Python. I also used it to help me correct my implementation.
# This understanding also helped me when using the logging lib on the cli.py file


def run_init(source: Session, target: Session) -> None:
    # 1. Create analytics tables
    TargetBase.metadata.create_all(target.get_bind())
    log.info("Analytics tables ready")

    # Verify the MySQL connection
    source.execute(select(1))
    log.info("MySQL connection ok")

    # Fill dim_date with every day between the first and last date in Sakila
    rental_min, rental_max, return_max = source.execute(
        select(
            func.min(Rental.rental_date),
            func.max(Rental.rental_date),
            func.max(Rental.return_date),
        )
    ).one()
    payment_min, payment_max = source.execute(
        select(func.min(Payment.payment_date), func.max(Payment.payment_date))
    ).one()

    # Any of these can be None
    candidates = [rental_min, rental_max, return_max, payment_min, payment_max]
    found = [value for value in candidates if value is not None]

    days = 0
    if found:
        current = min(found).date()
        last = max(found).date()
        while current <= last:
            target.merge(build_dim_date(current))
            current += timedelta(days=1)
            days += 1
    log.info("dim_date covers %d days", days)

    # Create one sync_state row per source table, without touching existing ones
    created = 0
    for model in SourceBase.__subclasses__():
        table_name = model.__tablename__
        if target.get(SyncState, table_name) is None:
            target.add(SyncState(table_name=table_name, last_update=None))
            created += 1
    log.info("sync_state: %d rows were created", created)

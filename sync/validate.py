import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.source import (
    Actor,
    Category,
    Customer,
    Film,
    FilmActor,
    FilmCategory,
    Inventory,
    Payment,
    Rental,
    Staff,
    Store,
)
from models.target import (
    BridgeFilmActor,
    BridgeFilmCategory,
    DimActor,
    DimCategory,
    DimCustomer,
    DimDate,
    DimFilm,
    DimStore,
    FactPayment,
    FactRental,
)
from sync.dates import _to_date_key

# Note for grading: Used genAI to help me implement _check_rentals(), _check_orphans(), and _check_payments().

log = logging.getLogger("sync")

# Amount totals must match to within $0.01.
AMOUNT_TOLERANCE = 0.01


class ValidationError(Exception):
    pass


# --------------------
#  Period


def resolve_period(
    source: Session, date_from: date | None, date_to: date | None
) -> tuple[date, date]:
    # Default: the 30 days ending on the latest payment date in Sakila.
    # (Sakila ends in February 2006, so a period based on today would be empty.)
    if date_to is None:
        latest = source.scalar(select(func.max(Payment.payment_date)))
        date_to = latest.date() if latest is not None else date.today()
    if date_from is None:
        date_from = date_to - timedelta(days=29)
    return date_from, date_to


def _source_period(column, date_from: date | None, date_to: date | None) -> list:
    # Sakila stores timestamps -> from 00:00 of day 1 up to the last one

    conditions = []
    if date_from is not None:
        conditions.append(column >= datetime.combine(date_from, time.min))
    if date_to is not None:
        next_day = date_to + timedelta(days=1)
        conditions.append(column < datetime.combine(next_day, time.min))
    return conditions


def _target_period(column, date_from: date | None, date_to: date | None) -> list:
    # Analytics tables store date keys (YYYYMMDD).
    conditions = []
    if date_from is not None:
        conditions.append(column >= _to_date_key(date_from))
    if date_to is not None:
        conditions.append(column <= _to_date_key(date_to))
    return conditions


# --------------------
#  Checks period dependancy


def _check_table_counts(source: Session, target: Session, problems: list[str]) -> None:
    # Dimensions and bridges: one target row per source row.
    pairs = [
        (Film, DimFilm),
        (Actor, DimActor),
        (Category, DimCategory),
        (Store, DimStore),
        (Customer, DimCustomer),
        (FilmActor, BridgeFilmActor),
        (FilmCategory, BridgeFilmCategory),
    ]
    for source_model, target_model in pairs:
        in_source = source.scalar(select(func.count()).select_from(source_model))
        in_target = target.scalar(select(func.count()).select_from(target_model))
        if in_source != in_target:
            problems.append(
                f"{target_model.__tablename__}: MySQL has {in_source} rows, "
                f"SQLite has {in_target}"
            )


def _check_duplicates(target: Session, problems: list[str]) -> None:
    # No natural key may appear twice.
    natural_keys = [
        DimFilm.film_id,
        DimActor.actor_id,
        DimCategory.category_id,
        DimStore.store_id,
        DimCustomer.customer_id,
        FactRental.rental_id,
        FactPayment.payment_id,
    ]
    for key in natural_keys:
        duplicated = target.execute(
            select(key).group_by(key).having(func.count() > 1)
        ).all()
        if duplicated:
            problems.append(
                f"{key.class_.__tablename__}: {len(duplicated)} duplicated "
                f"{key.key} values"
            )


# Note for grading: Used genAI to help me write this list.


def _check_orphans(target: Session, problems: list[str]) -> None:
    # Every key (fact/bridge) must exist in its dimension.
    references = [
        (FactRental.date_key_rented, DimDate.date_key),
        (FactRental.date_key_returned, DimDate.date_key),
        (FactRental.film_key, DimFilm.film_key),
        (FactRental.store_key, DimStore.store_key),
        (FactRental.customer_key, DimCustomer.customer_key),
        (FactPayment.date_key_paid, DimDate.date_key),
        (FactPayment.customer_key, DimCustomer.customer_key),
        (FactPayment.store_key, DimStore.store_key),
        (BridgeFilmActor.film_key, DimFilm.film_key),
        (BridgeFilmActor.actor_key, DimActor.actor_key),
        (BridgeFilmCategory.film_key, DimFilm.film_key),
        (BridgeFilmCategory.category_key, DimCategory.category_key),
    ]
    for foreign_key, dimension_key in references:
        # LEFT JOIN + IS NULL
        orphans = target.scalar(
            select(func.count())
            .select_from(foreign_key.class_)
            .outerjoin(dimension_key.class_, foreign_key == dimension_key)
            .where(foreign_key.is_not(None), dimension_key.is_(None))
        )
        if orphans:
            problems.append(
                f"{foreign_key.class_.__tablename__}: {orphans} rows with a "
                f"{foreign_key.key} that is not in "
                f"{dimension_key.class_.__tablename__}"
            )


# --------------------
#  Checks over the selected period


def _report_missing(
    name: str, in_source: set[int], in_target: set[int], problems: list[str]
) -> None:
    missing = sorted(in_source - in_target)
    if missing:
        problems.append(
            f"{name}: {len(missing)} rows missing in SQLite (first ids: {missing[:5]})"
        )


def _check_rentals(
    source: Session,
    target: Session,
    date_from: date | None,
    date_to: date | None,
    problems: list[str],
) -> None:
    in_source = _source_period(Rental.rental_date, date_from, date_to)
    in_target = _target_period(FactRental.date_key_rented, date_from, date_to)

    # Missing rows
    source_ids = set(source.scalars(select(Rental.rental_id).where(*in_source)))
    target_ids = set(target.scalars(select(FactRental.rental_id).where(*in_target)))
    _report_missing("fact_rental", source_ids, target_ids, problems)

    # N rentals per store
    source_counts = {
        store_id: count
        for store_id, count in source.execute(
            select(Inventory.store_id, func.count())
            .select_from(Rental)
            .join(Inventory)
            .where(*in_source)
            .group_by(Inventory.store_id)
        )
    }
    target_counts = {
        store_id: count
        for store_id, count in target.execute(
            select(DimStore.store_id, func.count())
            .select_from(FactRental)
            .join(DimStore)
            .where(*in_target)
            .group_by(DimStore.store_id)
        )
    }
    for store_id in sorted(set(source_counts) | set(target_counts)):
        expected = source_counts.get(store_id, 0)
        found = target_counts.get(store_id, 0)
        if expected != found:
            problems.append(
                f"fact_rental: store {store_id} has {expected} rentals in MySQL, "
                f"{found} in SQLite"
            )


def _check_payments(
    source: Session,
    target: Session,
    date_from: date | None,
    date_to: date | None,
    problems: list[str],
) -> None:
    in_source = _source_period(Payment.payment_date, date_from, date_to)
    in_target = _target_period(FactPayment.date_key_paid, date_from, date_to)

    # Missing rows
    source_ids = set(source.scalars(select(Payment.payment_id).where(*in_source)))
    target_ids = set(target.scalars(select(FactPayment.payment_id).where(*in_target)))
    _report_missing("fact_payment", source_ids, target_ids, problems)

    # Number of payments and total amount per store. Same attribution rule as
    # the load: the store of the rented copy, otherwise the staff member's store.
    store_id = func.coalesce(Inventory.store_id, Staff.store_id)
    source_totals = {
        store: (count, total)
        for store, count, total in source.execute(
            select(store_id, func.count(), func.sum(Payment.amount))
            .select_from(Payment)
            .join(Staff, Payment.staff_id == Staff.staff_id)
            .outerjoin(Rental, Payment.rental_id == Rental.rental_id)
            .outerjoin(Inventory, Rental.inventory_id == Inventory.inventory_id)
            .where(*in_source)
            .group_by(store_id)
        )
    }
    target_totals = {
        store: (count, total)
        for store, count, total in target.execute(
            select(DimStore.store_id, func.count(), func.sum(FactPayment.amount))
            .select_from(FactPayment)
            .join(DimStore)
            .where(*in_target)
            .group_by(DimStore.store_id)
        )
    }
    for store in sorted(set(source_totals) | set(target_totals)):
        expected_count, expected_total = source_totals.get(store, (0, 0))
        found_count, found_total = target_totals.get(store, (0, 0))
        if expected_count != found_count:
            problems.append(
                f"fact_payment: store {store} has {expected_count} payments in "
                f"MySQL, {found_count} in SQLite"
            )
        difference = abs(float(expected_total) - float(found_total))
        if round(difference, 4) > AMOUNT_TOLERANCE:
            problems.append(
                f"fact_payment: store {store} total is {float(expected_total):.2f} "
                f"in MySQL, {float(found_total):.2f} in SQLite"
            )


# --------------------
#  Entry points


def check_consistency(
    source: Session,
    target: Session,
    date_from: date | None = None,
    date_to: date | None = None,
) -> None:
    # Compares MySQL and SQLite. With no dates, the facts are compared in full.
    # Raises ValidationError listing every problem found.
    problems: list[str] = []

    _check_table_counts(source, target, problems)
    _check_duplicates(target, problems)
    _check_orphans(target, problems)
    _check_rentals(source, target, date_from, date_to, problems)
    _check_payments(source, target, date_from, date_to, problems)

    if problems:
        for problem in problems:
            log.error("MISMATCH %s", problem)
        raise ValidationError(
            f"{len(problems)} problem(s) found:\n  " + "\n  ".join(problems)
        )
    log.info("Validation passed: MySQL and SQLite are consistent")


def run_validate(
    source: Session,
    target: Session,
    date_from: date | None = None,
    date_to: date | None = None,
) -> None:
    # The `validate` command: fills in the default period, then checks.
    date_from, date_to = resolve_period(source, date_from, date_to)
    log.info("Validating period %s to %s", date_from, date_to)
    check_consistency(source, target, date_from, date_to)

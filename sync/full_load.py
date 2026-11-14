import logging
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from models.source import (
    Actor,
    Address,
    Category,
    City,
    Country,
    Customer,
    Film,
    FilmActor,
    FilmCategory,
    Inventory,
    Language,
    Payment,
    Rental,
    SourceBase,
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
    SyncState,
)
from sync.dates import _to_date_key, build_dim_date

log = logging.getLogger("sync")

# Note for grading: In full_load.py I wrote the helper functions on my own but had GenAI help when writing / reviewing
# Dimensions, Bridges, Facts

# --------------------
#  Helpers


def _fetch(source: Session, query, where=None) -> list[dict]:
    # Runs a query on Sakila and returns each row as a dict {column_name: value}.
    # `where` is unused by full-load (default); incremental pass a filter in it
    if where is not None:
        query = query.where(where)
    return [dict(row) for row in source.execute(query).mappings()]


def _upsert(target: Session, model, key: str, rows: list[dict]) -> int:
    # INSERT ... ON CONFLICT (key) DO UPDATE: inserts new rows and overwrites
    # existing ones (Type 1). Relies on the unique index on the natural key.
    if not rows:
        return 0
    stmt = insert(model)
    new_values = {column: stmt.excluded[column] for column in rows[0] if column != key}
    stmt = stmt.on_conflict_do_update(index_elements=[key], set_=new_values)
    target.execute(stmt, rows)
    return len(rows)


def _insert_missing(target: Session, model, rows: list[dict]) -> int:
    # For bridges: a row is only its key, so there is nothing to update.
    if not rows:
        return 0
    target.execute(insert(model).on_conflict_do_nothing(), rows)
    return len(rows)


def _key_map(target: Session, natural_key, surrogate_key) -> dict[int, int]:
    # Translation table, e.g. {film_id: film_key}
    rows = target.execute(select(natural_key, surrogate_key))
    return {natural: surrogate for natural, surrogate in rows}


def _ensure_dates(target: Session, dates: set[date]) -> None:
    # Adds to dim_date any date the sync encounters that is not there yet.
    existing = set(target.scalars(select(DimDate.date_key)))
    for d in dates:
        if _to_date_key(d) not in existing:
            target.add(build_dim_date(d))
    target.flush()


# --------------------
#  Dimensions


def load_dim_film(source: Session, target: Session, where=None) -> int:
    query = (
        select(
            Film.film_id,
            Film.title,
            Film.rating,
            Film.length,
            Language.name.label("language"),
            Film.release_year,
            Film.last_update,
        )
        .select_from(Film)
        .join(Language)
    )
    return _upsert(target, DimFilm, "film_id", _fetch(source, query, where))


def load_dim_actor(source: Session, target: Session, where=None) -> int:
    query = select(Actor.actor_id, Actor.first_name, Actor.last_name, Actor.last_update)
    return _upsert(target, DimActor, "actor_id", _fetch(source, query, where))


def load_dim_category(source: Session, target: Session, where=None) -> int:
    query = select(Category.category_id, Category.name, Category.last_update)
    return _upsert(target, DimCategory, "category_id", _fetch(source, query, where))


def load_dim_store(source: Session, target: Session, where=None) -> int:
    query = (
        select(Store.store_id, City.city, Country.country, Store.last_update)
        .select_from(Store)
        .join(Address)
        .join(City)
        .join(Country)
    )
    return _upsert(target, DimStore, "store_id", _fetch(source, query, where))


def load_dim_customer(source: Session, target: Session, where=None) -> int:
    query = (
        select(
            Customer.customer_id,
            Customer.first_name,
            Customer.last_name,
            Customer.active,
            City.city,
            Country.country,
            Customer.last_update,
        )
        .select_from(Customer)
        .join(Address)
        .join(City)
        .join(Country)
    )
    return _upsert(target, DimCustomer, "customer_id", _fetch(source, query, where))


# --------------------
#  Bridges


def load_bridge_film_actor(source: Session, target: Session, where=None) -> int:
    film_keys = _key_map(target, DimFilm.film_id, DimFilm.film_key)
    actor_keys = _key_map(target, DimActor.actor_id, DimActor.actor_key)

    query = select(FilmActor.film_id, FilmActor.actor_id)
    rows = [
        {
            "film_key": film_keys[row["film_id"]],
            "actor_key": actor_keys[row["actor_id"]],
        }
        for row in _fetch(source, query, where)
    ]
    return _insert_missing(target, BridgeFilmActor, rows)


def load_bridge_film_category(source: Session, target: Session, where=None) -> int:
    film_keys = _key_map(target, DimFilm.film_id, DimFilm.film_key)
    category_keys = _key_map(target, DimCategory.category_id, DimCategory.category_key)

    query = select(FilmCategory.film_id, FilmCategory.category_id)
    rows = [
        {
            "film_key": film_keys[row["film_id"]],
            "category_key": category_keys[row["category_id"]],
        }
        for row in _fetch(source, query, where)
    ]
    return _insert_missing(target, BridgeFilmCategory, rows)


# --------------------
#  Facts


def load_fact_rental(source: Session, target: Session, where=None) -> int:
    film_keys = _key_map(target, DimFilm.film_id, DimFilm.film_key)
    store_keys = _key_map(target, DimStore.store_id, DimStore.store_key)
    customer_keys = _key_map(target, DimCustomer.customer_id, DimCustomer.customer_key)

    # The film and the store come from the rented copy (inventory).
    query = (
        select(
            Rental.rental_id,
            Rental.rental_date,
            Rental.return_date,
            Rental.customer_id,
            Rental.staff_id,
            Inventory.film_id,
            Inventory.store_id,
        )
        .select_from(Rental)
        .join(Inventory)
    )

    rows = []
    dates: set[date] = set()
    for row in _fetch(source, query, where):
        rented = row["rental_date"].date()
        dates.add(rented)

        # A rental that has not been returned keeps both fields NULL.
        date_key_returned = None
        rental_duration_days = None
        if row["return_date"] is not None:
            returned = row["return_date"].date()
            dates.add(returned)
            date_key_returned = _to_date_key(returned)
            rental_duration_days = (returned - rented).days

        rows.append(
            {
                "rental_id": row["rental_id"],
                "date_key_rented": _to_date_key(rented),
                "date_key_returned": date_key_returned,
                "film_key": film_keys[row["film_id"]],
                "store_key": store_keys[row["store_id"]],
                "customer_key": customer_keys[row["customer_id"]],
                "staff_id": row["staff_id"],
                "rental_duration_days": rental_duration_days,
            }
        )

    _ensure_dates(target, dates)
    return _upsert(target, FactRental, "rental_id", rows)


def load_fact_payment(source: Session, target: Session, where=None) -> int:
    store_keys = _key_map(target, DimStore.store_id, DimStore.store_key)
    customer_keys = _key_map(target, DimCustomer.customer_id, DimCustomer.customer_key)

    # Outer joins: a payment without a rental has
    # rental_store_id = NULL.
    query = (
        select(
            Payment.payment_id,
            Payment.payment_date,
            Payment.customer_id,
            Payment.staff_id,
            Payment.amount,
            Inventory.store_id.label("rental_store_id"),
            Staff.store_id.label("staff_store_id"),
        )
        .select_from(Payment)
        .join(Staff, Payment.staff_id == Staff.staff_id)
        .outerjoin(Rental, Payment.rental_id == Rental.rental_id)
        .outerjoin(Inventory, Rental.inventory_id == Inventory.inventory_id)
    )

    rows = []
    dates: set[date] = set()
    for row in _fetch(source, query, where):
        paid = row["payment_date"].date()
        dates.add(paid)

        # Store of the rented copy; if no rental -> staff member's store.
        store_id = row["rental_store_id"]
        if store_id is None:
            store_id = row["staff_store_id"]

        rows.append(
            {
                "payment_id": row["payment_id"],
                "date_key_paid": _to_date_key(paid),
                "customer_key": customer_keys[row["customer_id"]],
                "store_key": store_keys[store_id],
                "staff_id": row["staff_id"],
                "amount": row["amount"],
            }
        )

    _ensure_dates(target, dates)
    return _upsert(target, FactPayment, "payment_id", rows)


# --------------------
#  Sync markers


def read_source_markers(source: Session) -> dict[str, datetime | None]:
    # Most recent last_update of each table
    return {
        model.__tablename__: source.scalar(select(func.max(model.last_update)))
        for model in SourceBase.__subclasses__()
    }


def save_markers(target: Session, markers: dict[str, datetime | None]) -> None:
    for table_name, last_update in markers.items():
        target.merge(SyncState(table_name=table_name, last_update=last_update))


# --------------------
# Command


def run_full_load(source: Session, target: Session) -> None:
    # Read the markers BEFORE the data, so a row that changes while we are
    # loading is picked up again by the next incremental run.
    markers = read_source_markers(source)

    # Dimensions
    log.info("dim_film: %d rows", load_dim_film(source, target))
    log.info("dim_actor: %d rows", load_dim_actor(source, target))
    log.info("dim_category: %d rows", load_dim_category(source, target))
    log.info("dim_store: %d rows", load_dim_store(source, target))
    log.info("dim_customer: %d rows", load_dim_customer(source, target))

    # Bridges (film, actor and cat keys)
    log.info("bridge_film_actor: %d rows", load_bridge_film_actor(source, target))
    log.info("bridge_film_category: %d rows", load_bridge_film_category(source, target))

    # Facts (every dimension key)
    log.info("fact_rental: %d rows", load_fact_rental(source, target))
    log.info("fact_payment: %d rows", load_fact_payment(source, target))

    # Starting markers for incremental
    save_markers(target, markers)
    log.info("sync_state: %d markers saved", len(markers))

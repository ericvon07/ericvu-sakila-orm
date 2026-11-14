import logging
from datetime import datetime

from sqlalchemy import or_, select
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
    Language,
    Payment,
    Rental,
    SourceBase,
    Store,
)
from models.target import SyncState
from sync.full_load import (
    load_bridge_film_actor,
    load_bridge_film_category,
    load_dim_actor,
    load_dim_category,
    load_dim_customer,
    load_dim_film,
    load_dim_store,
    load_fact_payment,
    load_fact_rental,
    read_source_markers,
    save_markers,
)

log = logging.getLogger("sync")

# -------------
# Helpers


def _read_markers(target: Session) -> dict[str, datetime | None]:
    # What sync_state says we have already processed, e.g. {"rental": 2006-02-15 21:30:53}
    rows = target.execute(select(SyncState.table_name, SyncState.last_update))
    return {table_name: last_update for table_name, last_update in rows}


def _changed_since(markers: dict[str, datetime | None], *models: type[SourceBase]):
    # Builds the filter "any of these tables changed since its marker":
    #   customer.last_update >= :m1 OR address.last_update >= :m2 OR ...
    # Uses >= (not >) so rows updated in the same second as the marker are not skipped.
    conditions = []
    for model in models:
        marker = markers.get(model.__tablename__)
        if marker is None:
            # No marker for this table yet: read everything.
            return None
        conditions.append(model.__table__.c.last_update >= marker)
    return or_(*conditions)


# -------------
# Main


def run_incremental(source: Session, target: Session) -> None:
    # Read the last-updated marker of each table from sync_state
    markers = _read_markers(target)

    # Read the new markers BEFORE data.
    new_markers = read_source_markers(source)

    # Query only the rows changed since the marker, then upsert them.
    # Each target table watches every source table its columns come from.

    # Dimensions
    changed = _changed_since(markers, Film, Language)
    log.info("dim_film: %d rows", load_dim_film(source, target, changed))

    changed = _changed_since(markers, Actor)
    log.info("dim_actor: %d rows", load_dim_actor(source, target, changed))

    changed = _changed_since(markers, Category)
    log.info("dim_category: %d rows", load_dim_category(source, target, changed))

    changed = _changed_since(markers, Store, Address, City, Country)
    log.info("dim_store: %d rows", load_dim_store(source, target, changed))

    changed = _changed_since(markers, Customer, Address, City, Country)
    log.info("dim_customer: %d rows", load_dim_customer(source, target, changed))

    # Bridges
    changed = _changed_since(markers, FilmActor)
    log.info(
        "bridge_film_actor: %d rows", load_bridge_film_actor(source, target, changed)
    )

    changed = _changed_since(markers, FilmCategory)
    log.info(
        "bridge_film_category: %d rows",
        load_bridge_film_category(source, target, changed),
    )

    # Facts
    changed = _changed_since(markers, Rental)
    log.info("fact_rental: %d rows", load_fact_rental(source, target, changed))

    changed = _changed_since(markers, Payment)
    log.info("fact_payment: %d rows", load_fact_payment(source, target, changed))

    # Save the new markers. Table with no rows has no MAX(last_update), so it keeps the prev marker.
    for table_name, last_update in new_markers.items():
        if last_update is None:
            new_markers[table_name] = markers.get(table_name)
    save_markers(target, new_markers)
    log.info("sync_state: %d markers saved", len(new_markers))

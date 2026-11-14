from datetime import datetime

import pytest
from sqlalchemy import func, inspect, select, update

from models.source import Customer, Film, Payment, Rental
from models.target import DimCustomer, DimFilm, FactPayment, FactRental, TargetBase
from sync.full_load import run_full_load
from sync.incremental import run_incremental
from sync.init import run_init
from sync.validate import ValidationError, run_validate

# ------------------
# Setup/helpers


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def find(session, column, value):
    # The single row where column == value.
    return session.scalars(select(column.class_).where(column == value)).one()


def init_and_load(source, target) -> None:
    run_init(source, target)
    run_full_load(source, target)
    target.commit()


# -------------------
# Proper tests


def test_init(source, target):
    run_init(source, target)

    tables = inspect(target.get_bind()).get_table_names()
    assert set(tables) == set(TargetBase.metadata.tables)


def test_full_load(source, target):
    init_and_load(source, target)

    assert count(target, DimFilm) == count(source, Film)
    assert count(target, DimCustomer) == count(source, Customer)
    assert count(target, FactRental) == count(source, Rental)
    assert count(target, FactPayment) == count(source, Payment)
    assert find(target, FactRental.rental_id, 3818).rental_duration_days == 5


def test_incremental_new_data(source, target):
    init_and_load(source, target)

    rental = Rental(
        rental_date=datetime(2006, 3, 1, 12, 0),
        inventory_id=1,
        customer_id=97,
        staff_id=1,
        last_update=func.now(),
    )
    source.add(rental)
    source.commit()

    run_incremental(source, target)

    new_row = find(target, FactRental.rental_id, rental.rental_id)
    assert new_row.date_key_rented == 20060301
    assert count(target, FactRental) == count(source, Rental)


def test_incremental_updates(source, target):
    init_and_load(source, target)

    source.get(Rental, 11496).return_date = datetime(2006, 2, 20, 10, 0)
    source.get(Customer, 97).address_id = 1  # address 1 is in Lethbridge
    source.commit()

    run_incremental(source, target)

    assert find(target, FactRental.rental_id, 11496).date_key_returned == 20060220
    assert find(target, DimCustomer.customer_id, 97).city == "Lethbridge"
    assert count(target, FactRental) == count(source, Rental)


def test_validate(source, target):
    init_and_load(source, target)

    run_validate(source, target)

    # Payment 145 is inside the 30-day period
    target.execute(
        update(FactPayment).where(FactPayment.payment_id == 145).values(amount=999)
    )
    with pytest.raises(ValidationError):
        run_validate(
            source, target
        )  # swap value for payment_id 145 and check if val error is raised

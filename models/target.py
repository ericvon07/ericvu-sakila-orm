from datetime import date as date_type, datetime
from sqlalchemy import ForeignKey, String, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from decimal import Decimal


class TargetBase(DeclarativeBase):
    pass


# --------------------
# Dimensions


class DimDate(TargetBase):
    __tablename__ = "dim_date"

    # date_key is computed in form (YYYYMMDD), so SQLite must not generate it.
    date_key: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    date: Mapped[date_type] = mapped_column(
        unique=True
    )  # date_type bc it'd conflict otherwise
    year: Mapped[int]
    quarter: Mapped[int]
    month: Mapped[int]
    day_of_month: Mapped[int]
    day_of_week: Mapped[int]
    is_weekend: Mapped[int]


class DimFilm(TargetBase):
    __tablename__ = "dim_film"

    film_key: Mapped[int] = mapped_column(primary_key=True)
    film_id: Mapped[int] = mapped_column(unique=True)
    title: Mapped[str] = mapped_column(String(128))
    rating: Mapped[str | None] = mapped_column(String(5))
    length: Mapped[int | None]
    language: Mapped[str] = mapped_column(String(20))
    release_year: Mapped[int | None]
    last_update: Mapped[datetime]


class DimActor(TargetBase):
    __tablename__ = "dim_actor"

    actor_key: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(unique=True)
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    last_update: Mapped[datetime]


class DimCategory(TargetBase):
    __tablename__ = "dim_category"

    category_key: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(25))
    last_update: Mapped[datetime]


class DimStore(TargetBase):
    __tablename__ = "dim_store"

    store_key: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(unique=True)
    city: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(50))
    last_update: Mapped[datetime]


class DimCustomer(TargetBase):
    __tablename__ = "dim_customer"

    customer_key: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(unique=True)
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    active: Mapped[bool]
    city: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(50))
    last_update: Mapped[datetime]


# --------------------
# Bridge Tables


class BridgeFilmActor(TargetBase):
    __tablename__ = "bridge_film_actor"

    film_key: Mapped[int] = mapped_column(
        ForeignKey("dim_film.film_key"), primary_key=True
    )
    actor_key: Mapped[int] = mapped_column(
        ForeignKey("dim_actor.actor_key"), primary_key=True, index=True
    )


class BridgeFilmCategory(TargetBase):
    __tablename__ = "bridge_film_category"

    film_key: Mapped[int] = mapped_column(
        ForeignKey("dim_film.film_key"), primary_key=True
    )
    category_key: Mapped[int] = mapped_column(
        ForeignKey("dim_category.category_key"), primary_key=True, index=True
    )


# --------------------
# Facts


class FactRental(TargetBase):
    __tablename__ = "fact_rental"

    fact_rental_key: Mapped[int] = mapped_column(primary_key=True)
    rental_id: Mapped[int] = mapped_column(unique=True)
    date_key_rented: Mapped[int] = mapped_column(
        ForeignKey("dim_date.date_key"), index=True
    )
    date_key_returned: Mapped[int | None] = mapped_column(
        ForeignKey("dim_date.date_key"), index=True
    )
    film_key: Mapped[int] = mapped_column(ForeignKey("dim_film.film_key"), index=True)
    store_key: Mapped[int] = mapped_column(
        ForeignKey("dim_store.store_key"), index=True
    )
    customer_key: Mapped[int] = mapped_column(
        ForeignKey("dim_customer.customer_key"), index=True
    )
    staff_id: Mapped[int]
    rental_duration_days: Mapped[int | None]


class FactPayment(TargetBase):
    __tablename__ = "fact_payment"

    fact_payment_key: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(unique=True)
    date_key_paid: Mapped[int] = mapped_column(
        ForeignKey("dim_date.date_key"), index=True
    )
    customer_key: Mapped[int] = mapped_column(
        ForeignKey("dim_customer.customer_key"), index=True
    )
    store_key: Mapped[int] = mapped_column(
        ForeignKey("dim_store.store_key"), index=True
    )
    staff_id: Mapped[int]
    amount: Mapped[Decimal] = mapped_column(Numeric(5, 2))


# --------------------
# Sync control


class SyncState(TargetBase):
    __tablename__ = "sync_state"

    # One row per Sakila source table
    table_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_update: Mapped[datetime | None]

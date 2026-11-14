from datetime import datetime
from sqlalchemy import ForeignKey, String, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from decimal import Decimal

# To check PKs and FKs on Docker Container:
# grep -E "CREATE TABLE|PRIMARY KEY|FOREIGN KEY" docker/initdb/01-sakila-schema.sql

# Third party sources used:

# https://docs.sqlalchemy.org/en/21/orm/declarative_styles.html -> learned about what a declarative base is
# https://docs.sqlalchemy.org/en/21/orm/mapping_styles.html -> Learned how to implement the Mapped[xx] datatype structure. And the mapped_column() function.


class SourceBase(DeclarativeBase):
    pass


class Film(SourceBase):
    __tablename__ = "film"

    film_id: Mapped[int] = mapped_column(primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("language.language_id"))
    title: Mapped[str] = mapped_column(String(128))
    rating: Mapped[str | None] = mapped_column(String(5))
    length: Mapped[int | None]
    release_year: Mapped[int | None]
    last_update: Mapped[datetime]


class Language(SourceBase):
    __tablename__ = "language"

    language_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
    last_update: Mapped[datetime]


class Actor(SourceBase):
    __tablename__ = "actor"

    actor_id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    last_update: Mapped[datetime]


class Category(SourceBase):
    __tablename__ = "category"

    category_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(25))
    last_update: Mapped[datetime]


class FilmActor(SourceBase):
    __tablename__ = "film_actor"

    film_id: Mapped[int] = mapped_column(ForeignKey("film.film_id"), primary_key=True)
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("actor.actor_id"), primary_key=True
    )
    last_update: Mapped[datetime]


class FilmCategory(SourceBase):
    __tablename__ = "film_category"

    film_id: Mapped[int] = mapped_column(ForeignKey("film.film_id"), primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.category_id"), primary_key=True
    )
    last_update: Mapped[datetime]


class Inventory(SourceBase):
    __tablename__ = "inventory"

    inventory_id: Mapped[int] = mapped_column(primary_key=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("film.film_id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("store.store_id"))
    last_update: Mapped[datetime]


class Rental(SourceBase):
    __tablename__ = "rental"

    rental_id: Mapped[int] = mapped_column(primary_key=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.inventory_id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.customer_id"))
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.staff_id"))
    rental_date: Mapped[datetime]
    return_date: Mapped[datetime | None]
    last_update: Mapped[datetime]


class Payment(SourceBase):
    __tablename__ = "payment"

    payment_id: Mapped[int] = mapped_column(primary_key=True)
    rental_id: Mapped[int | None] = mapped_column(ForeignKey("rental.rental_id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.customer_id"))
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.staff_id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    payment_date: Mapped[datetime]
    last_update: Mapped[datetime]


class Store(SourceBase):
    __tablename__ = "store"

    store_id: Mapped[int] = mapped_column(primary_key=True)
    address_id: Mapped[int] = mapped_column(ForeignKey("address.address_id"))
    last_update: Mapped[datetime]


class Staff(SourceBase):
    __tablename__ = "staff"

    staff_id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("store.store_id"))
    last_update: Mapped[datetime]


class Customer(SourceBase):
    __tablename__ = "customer"

    customer_id: Mapped[int] = mapped_column(primary_key=True)
    address_id: Mapped[int] = mapped_column(ForeignKey("address.address_id"))
    first_name: Mapped[str] = mapped_column(String(45))
    last_name: Mapped[str] = mapped_column(String(45))
    active: Mapped[bool]
    last_update: Mapped[datetime]


class Address(SourceBase):
    __tablename__ = "address"

    address_id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("city.city_id"))
    last_update: Mapped[datetime]


class City(SourceBase):
    __tablename__ = "city"

    city_id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(50))
    country_id: Mapped[int] = mapped_column(ForeignKey("country.country_id"))
    last_update: Mapped[datetime]


class Country(SourceBase):
    __tablename__ = "country"

    country_id: Mapped[int] = mapped_column(primary_key=True)
    country: Mapped[str] = mapped_column(String(50))
    last_update: Mapped[datetime]

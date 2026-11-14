from sqlalchemy import func, select

from connection.db import create_source_sessionmaker
from models.source import Address, City, Country, Customer, SourceBase

# Note for grading: I used generative AI to build this test script for the models module.
# Debugging purposes only

EXPECTED = {
    "film": 1000,
    "language": 6,
    "actor": 200,
    "category": 16,
    "film_actor": 5462,
    "film_category": 1000,
    "inventory": 4581,
    "rental": 16044,
    "payment": 16049,
    "store": 2,
    "staff": 2,
    "customer": 599,
    "address": 603,
    "city": 600,
    "country": 109,
}

Session = create_source_sessionmaker()

with Session() as session:
    # 1) Counting and reading 1 line for each model.
    for model in SourceBase.__subclasses__():
        table = model.__tablename__
        total = session.scalar(select(func.count()).select_from(model))
        first = session.scalars(select(model).limit(1)).first()
        status = "OK" if total == EXPECTED[table] else f"ESPERADO {EXPECTED[table]}"
        print(f"{table:15} {total:6} {first.last_update}  {status}")

    # 2) Join customer -> address -> city -> country
    row = session.execute(
        select(Customer.first_name, Customer.last_name, City.city, Country.country)
        .select_from(Customer)
        .join(Address)
        .join(City)
        .join(Country)
        .where(Customer.customer_id == 97)
    ).one()
    print(row)

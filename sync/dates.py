from models.target import DimDate
from datetime import date


def _to_date_key(d: date) -> int:
    # goes from 2000-10-10 to 20001010 (e.g.)
    return d.year * 10000 + d.month * 100 + d.day


def build_dim_date(d: date) -> DimDate:
    # ISO
    days_of_week = d.isoweekday()

    return DimDate(
        date_key=_to_date_key(d),
        date=d,
        year=d.year,
        quarter=(d.month - 1) // 3 + 1,
        month=d.month,
        day_of_month=d.day,
        day_of_week=days_of_week,
        is_weekend=1 if days_of_week > 5 else 0,
    )

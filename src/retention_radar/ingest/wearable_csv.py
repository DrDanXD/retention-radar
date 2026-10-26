"""Daily summary CSV adapter for wearables.

Most wearable platforms (Garmin Connect, Oura, Whoop) can export one row per day.
Column names differ by vendor, so this adapter only needs a date column. A day
counts as synced when at least one metric column on that row has a non-zero value.
Rows that are all blank or zero are the device sitting in a drawer.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from retention_radar.models import WearableSync

DATE_COLUMNS = ("date", "day", "calendarDate", "summary_date")


def _has_data(row: dict[str, str], date_col: str) -> bool:
    for key, value in row.items():
        if key == date_col or value is None:
            continue
        v = value.strip()
        if not v:
            continue
        try:
            if float(v) != 0:
                return True
        except ValueError:
            continue
    return False


def syncs_from_daily_csv(path: str | Path, source: str = "wearable") -> list[WearableSync]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        date_col = next((c for c in DATE_COLUMNS if c in fields), None)
        if date_col is None:
            raise ValueError(f"No date column found. Expected one of {DATE_COLUMNS}")
        days = {
            date.fromisoformat(row[date_col][:10])
            for row in reader
            if row.get(date_col) and _has_data(row, date_col)
        }
    return [WearableSync(day=d, source=source) for d in sorted(days)]

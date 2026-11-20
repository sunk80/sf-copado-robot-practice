"""Small pure-Python helpers shared by the Salesforce libraries.

Nothing in here talks to Salesforce or Robot Framework, so it can be unit-tested
on its own and reused anywhere (locally, GitHub Actions, Copado CRT).
"""
from __future__ import annotations

import csv
from typing import Iterable, Iterator

TRUTHY = {"true", "1", "yes", "y", "on"}


def truthy(value) -> bool:
    """Interpret Robot/CLI style values ('True', 'false', '1', 'yes') as booleans."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUTHY


def clean_record(record: dict) -> dict:
    """Drop the 'attributes' metadata Salesforce adds to every record (recursively)."""
    cleaned = {}
    for key, value in record.items():
        if key == "attributes":
            continue
        cleaned[key] = clean_record(value) if isinstance(value, dict) else value
    return cleaned


def dig(record, dotted: str):
    """Read 'Account.Name' style paths from a SOQL result, case-insensitively."""
    current = record
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        match = next((k for k in current if k.lower() == part.lower()), None)
        current = current.get(match) if match else None
    return current


def same_value(expected, actual) -> bool:
    """Compare a value from a test/CSV (usually a string) with a Salesforce value."""
    exp = "" if expected is None else str(expected).strip()
    if actual is None:
        return exp == ""
    if isinstance(actual, bool):
        return exp.lower() == str(actual).lower()
    if isinstance(actual, (int, float)):
        try:
            return float(exp) == float(actual)
        except ValueError:
            return False
    act = str(actual).strip()
    if exp == act:
        return True
    # Date in source (2026-01-31) vs datetime in org (2026-01-31T00:00:00.000+0000)
    if len(exp) == 10 and act.startswith(exp) and "T" in act:
        return True
    return False


def read_csv(path: str) -> tuple[list[str], list[dict]]:
    """Return (headers, rows) from a CSV file, tolerating a UTF-8 BOM."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def write_csv(path: str, headers: list[str], rows: Iterable[dict]) -> str:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def chunks(items: list, size: int) -> Iterator[list]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def soql_quote(value: str) -> str:
    """Escape a value for use inside single quotes in SOQL."""
    return str(value).replace("\\", "\\\\").replace("'", "\\'")

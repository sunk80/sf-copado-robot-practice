"""Test data helpers: unique names, run ids, synthetic CSV files, sampling.

Faker is used when installed; a simple built-in generator is the fallback.
All generated records carry the run prefix so leftovers are easy to clean up.
"""
from __future__ import annotations

import itertools
import os
import random
from datetime import datetime

from robot.api.deco import keyword, library

from sfutil import read_csv, truthy, write_csv

try:
    from faker import Faker
except ImportError:  # pragma: no cover
    Faker = None

INDUSTRIES = ["Insurance", "Banking", "Finance", "Technology", "Healthcare",
              "Manufacturing", "Retail", "Energy", "Transportation", "Consulting"]
CITIES = [("Atlanta", "GA"), ("Chicago", "IL"), ("Boston", "MA"), ("Austin", "TX"),
          ("Denver", "CO"), ("Seattle", "WA"), ("Miami", "FL"), ("Phoenix", "AZ")]
ACCOUNT_HEADERS = ["Name", "Industry", "Phone", "BillingCity", "BillingState",
                   "NumberOfEmployees", "Description"]


def _run_id() -> str:
    return os.getenv("GITHUB_RUN_ID") or datetime.now().strftime("%m%d%H%M%S")


def account_rows(rows: int, prefix: str, run_id: str, seed: int | None = None) -> list[dict]:
    rng = random.Random(seed)
    fake = Faker() if Faker else None
    if fake and seed is not None:
        fake.seed_instance(seed)
    data = []
    for n in range(1, int(rows) + 1):
        company = fake.company() if fake else f"Company {rng.randint(1000, 9999)}"
        city, state = rng.choice(CITIES)
        data.append({
            "Name": f"{prefix}-BULK-{run_id}-{n:05d} {company}"[:255],
            "Industry": rng.choice(INDUSTRIES),
            "Phone": f"555-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
            "BillingCity": city,
            "BillingState": state,
            "NumberOfEmployees": str(rng.randint(5, 5000)),
            "Description": f"Synthetic test data from run {run_id}",
        })
    return data


@library(scope="GLOBAL", auto_keywords=False)
class TestData:
    """Unique names and synthetic CSV files for Salesforce tests."""

    def __init__(self):
        self.run_id = _run_id()
        self._counter = itertools.count(1)

    @keyword
    def get_run_id(self) -> str:
        return self.run_id

    @keyword
    def unique_name(self, prefix: str) -> str:
        """e.g. ``RFPOC-Acct-1119211500-003`` - unique per run, easy to find and clean up."""
        return f"{prefix}-{self.run_id}-{next(self._counter):03d}"

    @keyword
    def is_truthy(self, value) -> bool:
        """Turn True/false/1/yes style variables into a real boolean."""
        return truthy(value)

    @keyword
    def generate_account_csv(self, path: str, rows: int = 200, prefix: str = "RFPOC") -> str:
        """Write a synthetic Account CSV (Name, Industry, Phone, BillingCity, ...)."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        write_csv(path, ACCOUNT_HEADERS, account_rows(int(rows), prefix, self.run_id))
        return path

    @keyword
    def pick_sample_rows(self, csv_file: str, count: int = 3) -> list:
        """Random rows from a CSV (e.g. bulk success results) for UI spot checks."""
        _, rows = read_csv(csv_file)
        count = min(int(count), len(rows))
        return random.sample(rows, count) if count else []

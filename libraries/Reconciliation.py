"""Reconcile a bulk load: compare what was sent with what is now in the org.

The comparison logic (``build_reconciliation``) is pure Python so it can be
unit-tested without an org; the keyword fetches the org data and writes a CSV report.
"""
from __future__ import annotations

import os
import random
from datetime import datetime

from robot.api import logger
from robot.api.deco import keyword, library
from robot.libraries.BuiltIn import BuiltIn

from sfutil import chunks, dig, read_csv, same_value, soql_quote, write_csv

REPORT_HEADERS = ["status", "row", "record_id", "field", "expected", "actual", "error"]


def comparable_fields(headers: list[str], org_field_names: set[str]) -> list[str]:
    """CSV columns worth comparing: real fields on the object, excluding Ids and sf__ columns."""
    return [h for h in headers
            if not h.startswith("sf__") and "." not in h and h.lower() != "id"
            and h.lower() in org_field_names]


def build_reconciliation(success_rows: list[dict], failed_rows: list[dict],
                         org_by_id: dict[str, dict], fields: list[str]) -> tuple[dict, list[dict]]:
    """Return (summary, report_rows) for success/failed result rows vs org records."""
    report, matched, mismatched, missing = [], 0, 0, 0
    for index, row in enumerate(success_rows, start=1):
        record_id = row.get("sf__Id", "")
        org = org_by_id.get(record_id)
        if org is None:
            missing += 1
            report.append({"status": "MISSING", "row": index, "record_id": record_id})
            continue
        diffs = [(f, row.get(f, ""), dig(org, f)) for f in fields if not same_value(row.get(f, ""), dig(org, f))]
        if diffs:
            mismatched += 1
            report.extend({"status": "MISMATCH", "row": index, "record_id": record_id,
                           "field": f, "expected": e, "actual": a} for f, e, a in diffs)
        else:
            matched += 1
    for index, row in enumerate(failed_rows, start=1):
        report.append({"status": "LOAD_FAILED", "row": index, "record_id": row.get("sf__Id", ""),
                       "error": row.get("sf__Error", "")})
    summary = {"checked": len(success_rows), "matched": matched, "mismatched": mismatched,
               "missing": missing, "load_failed": len(failed_rows), "fields_compared": fields}
    return summary, report


@library(scope="GLOBAL", auto_keywords=False)
class Reconciliation:
    """Source-vs-org reconciliation for bulk loads."""

    @staticmethod
    def _api():
        return BuiltIn().get_library_instance("SalesforceAPI")

    @keyword
    def reconcile_bulk_load(self, job: dict, sample_size: int = 0, report_dir: str = "results/recon") -> dict:
        """Compare every (or a random sample of) loaded row with the org and write a CSV report.

        ``sample_size=0`` checks all rows. Returns a summary dictionary that also
        holds ``source_rows`` and ``report_file``.
        """
        api = self._api()
        object_name = job["object"]
        headers, success_rows = read_csv(job["success_file"])
        _, failed_rows = read_csv(job["failed_file"])
        org_fields = {f["name"].lower() for f in api.describe_fields(object_name)}
        fields = comparable_fields(headers, org_fields)

        to_check = success_rows
        if int(sample_size) and len(success_rows) > int(sample_size):
            to_check = random.sample(success_rows, int(sample_size))

        org_by_id: dict[str, dict] = {}
        select = ", ".join(["Id", *fields])
        for batch in chunks([r["sf__Id"] for r in to_check if r.get("sf__Id")], 200):
            id_list = ", ".join(f"'{soql_quote(i)}'" for i in batch)
            for record in api.query_records(f"SELECT {select} FROM {object_name} WHERE Id IN ({id_list})"):
                org_by_id[record["Id"]] = record
                org_by_id[record["Id"][:15]] = record  # tolerate 15/18-char Ids

        summary, report = build_reconciliation(to_check, failed_rows, org_by_id, fields)
        summary["source_rows"] = len(success_rows) + len(failed_rows)
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, f"recon_{object_name}_{datetime.now():%Y%m%d_%H%M%S}.csv")
        summary["report_file"] = write_csv(path, REPORT_HEADERS, report)
        logger.info(
            f"Reconciliation: checked={summary['checked']} matched={summary['matched']} "
            f"mismatched={summary['mismatched']} missing={summary['missing']} "
            f"load_failed={summary['load_failed']} -> {path}"
        )
        return summary

    @keyword
    def reconciliation_should_pass(self, summary: dict, max_mismatched: int = 0, max_load_failed: int = 0) -> None:
        problems = []
        if summary["missing"]:
            problems.append(f"{summary['missing']} loaded record(s) not found in the org")
        if summary["mismatched"] > int(max_mismatched):
            problems.append(f"{summary['mismatched']} record(s) with field mismatches")
        if summary["load_failed"] > int(max_load_failed):
            problems.append(f"{summary['load_failed']} row(s) failed to load")
        if problems:
            raise AssertionError("; ".join(problems) + f". Report: {summary['report_file']}")

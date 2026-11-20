"""Bulk API 2.0 keywords: pre-check a CSV, load it, download results, roll back.

Uses the session from the SalesforceAPI library and plain REST calls, so there is
no extra dependency and the same code works locally, in CI and in Copado CRT.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

from robot.api import logger
from robot.api.deco import keyword, library
from robot.libraries.BuiltIn import BuiltIn

from sfutil import read_csv, truthy, write_csv

FINAL_STATES = {"JobComplete", "Failed", "Aborted"}
OPERATIONS = {"insert", "update", "upsert", "delete"}


@library(scope="GLOBAL", auto_keywords=False)
class SalesforceBulk:
    """Bulk API 2.0 ingest jobs with result files for reconciliation."""

    def __init__(self, poll_seconds: float = 5, timeout_seconds: float = 900):
        self.poll_seconds = float(poll_seconds)
        self.timeout_seconds = float(timeout_seconds)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _api():
        return BuiltIn().get_library_instance("SalesforceAPI")

    def _request(self, method: str, path: str, **kwargs):
        sf = self._api()._client()
        headers = dict(sf.headers)
        headers.update(kwargs.pop("headers", {}))
        response = sf.session.request(method, f"{sf.base_url}{path}", headers=headers, timeout=120, **kwargs)
        if response.status_code >= 400:
            raise AssertionError(f"Bulk API {method} {path} failed ({response.status_code}): {response.text}")
        return response

    # ------------------------------------------------------------------ pre-check
    @keyword
    def precheck_bulk_file(self, csv_file: str, object_name: str, operation: str = "insert",
                           external_id_field: str | None = None, max_rows: int = 1000) -> dict:
        """Validate a CSV before loading: columns exist, required fields present, row limits.

        ``max_rows`` protects small orgs (a Developer Edition has about 5 MB of data storage).
        """
        operation = operation.lower()
        if operation not in OPERATIONS:
            raise ValueError(f"operation must be one of {sorted(OPERATIONS)}")
        if not os.path.exists(csv_file):
            raise AssertionError(f"File not found: {csv_file}")
        headers, rows = read_csv(csv_file)
        fields = {f["name"].lower(): f for f in self._api().describe_fields(object_name)}
        problems = []

        if not rows:
            problems.append("File has no data rows.")
        if len(rows) > int(max_rows):
            problems.append(f"{len(rows)} rows exceeds MAX_ROWS={max_rows}.")

        plain_headers = [h for h in headers if "." not in h]  # Parent.ExternalId__c style refs allowed
        unknown = [h for h in plain_headers if h.lower() not in fields]
        if unknown:
            problems.append(f"Columns not found on {object_name}: {', '.join(unknown)}")

        lower_headers = {h.lower() for h in headers}
        if operation in {"update", "delete"} and "id" not in lower_headers:
            problems.append(f"'{operation}' needs an Id column.")
        if operation == "upsert":
            if not external_id_field:
                problems.append("'upsert' needs EXTERNAL_ID (an external Id field name).")
            elif external_id_field.lower() not in lower_headers:
                problems.append(f"External Id column '{external_id_field}' is missing.")

        if operation == "insert":
            required = [f["name"] for f in fields.values()
                        if f["createable"] and not f["nillable"] and not f["defaultedOnCreate"]
                        and f["type"] != "boolean"]
            missing = [r for r in required if r.lower() not in lower_headers]
            if missing:
                problems.append(f"Required fields missing for insert: {', '.join(missing)}")
            for req in required:
                column = next((h for h in headers if h.lower() == req.lower()), None)
                if column:
                    blanks = sum(1 for row in rows if not (row.get(column) or "").strip())
                    if blanks:
                        problems.append(f"{blanks} row(s) have blank required field {column}.")

        summary = {"file": csv_file, "object": object_name, "operation": operation,
                   "rows": len(rows), "columns": headers, "problems": problems}
        if problems:
            raise AssertionError("Pre-check failed:\n  " + "\n  ".join(problems))
        logger.info(f"Pre-check passed: {len(rows)} row(s), columns={headers}")
        return summary

    # ------------------------------------------------------------------ load
    @keyword
    def run_bulk_job(self, object_name: str, operation: str, csv_file: str,
                     external_id_field: str | None = None, results_dir: str = "results/bulk") -> dict:
        """Create a Bulk API 2.0 job, upload the CSV, wait, and save result files.

        Returns a dictionary: job_id, state, processed, failed, success_file,
        failed_file, unprocessed_file, error_message.
        """
        operation = operation.lower()
        with open(csv_file, "rb") as handle:
            data = handle.read()
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]  # strip UTF-8 BOM
        body = {"object": object_name, "operation": operation, "contentType": "CSV",
                "lineEnding": "CRLF" if b"\r\n" in data else "LF"}
        if operation == "upsert":
            body["externalIdFieldName"] = external_id_field

        job = self._request("POST", "jobs/ingest/", json=body).json()
        job_id = job["id"]
        logger.info(f"Bulk job {job_id} created ({operation} {object_name})")
        self._request("PUT", f"jobs/ingest/{job_id}/batches", data=data,
                      headers={"Content-Type": "text/csv"})
        self._request("PATCH", f"jobs/ingest/{job_id}/", json={"state": "UploadComplete"})

        info = self._wait_for_job(job_id)
        os.makedirs(results_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files = {}
        for kind, path in (("success_file", "successfulResults/"),
                           ("failed_file", "failedResults/"),
                           ("unprocessed_file", "unprocessedrecords/")):
            target = os.path.join(results_dir, f"{object_name}_{operation}_{stamp}_{kind.split('_')[0]}.csv")
            content = self._request("GET", f"jobs/ingest/{job_id}/{path}").content
            with open(target, "wb") as handle:
                handle.write(content)
            files[kind] = target

        result = {"job_id": job_id, "state": info["state"], "object": object_name, "operation": operation,
                  "processed": int(info.get("numberRecordsProcessed", 0)),
                  "failed": int(info.get("numberRecordsFailed", 0)),
                  "error_message": info.get("errorMessage", ""), **files}
        logger.info(f"Bulk job {job_id}: state={result['state']} processed={result['processed']} "
                    f"failed={result['failed']}")
        return result

    def _wait_for_job(self, job_id: str) -> dict:
        deadline = time.time() + self.timeout_seconds
        while True:
            info = self._request("GET", f"jobs/ingest/{job_id}/").json()
            if info["state"] in FINAL_STATES:
                return info
            if time.time() > deadline:
                raise AssertionError(f"Bulk job {job_id} still '{info['state']}' after {self.timeout_seconds}s")
            time.sleep(self.poll_seconds)

    @keyword
    def bulk_job_should_succeed(self, job: dict, max_failed: int = 0) -> None:
        if job["state"] != "JobComplete":
            raise AssertionError(f"Bulk job {job['job_id']} ended '{job['state']}': {job['error_message']}")
        if job["failed"] > int(max_failed):
            raise AssertionError(f"{job['failed']} record(s) failed (allowed {max_failed}). "
                                 f"See {job['failed_file']}")

    # ------------------------------------------------------------------ rollback / cleanup
    @keyword
    def bulk_delete_ids(self, object_name: str, ids: list, results_dir: str = "results/bulk") -> dict | None:
        """Delete records by Id with a Bulk API 2.0 delete job."""
        ids = [i for i in ids if i]
        if not ids:
            logger.info("Nothing to delete.")
            return None
        os.makedirs(results_dir, exist_ok=True)
        path = os.path.join(results_dir, f"{object_name}_delete_ids_{datetime.now():%Y%m%d_%H%M%S}.csv")
        write_csv(path, ["Id"], ({"Id": i} for i in ids))
        return self.run_bulk_job(object_name, "delete", path, results_dir=results_dir)

    @keyword
    def rollback_bulk_job(self, job: dict | None, keep=False) -> None:
        """Delete records a job *created* (insert/upsert). Updates are never rolled back."""
        if not job:
            return
        if truthy(keep):
            logger.info("KEEP=True: loaded data left in the org.")
            return
        if job["operation"] not in {"insert", "upsert"}:
            logger.warn(f"No automatic rollback for '{job['operation']}' jobs; original values are not stored.")
            return
        _, rows = read_csv(job["success_file"])
        created = [r["sf__Id"] for r in rows if truthy(r.get("sf__Created", "true"))]
        logger.info(f"Rolling back {len(created)} created {job['object']} record(s)")
        self.bulk_delete_ids(job["object"], created)

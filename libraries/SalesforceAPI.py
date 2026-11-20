"""Salesforce REST + SOQL keywords for Robot Framework.

Deliberately tool-agnostic: it only uses simple-salesforce, so the same keywords
run on your laptop, in GitHub Actions and later inside Copado Robotic Testing.

Security note: the access token never passes through a Robot keyword argument or
return value, so it never appears in log.html / output.xml (important for a
public repository, where CI artifacts can be downloaded).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from urllib.parse import quote

from robot.api import logger
from robot.api.deco import keyword, library
from robot.libraries.BuiltIn import BuiltIn
from simple_salesforce import Salesforce
from simple_salesforce.exceptions import SalesforceError, SalesforceResourceNotFound

from sfutil import clean_record, dig, same_value, soql_quote, truthy


@library(scope="GLOBAL", auto_keywords=False)
class SalesforceAPI:
    """Connect to a Salesforce org and create, read, update, delete and query records."""

    def __init__(self, api_version: str = "62.0"):
        self.api_version = str(api_version)
        self.sf: Salesforce | None = None
        self._instance_url: str | None = None
        self._token: str | None = None
        self._created: list[tuple[str, str]] = []

    # ------------------------------------------------------------------ connection
    @keyword
    def connect_to_salesforce(self, org_alias: str | None = None) -> str:
        """Connect using SF_ACCESS_TOKEN + SF_INSTANCE_URL, or else the Salesforce CLI alias.

        Locally: run ``sf org login web --alias devorg`` once.
        In CI: the workflow logs the CLI in from the SFDX_AUTH_URL secret.
        Returns the instance URL (never the token).
        """
        token = os.getenv("SF_ACCESS_TOKEN")
        url = os.getenv("SF_INSTANCE_URL")
        if not (token and url):
            alias = org_alias or os.getenv("SF_ORG_ALIAS", "devorg")
            token, url = self._credentials_from_cli(alias)
        self._token, self._instance_url = token, url.rstrip("/")
        self.sf = Salesforce(instance_url=self._instance_url, session_id=token, version=self.api_version)
        logger.info(f"Connected to {self._instance_url} (API v{self.api_version})")
        return self._instance_url

    @staticmethod
    def _credentials_from_cli(alias: str) -> tuple[str, str]:
        exe = shutil.which("sf")
        if not exe:
            raise RuntimeError(
                "Salesforce CLI 'sf' not found. Install it (npm install -g @salesforce/cli) "
                "or set SF_ACCESS_TOKEN and SF_INSTANCE_URL."
            )
        def run(*args: str) -> dict:
            proc = subprocess.run([exe, *args, "--json"], capture_output=True, text=True, timeout=180)
            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError as err:
                raise RuntimeError(f"Could not read 'sf {' '.join(args)}' output: {proc.stderr.strip()}") from err
            if data.get("status") != 0 or "result" not in data:
                raise RuntimeError(
                    f"'sf {' '.join(args)}' failed for alias '{alias}': {data.get('message')}. "
                    f"Log in first: sf org login web --alias {alias}"
                )
            return data["result"]

        info = run("org", "display", "--target-org", alias)
        # Recent CLI versions redact the token in 'org display'; a dedicated command reveals it.
        token = info.get("accessToken", "")
        if not token or "REDACTED" in token.upper():
            token = run("org", "auth", "show-access-token", "--target-org", alias).get("accessToken", "")
        if not token:
            raise RuntimeError(f"Could not obtain an access token for alias '{alias}' from the Salesforce CLI.")
        return token, info["instanceUrl"]

    def _client(self) -> Salesforce:
        if self.sf is None:
            raise RuntimeError("Not connected. Call 'Connect To Salesforce' first (e.g. in Suite Setup).")
        return self.sf

    def _object(self, object_name: str):
        return getattr(self._client(), object_name)

    @keyword
    def get_instance_url(self) -> str:
        self._client()
        return self._instance_url

    @keyword
    def get_org_info(self) -> dict:
        """Return Id, Name, OrganizationType and IsSandbox of the connected org."""
        rows = self.query_records("SELECT Id, Name, OrganizationType, IsSandbox FROM Organization")
        info = rows[0]
        logger.info(f"Org: {info['Name']} | type={info['OrganizationType']} | sandbox={info['IsSandbox']}")
        return info

    @keyword
    def assert_safe_org(self, allow_production=False) -> None:
        """Fail unless the org is a sandbox or Developer Edition (protects production)."""
        info = self.get_org_info()
        safe = info["IsSandbox"] or info["OrganizationType"] == "Developer Edition"
        if not safe and not truthy(allow_production):
            raise AssertionError(
                f"Refusing to run against '{info['OrganizationType']}' org '{info['Name']}'. "
                "Tests only run on sandboxes / Developer Edition unless ALLOW_PRODUCTION=True."
            )

    @keyword
    def get_daily_api_remaining(self) -> int:
        limits = self._client().limits()["DailyApiRequests"]
        logger.info(f"Daily API requests: {limits['Remaining']} remaining of {limits['Max']}")
        return int(limits["Remaining"])

    # ------------------------------------------------------------------ browser session
    @keyword
    def open_salesforce_in_browser(self, ui_library: str = "QWeb", browser: str = "chrome",
                                   headless=False, ret_url: str = "/lightning/page/home") -> None:
        """Open a browser already logged in to the org (no login page, no MFA prompt).

        Uses the API session with frontdoor.jsp. The URL holding the session id is
        handed to Selenium directly, so it is never written to the Robot log.
        Works with QWeb locally and with QForce (which includes QWeb) in Copado.
        """
        self._client()
        builtin = BuiltIn()
        builtin.import_library(ui_library)
        options = "--headless=new,--no-sandbox,--disable-dev-shm-usage" if truthy(headless) else None
        if options:
            builtin.run_keyword("OpenBrowser", "about:blank", browser, options)
        else:
            builtin.run_keyword("OpenBrowser", "about:blank", browser)
        driver = self._current_webdriver(ui_library)
        try:
            driver.set_window_size(1920, 1080)
        except Exception:  # some drivers/headless modes ignore this
            pass
        frontdoor = (f"{self._instance_url}/secur/frontdoor.jsp?sid={quote(self._token, safe='')}"
                     f"&retURL={quote(ret_url, safe='')}")
        driver.get(frontdoor)
        logger.info(f"Browser opened and logged in; navigated to {ret_url}")

    @staticmethod
    def _current_webdriver(ui_library: str):
        """Selenium WebDriver behind QWeb/QForce (used only to load the frontdoor URL)."""
        builtin = BuiltIn()
        lib = builtin.get_library_instance(ui_library)
        names = {n.replace(" ", "").replace("_", "").lower()
                 for n in getattr(lib, "get_keyword_names", lambda: [])()}
        if "returnbrowser" in names:
            return builtin.run_keyword("ReturnBrowser")
        from QWeb.internal import browser as qweb_browser  # fallback for QWeb versions without ReturnBrowser
        return qweb_browser.get_current_browser()

    # ------------------------------------------------------------------ CRUD
    @keyword
    def create_record(self, object_name: str, **fields) -> str:
        """Create a record and return its Id. Created records are tracked for cleanup."""
        result = self._object(object_name).create(fields)
        record_id = result["id"]
        self._created.append((object_name, record_id))
        logger.info(f"Created {object_name} {record_id}")
        return record_id

    @keyword
    def create_record_should_fail(self, object_name: str, expected_error: str, **fields) -> str:
        """Expect Salesforce to reject the record with ``expected_error`` (e.g. REQUIRED_FIELD_MISSING)."""
        try:
            result = self._object(object_name).create(fields)
        except SalesforceError as err:
            message = json.dumps(err.content) if not isinstance(err.content, str) else err.content
            if expected_error not in message:
                raise AssertionError(f"Expected error '{expected_error}' but got: {message}") from None
            logger.info(f"Rejected as expected: {message}")
            return message
        self._created.append((object_name, result["id"]))
        raise AssertionError(f"Expected {object_name} creation to fail with '{expected_error}', "
                             f"but record {result['id']} was created.")

    @keyword
    def update_record(self, object_name: str, record_id: str, **fields) -> None:
        self._object(object_name).update(record_id, fields)
        logger.info(f"Updated {object_name} {record_id}: {', '.join(fields)}")

    @keyword
    def delete_record(self, object_name: str, record_id: str) -> None:
        self._object(object_name).delete(record_id)
        self._created = [item for item in self._created if item[1] != record_id]
        logger.info(f"Deleted {object_name} {record_id}")

    @keyword
    def track_record_for_cleanup(self, object_name: str, record_id: str) -> None:
        """Register a record created some other way (e.g. through the UI) for cleanup."""
        self._created.append((object_name, record_id))

    @keyword
    def delete_tracked_records(self) -> int:
        """Delete every record created by this run, newest first. Returns how many were deleted."""
        deleted = 0
        for object_name, record_id in reversed(self._created):
            try:
                self._object(object_name).delete(record_id)
                deleted += 1
            except SalesforceResourceNotFound:
                pass  # already gone (deleted by the test or by cascade)
            except SalesforceError as err:
                logger.warn(f"Could not delete {object_name} {record_id}: {err}")
        self._created.clear()
        logger.info(f"Cleanup deleted {deleted} record(s)")
        return deleted

    # ------------------------------------------------------------------ queries
    @keyword
    def query_records(self, soql: str) -> list:
        """Run a SOQL query (all pages) and return a list of dictionaries."""
        result = self._client().query_all(soql)
        records = [clean_record(r) for r in result["records"]]
        logger.info(f"{len(records)} record(s): {soql}")
        return records

    @keyword
    def get_record_count(self, object_name: str, where: str | None = None) -> int:
        soql = f"SELECT COUNT() FROM {object_name}" + (f" WHERE {where}" if where else "")
        count = int(self._client().query(soql)["totalSize"])
        logger.info(f"{object_name} count = {count}" + (f" (where {where})" if where else ""))
        return count

    @keyword
    def get_field_value(self, object_name: str, record_id: str, field: str):
        rows = self.query_records(f"SELECT {field} FROM {object_name} WHERE Id = '{soql_quote(record_id)}'")
        if not rows:
            raise AssertionError(f"{object_name} {record_id} not found")
        return dig(rows[0], field)

    @keyword
    def verify_record_fields(self, object_name: str, record_id: str, **expected) -> None:
        """Query the record and compare each named field, reporting all mismatches at once."""
        if not expected:
            raise ValueError("Give at least one Field=value to verify.")
        fields = ", ".join(expected)
        rows = self.query_records(f"SELECT {fields} FROM {object_name} WHERE Id = '{soql_quote(record_id)}'")
        if not rows:
            raise AssertionError(f"{object_name} {record_id} not found")
        problems = [f"{name}: expected '{value}', got '{dig(rows[0], name)}'"
                    for name, value in expected.items() if not same_value(value, dig(rows[0], name))]
        if problems:
            raise AssertionError(f"{object_name} {record_id} mismatches:\n  " + "\n  ".join(problems))
        logger.info(f"{object_name} {record_id}: {len(expected)} field(s) match")

    @keyword
    def verify_record_field(self, object_name: str, record_id: str, field: str, expected) -> None:
        """Single-field check; supports relationship paths such as ``Account.Name``."""
        actual = self.get_field_value(object_name, record_id, field)
        if not same_value(expected, actual):
            raise AssertionError(f"{object_name}.{field}: expected '{expected}', got '{actual}'")

    @keyword
    def record_should_not_exist(self, object_name: str, record_id: str) -> None:
        count = self.get_record_count(object_name, f"Id = '{soql_quote(record_id)}'")
        if count:
            raise AssertionError(f"{object_name} {record_id} still exists")

    @keyword
    def describe_fields(self, object_name: str) -> list:
        """Return field metadata (name, createable, updateable, nillable, defaultedOnCreate, type)."""
        keys = ("name", "createable", "updateable", "nillable", "defaultedOnCreate", "type", "externalId")
        return [{k: f.get(k) for k in keys} for f in self._object(object_name).describe()["fields"]]

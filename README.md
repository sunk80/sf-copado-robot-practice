# Salesforce test automation with Robot Framework (Copado-aligned practice)

A practice framework that **loads data into Salesforce and validates it through the
API, SOQL and the Lightning UI**, with three kinds of runs:

| Suite | What it does | When it runs |
|---|---|---|
| **Smoke** | A few critical checks: org reachable, Account/Contact create → SOQL → UI | Every push to `main`, weekday mornings, on demand |
| **Regression** | Smoke + full CRUD, data-driven tests, negative tests, UI ↔ data sync | Nightly, on demand |
| **Adhoc** | One-time tasks: bulk load a CSV + reconcile + roll back, or clean up leftovers | On demand only |

It is built to move into **Copado Robotic Testing (CRT)** later with minimal changes:
UI steps use **QWords** (`ClickText`, `TypeText`, `VerifyText`) from the open-source
**QWeb** library, which Copado's **QForce** library includes. API, SOQL and Bulk logic is
plain Python, so it runs anywhere Robot Framework runs.

> Practice project for a free Salesforce **Developer Edition** org. Use synthetic data only.

---

## How it fits together

```
tests/                     test cases - business keywords only, no locators or API calls
  smoke/                   tag: smoke
  regression/              tag: regression
  adhoc/                   tag: adhoc (+ bulk | cleanup)
resources/
  common.resource          the ONLY place that knows how we connect + which UI library (QWeb/QForce)
  business/records.resource   Create Test Account, Create Test Contact ...
  business/ui.resource        Open Record Page, UI Field Should Show, Edit Field In UI ...
  variables/settings.resource defaults (org alias, headless, prefix, safety switches)
libraries/                 tool-agnostic Python
  SalesforceAPI.py         connect, CRUD, SOQL, field checks, cleanup, logged-in browser
  SalesforceBulk.py        Bulk API 2.0: pre-check, load, results, rollback
  Reconciliation.py        source CSV vs org comparison + CSV report
  TestData.py              unique names, synthetic CSVs, sampling
  sfutil.py                pure helpers (value comparison, CSV)
config/*.args              Robot options per suite
data/adhoc/                sample CSV for bulk practice
.github/                   GitHub Actions: smoke, regression, adhoc + shared setup action
tools/ci_summary.py        job summary in GitHub Actions
```

**Every test follows the same pattern:** create data through the API (fast and reliable) →
verify with SOQL → verify a sample in the Lightning UI → delete what it created.

**Safety built in**
- Tests refuse to run on a production org (only sandboxes / Developer Edition) unless `ALLOW_PRODUCTION=True`.
- Every record is named with the `RFPOC-` prefix and deleted at the end of each suite.
- The access token is never passed through Robot keywords, so it never appears in `log.html`.
- Bulk loads are pre-checked and capped (`MAX_ROWS=1000`) because a Developer Edition has only ~5 MB of storage.

---

## 1. One-time setup

**You need:** Python 3.10–3.12, Google Chrome, Node.js 18+ and Git.

1. **Get a free org:** sign up at <https://developer.salesforce.com/signup> and activate it from the email.
2. **Install the Salesforce CLI:** `npm install --global @salesforce/cli`
3. **Get the code and install dependencies**
   ```bash
   git clone https://github.com/<you>/sf-copado-robot-practice.git
   cd sf-copado-robot-practice
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Log in once** (opens a browser; handles MFA). No connected app is needed:
   ```bash
   sf org login web --alias devorg
   ```
   The framework reads the session from the CLI alias `devorg` (change with `-v SF_ORG_ALIAS:other`).
   Alternatively set `SF_ACCESS_TOKEN` and `SF_INSTANCE_URL` environment variables.

---

## 2. Run the suites

The test folder always goes **last** on the command line.

```bash
# Smoke (watch the browser)
robot --argumentfile config/smoke.args tests

# Regression, headless
robot --argumentfile config/regression.args --variable HEADLESS:True tests

# Only API tests, or only one object
robot --argumentfile config/regression.args --include apiANDaccount tests

# Adhoc bulk load: generate 300 synthetic Accounts, load, reconcile, UI spot check, roll back
robot --argumentfile config/adhoc.args --include bulk --variable ROWS:300 tests/adhoc

# Adhoc bulk load of your own file, kept in the org
robot --argumentfile config/adhoc.args --include bulk \
      --variable FILE:data/adhoc/sample_accounts.csv --variable KEEP:True tests/adhoc

# Pre-check a file without loading anything
robot --argumentfile config/adhoc.args --include bulk \
      --variable FILE:my_file.csv --variable DRY_RUN:True tests/adhoc

# Remove leftover RFPOC- test data (try DRY_RUN:True first)
robot --argumentfile config/adhoc.args --include cleanup tests/adhoc
```

Results go to `results/<suite>/` (`report.html`, `log.html`). Bulk result files are in
`results/bulk/` and reconciliation reports in `results/recon/`.

### Adhoc bulk load options

| Variable | Default | Meaning |
|---|---|---|
| `FILE` | *(empty)* | CSV to load. Empty = generate synthetic Accounts |
| `OBJECT` | `Account` | Target object |
| `OPERATION` | `insert` | `insert`, `update` (needs `Id` column) or `upsert` (needs `EXTERNAL_ID`) |
| `EXTERNAL_ID` | *(empty)* | External Id field for upsert |
| `ROWS` | `200` | Rows to generate when `FILE` is empty |
| `MAX_ROWS` | `1000` | Pre-check limit (protects small orgs) |
| `RECON_SAMPLE` | `0` | Rows to reconcile; `0` = all |
| `UI_SAMPLE` | `3` | Records to open in the UI; `0` = skip |
| `KEEP` | `False` | `False` = delete records the job created afterwards (inserts/upserts only; updates are never rolled back) |
| `DRY_RUN` | `False` | Pre-check only |

**What the adhoc load does:** pre-check (columns exist on the object, required fields present
and not blank, row limits) → Bulk API 2.0 job → download success/failed/unprocessed results →
reconcile every loaded row against the org with SOQL (`MATCH` / `MISMATCH` / `MISSING` /
`LOAD_FAILED` report) → open a few records in Lightning → roll back unless `KEEP=True`.

### Optional: add a custom validation rule (more realistic negative test)

In Setup → Object Manager → Account → Validation Rules → New:
- **Rule name:** `RFPOC_Insurance_Requires_Phone`
- **Formula:** `AND(ISPICKVAL(Industry, "Insurance"), ISBLANK(Phone))`
- **Error message:** `Insurance accounts need a phone number.`

Then run regression with `--variable CUSTOM_RULES:True`. The framework's own test data always
sets a Phone, so other tests keep passing.

---

## 3. Run in GitHub Actions

Workflows: **Smoke** (push to `main`, weekdays 11:17 UTC, manual), **Regression** (nightly
06:23 UTC, manual) and **Adhoc** (manual, with inputs for task, object, operation, file, rows,
keep, dry run). All share one concurrency group so two runs never hit the org at once.

**Add the org login as a secret:**
1. Locally: `sf org display --target-org devorg --verbose --json`
2. Copy the value of `sfdxAuthUrl` (starts with `force://`).
3. GitHub repo → Settings → Secrets and variables → Actions → New repository secret →
   name **`SFDX_AUTH_URL`**, paste the value.
4. Actions tab → Smoke → Run workflow.

> **Treat `SFDX_AUTH_URL` like a password.** It grants access to the org. Keep it only in
> GitHub Secrets, never in a file or commit. Use a practice org that holds no real data.
> Refresh tokens that are unused for 30 days expire; the nightly regression keeps it active.
> If the login step fails, log in again locally and update the secret.

Pull requests from forks are skipped because secrets are not available to them.
Run logs and artifacts of a public repo can be seen by others; they contain only the
synthetic `RFPOC-` test data and your org's URL, never the token.

---

## 4. Publish this project to GitHub (public)

```bash
cd sf-copado-robot-practice
git init -b main
git add .
git commit -m "Robot Framework Salesforce practice framework"

# With the GitHub CLI (gh auth login first):
gh repo create sf-copado-robot-practice --public --source . --push

# Or create an empty public repo on github.com, then:
git remote add origin https://github.com/<you>/sf-copado-robot-practice.git
git push -u origin main
```

Then add the `SFDX_AUTH_URL` secret (section 3).

---

## 5. Adding a test

1. Put it in `tests/smoke` or `tests/regression` and give it tags (`smoke`/`regression`, plus `api`/`ui` and the object).
2. Use business keywords from `resources/business/`. Add a new one there if needed.
3. UI steps use QWords only (`ClickText`, `TypeText`, `VerifyText`, `GoTo`, ...); no XPath.
4. Create data with `Create Test Account` / `Create Record` so it is cleaned up automatically.

```robotframework
Phone Change Is Shown In UI
    [Tags]    regression    account    ui
    ${id}=    Create Test Account    Industry=Banking
    Update Record    Account    ${id}    Phone=555-0123
    Open Record Page    Account    ${id}
    UI Field Should Show    Phone    555-0123
```

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `'sf org display' failed` | Run `sf org login web --alias devorg` again |
| UI test can't find text | Lightning layouts differ; check the screenshot in `log.html`, then adjust the label/text in `ui.resource` |
| Field shows a formatted value (e.g. phone) | `UI Field Should Show` matches visible text; use the value as displayed |
| `STORAGE_LIMIT_EXCEEDED` | Run the cleanup task; lower `ROWS` |
| Headless browser issues | Run without `HEADLESS:True` locally to watch it |
| QWeb install fails | Use Python 3.10–3.12 |

---

## 7. Moving to Copado Robotic Testing later

- In CRT, set the robot variable `UI_LIBRARY` to `QForce` (QForce includes all QWeb keywords).
- Replace the CLI login in `Connect To Salesforce` with your company's CRT login pattern.
- Map tags to CRT suites/robots: `smoke` → pipeline quality gate, `regression` → nightly schedule, `adhoc` → manual runs.
- The Python libraries and test cases stay as they are (confirm CRT allows custom Python libraries).

## License

MIT

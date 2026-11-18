# Mini Gauntlet

A small cloud-posture scanner. It reads a snapshot of AWS, Azure and Google Cloud
configuration (`data/inventory.json`), runs ten security checks over it, stores
the findings in SQLite and shows them in a React dashboard.

> **CI:** TODO: link the green GitHub Actions run for the final commit here.

## Quick start

```bash
docker compose up --build
```

- Dashboard: <http://localhost:3000>
- API: <http://localhost:8000> (for example `curl localhost:8000/api/health`)

Click **Run scan**. A full scan takes about 3 seconds. Scans are stored in the
`db-data` volume and survive restarts. `docker compose down -v` deletes them.

## Running without Docker

Backend (Python 3.12; 3.10+ works):

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

| Variable | Default | Meaning |
|---|---|---|
| `INVENTORY_PATH` | the repo's `data/inventory.json` | Snapshot to scan |
| `DB_PATH` | `mini_gauntlet.db` | SQLite file |
| `SCAN_WORKERS` | `4` | Accounts scanned at the same time |

Frontend (Node 22):

```bash
cd frontend
npm ci
npm run dev   # http://localhost:3000; /api is proxied to :8000
```

## Running the tests

```bash
# Backend: lint, format check, 163 tests (about 5 s)
cd backend
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest

# Frontend: lint, type-check, 15 tests
cd frontend
npx eslint . && npx tsc --noEmit && npx vitest run
```

What the tests cover:
- **Checks** (`tests/test_checks_*.py`): PASS, FAIL and CANNOT_SCAN for each of the ten checks, plus these edge cases:
  - port ranges
  - `::/0`
  - protocol `-1`, `*` and `all`
  - Deny rules and Outbound/EGRESS rules
  - disabled rules
  - a key exactly 90 days old vs. 91 days old
  - inactive keys
  - non-numeric ports
- **Engine** (`tests/test_engine.py`):
  - the acceptance numbers
  - a full scan with 4 workers in 2.9–4.5 s
  - the worker limit
  - collection errors and missing collections
  - a crashing check or a broken account doesn't stop the scan
  - the registry
- **Acceptance** (`tests/test_acceptance.py`): the exact expected status of all 49 findings.
- **API** (`tests/test_api.py`):
  - 202, 404 and 422 responses
  - every filter, case-insensitively
  - pagination and its limits
  - the exact sort order
  - FAILED scans
  - persistence across a restart
- **Dashboard** (Vitest + React Testing Library):
  - the `<img onerror>` description renders as plain text
  - error state when the API is down, empty state, `N/A` scores
  - Run scan, polling, filters

## Architecture

```
 browser ──► web (nginx :3000) ──/api──► api (FastAPI :8000) ──► SQLite (volume)
               static React app             │
                                            └─ background task ─► scanner engine
                                                                    ├─ registry: 10 checks
                                                                    ├─ ThreadPoolExecutor (SCAN_WORKERS)
                                                                    └─ reads inventory.json (read-only mount)
```

- **Scanner** (`backend/app/scanner/`):
  - Each check is one function with an `@check(...)` decorator that adds it to a registry. Every module in `checks/` is imported automatically, so a new check needs no other edits.
  - A check returns `None` (PASS) or a details string (FAIL), or raises `CannotScan`.
  - The engine handles everything shared by all checks: simulated latency, unreadable or missing collections, and turning crashes into CANNOT_SCAN with a warning log.
  - Accounts are scanned at the same time on a `ThreadPoolExecutor`.
- **API** (`backend/app/main.py`, `scans.py`, `db.py`):
  - `POST /api/scans` stores a RUNNING scan, returns 202 and runs the scan as a FastAPI background task.
  - When the scan ends, its findings and its COMPLETED (or FAILED) status are written in one transaction.
  - Scores and counts are computed with `GROUP BY` when read.
- **Dashboard** (`frontend/src/`):
  - Two pages behind a tiny hash router, with typed fetch helpers.
  - Polls every 1.5 s while a scan is RUNNING.
  - Every value is rendered as React text.
- **Docker:**
  - The API image is Python slim.
  - The dashboard uses a multi-stage build: Node builds it and unprivileged nginx serves it. nginx also proxies `/api`, so the browser never needs CORS.
  - Both images run as non-root users, have health checks and use base images pinned by tag and multi-arch digest.

## Assumptions

Decisions on points the brief leaves open:

1. **`public_access_block: null` is a FAIL**: no protection is configured. A flag missing from the block counts as off.
2. **Protocol `-1` (AWS), `*` (Azure) and `all` (GCP) mean every protocol and every port.** A GCP `allowed` entry with no `ports` also means every port.
3. **"Older than 90 days" means strictly greater.** A key exactly 90 days old PASSES. Age is `snapshot_taken_at - created_at` as a full timedelta, so 90 days and 1 second FAILS.
4. **Inactive access keys are ignored**, whatever their age.
5. **`allAuthenticatedUsers` counts as public**, because any Google account matches it.
6. **A non-numeric port (for example `"twenty-two"`) is CANNOT_SCAN**, and a warning is logged. Ports are validated even when the source is private: a malformed rule is reported, not guessed at.
7. **Disabled firewall rules, Deny rules and Outbound/EGRESS rules never FAIL.**
8. **Only TCP (or all-protocol) rules can expose SSH (22) or RDP (3389).** UDP and ICMP rules are ignored.
9. **"The internet" means `0.0.0.0/0` or `::/0`.** For Azure it also includes the source tags `*`, `Internet` and `Any`.
10. **A required true/false field that is missing or not a boolean is CANNOT_SCAN**, for example a missing `publicly_accessible`. The S3 rule in item 1 is the one exception.
11. **GCP firewall FAIL details include the rule's own `description`**, because it often says why the rule exists. It is untrusted text and is only ever shown as text.
12. **Filter values are not validated.** An unknown value such as `status=unknown` returns an empty page, not a 422.
13. **`account_ids` are de-duplicated.** If the snapshot can't be read when `POST /api/scans` runs, unknown IDs can't be detected, so the scan is accepted and ends FAILED with the reason.
14. **A scan still RUNNING when the API starts was cut off by a restart** and is marked FAILED.
15. **Account-level CANNOT_SCAN findings have no region and no resource ID.** In the findings order they sort before resource findings of the same check.
16. **Scores use Python's `round(x, 1)`.** No value in this snapshot lands on a .x5 tie.
17. **Acceptance numbers.** The first hand count of the snapshot gave 28 PASS / 17 FAIL. A recount, and the scanner, give **27 PASS / 18 FAIL / 4 CANNOT_SCAN**: overall **60.0**, prod **58.3**, dev 66.7, azure 57.1, gcp 63.6, FAIL by severity **CRITICAL 7**, HIGH 8, MEDIUM 2, LOW 1. The difference is one CRITICAL in prod: all four security groups `bastion` (22 from 0.0.0.0/0), `legacy-admin` (3000–3500 includes 3389), `ipv6-ssh` (22 from ::/0) and `debug-all-traffic` (protocol -1) expose SSH or RDP. No check was changed to make the numbers match; the tests use the recounted values.

## Decisions and trade-offs

- **SQLite with the standard `sqlite3` module, no ORM.** Every query is visible and easy to explain. Each call opens its own short connection, and WAL mode lets reads continue during a write. Trade-off: one writer, one host. DEPLOY.md moves to PostgreSQL.
- **FastAPI `BackgroundTasks` rather than a job queue.** Simple and enough for one process. A scan cut off by a restart is marked FAILED, not lost silently. A queue and a worker are the next step.
- **Threads for concurrency.** The work waits on I/O (here, a sleep), so the GIL doesn't matter. `max_workers` gives the limit for free.
- **Scores are computed when read, not stored.** They can never disagree with the findings.
- **No React Router.** react-router-dom 6 had open advisories (fixed only in v7) and two pages don't need it. A 15-line hash router works behind any static server.
- **nginx proxies `/api`.** One origin means no CORS, and a strict CSP header guards against script injection as a second layer.
- **The snapshot is bind-mounted read-only** rather than copied into the image. There is one copy of the data, and the image matches how a live scanner would get its input from outside.
- **Polling rather than WebSockets or SSE.** The brief allows it. It stops as soon as nothing is RUNNING.
- **Dependencies are pinned to exact versions** (Python and npm) and base images by digest, for repeatable builds.

## What's unfinished and what I'd do next

- No authentication on the API or dashboard. DEPLOY.md puts an OIDC login in front.
- Move scans to a queue and worker, and storage to PostgreSQL with migrations (Alembic).
- Live collectors (boto3 and the Azure and GCP SDKs) behind the same check interface.
- An end-to-end browser test (Playwright) in CI against `docker compose up`.
- Structured JSON logs and a request ID.
- `npm audit` reports one moderate, dev-only advisory (minimatch ReDoS inside `typescript-eslint` ≤ 8.72.2). It affects lint time only, not the shipped bundle. Upgrade once 8.73+ has been out a little longer.
- None of the stretch goals were attempted.

## Time spent

> TODO: fill in by hand.

| Part | Time |
|---|---|
| 1. Scanner engine | TODO |
| 2. REST API | TODO |
| 3. Dashboard | TODO |
| 4. Tests | TODO |
| 5. Docker | TODO |
| 6. CI | TODO |
| 7. DEPLOY.md | TODO |

## Use of AI assistants

> TODO: describe where and how AI assistants were used (see NOTES.md).

## Repository layout

```
backend/
  app/
    main.py          FastAPI routes
    scans.py         runs a scan in the background; builds summaries
    db.py            SQLite schema and queries
    schemas.py       Pydantic request/response models
    config.py        environment variables
    scanner/
      engine.py      runs checks over accounts concurrently
      registry.py    @check decorator and CHECKS list
      models.py      Finding, Status, Severity, CannotScan
      checks/        aws.py, azure.py, gcp.py, common.py (helpers)
  tests/             pytest
frontend/
  src/               React app, Vitest tests next to the code
  nginx.conf         static files + /api proxy + CSP
data/inventory.json  the snapshot (never edited)
docker-compose.yml   api + web + db-data volume
.github/workflows/   CI
DEPLOY.md            AWS production design
```

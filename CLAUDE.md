# Mini Gauntlet: project rules

Conventions for anyone working in this repo, human or AI agent. Favour plain, readable
code that a new teammate can follow and change without a tour: standard library first,
no clever abstractions, and short comments only where the logic is not obvious.

## Stack
- Backend: Python 3.12, FastAPI, SQLite (path from env DB_PATH), pytest, Ruff
- Scanner: check registry via decorator, ThreadPoolExecutor (SCAN_WORKERS, default 4),
  snapshot path from env INVENTORY_PATH
- Frontend: React 18, TypeScript, Vite, Vitest, React Testing Library, ESLint
- Docker: pinned base images, non-root user, .dockerignore, healthchecks, compose with a volume
- CI: GitHub Actions (ruff, eslint, tsc --noEmit, pytest, vitest, build both images)

## Hard rules
- Never edit data/inventory.json. Never commit secrets, .env files, node_modules,
  build output or the .db file.
- Treat every string from the inventory as untrusted. Never use dangerouslySetInnerHTML.
- Age rules use snapshot_taken_at, never the current clock.
- One bad record or one crashing check must never stop a scan: log a warning, emit CANNOT_SCAN.
- No stretch goals until the core works end to end.

## Decisions (document these in README under "Assumptions")
- public_access_block null => FAIL (no protection configured)
- protocol "-1" (AWS), "*" (Azure), "all" (GCP) mean all ports
- "older than 90 days" is strictly greater: a key exactly 90 days old PASSES
- Inactive access keys are ignored
- allAuthenticatedUsers counts as public
- A non-numeric port => CANNOT_SCAN, with a warning log
- Disabled firewall rules, Deny rules and Outbound/EGRESS rules never FAIL

## Acceptance numbers for data/inventory.json (must be automated tests)
- 49 findings: 27 PASS, 18 FAIL, 4 CANNOT_SCAN
- Overall score 60.0; per account: prod 58.3, dev 66.7, azure 57.1, gcp 63.6
- FAIL by severity: CRITICAL 7, HIGH 8, MEDIUM 2, LOW 1
- If the scanner disagrees with these numbers, never change a check to match:
  recount by hand, then fix whichever side is wrong
- Full scan with 4 workers: about 3 seconds

## How to work
- Commit after each part with a clear message.
- Run tests, lint and type-check before saying a part is done.
- Keep NOTES.md updated: assumptions, rough time per part, where AI was used.
- Summarise the design of each part in the PR or commit message.
# NOTES

Engineering notes for Mini Gauntlet: assumptions, time per part, AI usage.

## Assumptions
- `public_access_block: null` => FAIL (no protection configured).
- Protocol `-1` (AWS), `*` (Azure), `all` (GCP) mean all protocols and all ports.
- "Older than 90 days" is strictly greater: a key exactly 90 days old PASSES.
- Inactive access keys are ignored.
- `allAuthenticatedUsers` counts as public.
- A non-numeric port => CANNOT_SCAN, with a warning log.
- Disabled firewall rules, Deny rules and Outbound/EGRESS rules never FAIL.
- Acceptance numbers: the first hand count had 28 PASS / 17 FAIL. A recount found 4 CRITICAL
  AWS-EC2-01 failures in prod (bastion, legacy-admin 3000-3500 covers 3389, ipv6-ssh ::/0,
  debug-all-traffic protocol -1), so the tests use 27 PASS / 18 FAIL / 4 CANNOT_SCAN,
  overall 60.0, prod 58.3, CRITICAL 7.

## Time per part
The whole core, including local verification with Docker, was built in one AI-assisted session:
about 40 minutes of wall-clock time (2026-11-18, 19:28-20:05 UTC, from the session log).
Publishing to GitHub and CI followed on 2026-11-19. Time per part was not tracked separately.

## Where AI was used
Claude Code (an AI coding agent) wrote every part and the docs, and ran the tests, linters,
Docker and CI. I set the rules in CLAUDE.md, approved the corrected acceptance numbers (the AI
stopped and asked instead of changing a check) and chose the read-only snapshot mount.
I reviewed every file and design decision.

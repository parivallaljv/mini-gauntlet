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
TODO (fill in by hand)

| Part | Time |
|---|---|
| Step 0 setup | TODO |
| 1 Scanner engine | TODO |
| 2 REST API | TODO |
| 3 Dashboard | TODO |
| 4 Tests | TODO |
| 5 Docker | TODO |
| 6 CI | TODO |
| 7 DEPLOY.md | TODO |

## Where AI was used
TODO (fill in by hand)

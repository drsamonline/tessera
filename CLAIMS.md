# Claim register

Every public claim this project makes, and the command that checks it. A claim without a check is a slogan, and this
file exists so that adding one costs something.

Run all the checks: `python3 scripts/check_claims.py`.

| # | Claim | Check | Status |
|---|---|---|---|
| 1 | 748 tests pass | `python3 -m unittest discover -s tests -t .` | verified |
| 2 | Four connectors pass a 16-check conformance suite | `python3 scripts/conformance_report.py` | verified against recorded transports |
| 3 | The Postgres DDL is valid Postgres syntax | `python3 scripts/validate_ddl.py` (libpg_query) | verified |
| 4 | The Postgres DDL runs against a server | — | **not verified. Never executed.** |
| 5 | A connector works against a live tenant | — | **not verified. Never attempted.** |
| 6 | The API serves HTTP and answers a request | `python3 scripts/smoke.py`; `tests/test_server.py` | verified |
| 7 | The demo starts both halves and prints a working link | `python3 -m tessera.demo` | verified by hand, 15 Nov 2026 |
| 8 | Two tenants are isolated in one process | `tests/test_tenants.py` | verified |
| 9 | A deletion is a tombstone, not a destruction | `tests/test_standalone.py::TestTombstone` | verified |
| 10 | 43 specification defects found, all closed | `docs/audit/defect-register.md` | verified by reading the register |
| 11 | 13 review findings; 11 fixed, 2 open by design | `docs/31-code-review.md` | verified |
| 12 | 47 documents | `python3 scripts/check_docs.py` | verified |
| 13 | The DDL has RLS with `FORCE` and `WITH CHECK` | `tessera.store.validate()` | verified structurally, not by execution |
| 14 | The console reads from a running engine | `assets/shot-engine.png`; `tests/a11y-harness.html` | verified by hand |
| 15 | The console passes 64/64 accessible-name checks | `tests/a11y-harness.html` | verified in Chromium |
| 16 | The console's static gates pass | `scripts/check_app.py` | verified |
| 17 | The APK installs and runs | — | **not verified. Never run on a device.** |
| 18 | No customer has used this | — | true by definition, and the point |

## The four that are not verified

They are the four that matter most to a buyer, and no amount of documentation closes them:

1. **Row 4** — the DDL has never run. A server would settle it in ten minutes.
2. **Row 5** — no connector has touched a live tenant. A sandbox token would settle it in an hour.
3. **Row 17** — the APK has never launched on Android. A phone would settle it in a minute.
4. **Row 13** — RLS is verified by reading the SQL, not by attempting a cross-tenant read against a live database.

## The rule

A new public claim enters this table before it enters a README, a landing page or a release note. If the check column
says "—", the claim says so in the sentence where it appears.

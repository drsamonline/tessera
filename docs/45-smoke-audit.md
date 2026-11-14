# 45 - Smoke audit

**Status: Draft**

"Check every function if it works" is not a thing a script can do for a codebase with 709 tests. This is the thing it
can do: import every module, call something real in it, and fail loudly if a module does not import or does not
answer.

```
python3 scripts/smoke.py
42 ok, 0 failed, 42 modules
```

## What it covers

One real call per module, chosen to be the thing that breaks if the module breaks:

| Module | The call |
|---|---|
| `canonical` | Validate a Contact and get an empty problem list |
| `ledger` | Append one event, verify the chain |
| `conflict` | Resolve a single-source field and get its rule back |
| `conformance` | Run the full 16-check suite against the native connector |
| `store` | Generate the Postgres DDL and assert the four properties |
| `learning` | Assert the structural claims hold |
| `mobile` | Derive a key from a passphrase |
| `openapi` | Build the document and assert it validates |

## What it found

Five failures on the first run, and all five were the script's fault, not the code's:

| Reported | Actual |
|---|---|
| `compliance has no attribute DsrRequest` | The class is `DsarRequest` |
| `conformance has no attribute run_conformance` | It does; the call was shadowed by a bad lambda |
| `Histogram.__init__() missing 1 argument` | It takes a name |
| `openapi has no attribute build_document` | It does |
| `Seat.__init__() missing 2 arguments` | It takes `version` and `capability_manifest` |

That is the useful result: the audit found no defects, and it found five places where a caller would have guessed
wrong. The signatures are the interface, and a smoke test is the cheapest way to find out that an interface is not
the one you remember.

## What it does not do

- **It does not replace the suite.** One call per module says the module imports and answers; the 709 tests say the
  answers are right.
- **It does not cover every function.** `scripts/smoke.py` is a smoke test, not a coverage report.
- **It is not in CI.** It should be; it takes four seconds.

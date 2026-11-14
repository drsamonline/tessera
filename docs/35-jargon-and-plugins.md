# 35 - Jargon lint and plugin hardening

**Status: Draft**

Deliverables 12 and 16. Two small modules, both of which exist because a rule in the specification was otherwise
unenforceable.

## The jargon lint

Constraint 17 in [17-constraints.md](17-constraints.md): *"Do not leak internal terms into the interface. Lint
blocks release."*

Thirteen terms, thirteen replacements, taken verbatim from the map in [07-experience.md](07-experience.md#jargon-map).
`test_the_map_matches_the_document` parses the markdown and compares it to the dictionary, so the linter and the
document cannot drift apart without a test failing.

```
python3 -m tessera.jargon
JARGON OK - 13 terms, no leaks in the shipped catalogue
```

It runs as a CI step that fails the build, which is what "lint blocks release" has to mean if it means anything.

### The linter is deliberately coarse

- It matches the term and allows the case where the match sits inside its own approved replacement, so
  "Workflow chain" does not trip on "Chain".
- `Chain`, `Seat` and `Occupant` are also ordinary English words, so they match on a word boundary and
  case-insensitively; the rest match as written.
- Everything else is reported for a human.

A cleverer linter would grow a suppression mechanism, and a suppression mechanism is how a lint rule becomes a
formality. This one has none, on purpose.

`test_every_term_is_caught_in_a_fixture` builds a string per term and asserts each is caught. `test_the_shipped_catalogue_has_no_leaks`
runs it against all 28 keys in all five locales.

## Plugin hardening

Four gates, in order:

| Gate | What it stops |
|---|---|
| Allowlist | A plugin name the deployment did not choose |
| Pinned hash | Any byte changed after signing |
| Signature | A manifest signed with another key, or not signed at all |
| Static scan | A denied import or call in the source |
| Permission grant | A capability the deployment did not grant |

A denied import list (`os`, `subprocess`, `socket`, `ctypes`, `pickle`, `importlib`, …) and a denied call list
(`eval`, `exec`, `compile`, `__import__`, `open`, …) are scanned with `ast`, not with a regex over the text. A
regex over source is how `ev\u0061l` gets through.

### Nothing here executes a plugin

`validate()` parses and inspects. It does not import, and `test_the_loader_never_executes_the_plugin` writes a
plugin whose only statement would create a file, runs validation, and asserts the file does not exist.

A loader that runs untrusted code to find out whether it is safe to run has already answered the question wrongly.
Execution belongs in a separate process with the same gates in front of it.

### A refused permission is logged

`plugin.refused` is a ledger event with the plugin name, version and the reason. A permission system whose refusals
leave no trace is a permission system nobody can audit.

## Deliverables, updated

| Criterion | State |
|---|---|
| 12: rule runs in CI | Met - a failing CI step |
| 12: a fixture per jargon term fails the build | Met - 13 fixtures, each asserted |
| 12: zero leaks in the shipped catalogue | Met - 28 keys, 5 locales |
| 16: unsigned plugin rejected | Met |
| 16: modified hash rejected | Met |
| 16: out-of-allowlist network call blocked and logged | Met - blocked at the permission gate, logged as `plugin.refused` |

## What is not here

- **No plugin execution, at all.** The gates validate; nothing runs a plugin.
- **No sandbox process.** The separate process with the same gates in front is described and not built.
- **No third-party signature chain.** One deployment key, not a web of trust.
- **No version pinning per plugin.** The hash pins the content; the version string is informational.
- **No dynamic analysis.** Static scanning sees what the source says, not what it does at runtime.

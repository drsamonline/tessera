# 42 - Property tests

**Status: Draft**

Reference: the review in [31-code-review.md](31-code-review.md), and its blind spot. The suite tests the cases
somebody thought of. `tessera/fuzz.py` tests the ones nobody did, and prints the seed when it finds one so the
failure is reproducible.

No dependency: `random.Random(seed)` is the whole point. A fuzzer you cannot replay is a rumour.

## Four invariants

| Suite | Invariant |
|---|---|
| `ledger` | The chain verifies after any sequence of appends, sequences are contiguous, every payload hash recomputes, and tampering is **always** caught |
| `sync` | Any interleaving converges to one fingerprint, the server accepts no more operations than were made, and replaying the log changes nothing |
| `conflict` | Resolution is total, deterministic, and the winner is one of the candidates |
| `routing` | The score stays in its declared range and moves the right way when a term improves or the penalty drops |

```
python3 -m tessera.fuzz
  ledger     ok
  sync       ok
  conflict   ok
  routing    ok
FUZZ CLEAN
```

## The fuzzer has teeth

`TestTheFuzzerHasTeeth` swaps in a ledger whose `verify()` always returns `True` and a conflict resolver that
alternates its answer, and asserts both are caught. A fuzzer that only ever passes is a fuzzer nobody has tested -
the same argument as the deliberately broken connector in [21-connectors-and-mesh.md](21-connectors-and-mesh.md).

## R-17: the range claim was mine, not the code's

The fuzzer found `score -0.0113 is outside [0, 1]` on seed 2.

Every **term** is normalised to `[0,1]`. The **total** is not: the cross-boundary penalty is subtracted with a
weight of 0.2, so the routing score lies in `[-0.20, 1.00]`. `docs/10-metrics.md` claimed `[0,1]`, and the code
never did.

The tempting fix is to clamp. That is the wrong one: clamping collapses every heavily-penalised candidate to a tie
at zero, which is precisely the situation where the ordering matters. `test_ordering_survives_below_zero` asserts
that a candidate at −0.20 and one at −0.12 stay ordered.

So the **invariant and the document** changed, not the arithmetic. That is the difference between a property test
finding a bug and a property test finding a wrong assumption, and this one was the second.

## What is covered, and what a seed cannot reach

- **Interleavings**: random sync points between random writers, which is where the sync bugs live.
- **Tampering**: one random line rewritten per ledger run, which is the only way the verification path is exercised.
- **Boundaries**: the routing suite raises a term by 0.1 and asserts the score never falls.

Not reachable with a seed: a real network, a real clock, concurrent processes, and a million events. The fuzzer
runs in seconds because it has to run on every push; the load model is a separate question and
[23-stage-one.md](23-stage-one.md) says which of them the benchmark answers.

## What is not here

- **No shrinking.** A failing seed is reproducible but not minimised; you replay the whole sequence.
- **No hypothesis.** A hand-written generator, so it explores what its author thought to randomise.
- **No concurrency.** One process, one thread.
- **Not in CI as a gate.** `python3 -m tessera.fuzz` runs 20 seeds by hand; the suite runs 10 per suite. Adding the
  longer run to CI is a minute of wall clock and would catch more.

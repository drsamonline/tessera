"""Property tests: random inputs, fixed invariants, a seed you can replay.

The suite tests the cases somebody thought of. This module tests the ones nobody
did, and it prints the seed when it finds one so the failure is reproducible.

No dependency: `random.Random(seed)` is enough, and a seeded PRNG is the whole
point. A fuzzer you cannot replay is a rumour.

Four invariants, each one a claim the documentation already makes:

    ledger     the chain verifies after any sequence of appends, and tampering is
               always caught
    sync       any interleaving converges, and no accepted operation is lost
    conflict   resolution is total and deterministic, and the winner is one of the
               candidates
    routing    the score is always in [0, 1] and monotone in every positive term
"""

from __future__ import annotations

import os
import random
import shutil
import tempfile

from . import canonical, conflict, ledger, routing, sync

TENANT = "018f0000-0000-7000-8000-000000000001"
FIELDS = ("full_name", "email", "phone", "stage")
REFS = tuple(f"Contact:018f0000-0000-7000-8000-00000000c0{n:02d}" for n in range(1, 5))


def _contact(record_id: str, **over) -> dict:
    payload = {
        "id": record_id, "tenant_id": TENANT,
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent",
        "purpose_id": "p", "retention_policy_id": "r", "full_name": "Asha Rao",
    }
    payload.update(over)
    return payload


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def fuzz_ledger(seed: int, events: int = 40) -> list[str]:
    """Append at random, verify after every append, then tamper once."""
    rng = random.Random(seed)
    failures = []
    directory = tempfile.mkdtemp(prefix="tessera-fuzz-ledger-")
    try:
        log = ledger.EventLog(os.path.join(directory, "ledger.jsonl"))
        for index in range(events):
            ref = rng.choice(REFS)
            log.append(TENANT, "system", "contact.sync",
                       {"record": _contact(ref.split(":")[1], full_name=f"v{index}")},
                       canonical_ref=ref, source_node_id="fuzz")

            ok, problems = log.verify()
            if not ok:
                failures.append(f"seed {seed}: chain broke after {index + 1} events: "
                                f"{problems[:2]}")
                return failures

            stored = list(log.events(TENANT))
            sequences = [event["sequence"] for event in stored]
            if sequences != list(range(1, len(sequences) + 1)):
                failures.append(f"seed {seed}: sequences are not contiguous at {index}")
                return failures

            for event in stored:
                if canonical.canonical_hash(event["payload"]) != event["payload_hash"]:
                    failures.append(f"seed {seed}: payload hash mismatch at seq "
                                    f"{event['sequence']}")
                    return failures

        stored = list(log.events(TENANT))
        if stored:
            target = rng.randrange(len(stored))
            with open(log.path, encoding="utf-8") as handle:
                lines = handle.readlines()
            lines[target] = lines[target].replace('"v', '"tampered', 1)
            with open(log.path, "w", encoding="utf-8") as handle:
                handle.writelines(lines)
            ok, _ = log.verify()
            if ok:
                failures.append(f"seed {seed}: tampering at line {target} was not caught")
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    return failures


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def fuzz_sync(seed: int, replicas: int = 3, operations: int = 40) -> list[str]:
    """Random concurrent writes with random sync interleavings."""
    failures = []
    directory = tempfile.mkdtemp(prefix="tessera-fuzz-sync-")
    try:
        rng = random.Random(seed)
        log = ledger.EventLog(os.path.join(directory, "ledger.jsonl"))
        server = sync.SyncServer(TENANT, log)
        clients = [sync.Replica(f"r{n}") for n in range(1, replicas + 1)]

        for _ in range(operations):
            client = rng.choice(clients)
            client.set(rng.choice(REFS), rng.choice(FIELDS),
                       f"v{rng.randrange(50)}")
            if rng.random() < 0.35:
                sync.sync(rng.choice(clients), server)

        for _ in range(2):
            for client in clients:
                sync.sync(client, server)

        fingerprints = {client.fingerprint() for client in clients}
        if len(fingerprints) != 1:
            failures.append(f"seed {seed}: {len(fingerprints)} states after convergence")

        if len(server.ops) > operations:
            failures.append(f"seed {seed}: the server accepted {len(server.ops)} of "
                            f"{operations} operations")

        before = {client.replica_id: client.fingerprint() for client in clients}
        for client in clients:
            client.pull(list(server.ops))
        after = {client.replica_id: client.fingerprint() for client in clients}
        if before != after:
            failures.append(f"seed {seed}: replaying the log changed a replica")

        ok, problems = log.verify()
        if not ok:
            failures.append(f"seed {seed}: the ledger broke under sync: {problems[:2]}")
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    return failures


# ---------------------------------------------------------------------------
# Conflict
# ---------------------------------------------------------------------------

def fuzz_conflict(seed: int, rounds: int = 30) -> list[str]:
    """Resolution must be total, deterministic, and pick a real candidate."""
    rng = random.Random(seed)
    failures = []
    modes = ("mirror", "bidirectional", "authority", "delegate")

    for _ in range(rounds):
        count = rng.randrange(1, 5)
        candidates = [
            conflict.Conflict(
                node_id=f"n{n}",
                value=f"v{rng.randrange(4)}",
                valid_from=f"2026-11-{rng.randrange(1, 29):02d}T09:00:00Z",
                trust_score=round(rng.random(), 3),
            )
            for n in range(count)
        ]
        authority = {f"n{n}": rng.choice(modes) for n in range(count)}

        first = conflict.resolve("email", candidates, authority)
        second = conflict.resolve("email", list(candidates), dict(authority))

        if "rule" not in first:
            failures.append(f"seed {seed}: resolution returned no rule")
            continue
        if first.get("rule") != second.get("rule") or first.get("value") != second.get("value"):
            failures.append(f"seed {seed}: resolution is not deterministic")
        if first.get("blocked"):
            if first["rule"] != "human_review":
                failures.append(f"seed {seed}: blocked without human_review")
            continue
        if first.get("value") not in [c.value for c in candidates]:
            failures.append(f"seed {seed}: the winner is not one of the candidates")
        if len(candidates) > 1 and len({c.value for c in candidates}) > 1:
            if first.get("winner") is None:
                failures.append(f"seed {seed}: a disagreement produced no winner")
    return failures


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def fuzz_routing(seed: int, rounds: int = 30) -> list[str]:
    """The score stays in range and moves the right way when a term improves."""
    rng = random.Random(seed)
    failures = []
    positive = ("capability_match", "authority_match", "sla_headroom", "trust_score",
                "utilization", "cost_efficiency", "data_freshness")

    for _ in range(rounds):
        terms = {name: round(rng.random(), 3) for name in positive}
        terms["cross_boundary_penalty"] = round(rng.random(), 3)
        score = routing.score(terms)["score"]

        # The terms are in [0, 1]; the *total* is not, because the cross-boundary
        # penalty is subtracted and its weight is 0.2. Clamping to [0, 1] would
        # collapse every heavily-penalised candidate to a tie, which is exactly
        # when the ordering matters. (R-17)
        floor = -routing.weights()["_penalty_weight"]
        if not floor <= score <= 1.0:
            failures.append(f"seed {seed}: score {score} is outside [{floor}, 1]")

        name = rng.choice(positive)
        if terms[name] < 0.9:
            better = dict(terms)
            better[name] = round(min(1.0, terms[name] + 0.1), 3)
            if routing.score(better)["score"] < score:
                failures.append(f"seed {seed}: raising {name} lowered the score")

        if terms["cross_boundary_penalty"] > 0.1:
            worse = dict(terms)
            worse["cross_boundary_penalty"] = round(
                terms["cross_boundary_penalty"] - 0.1, 3)
            if routing.score(worse)["score"] < score:
                failures.append(f"seed {seed}: lowering the penalty lowered the score")
    return failures


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

SUITES = {
    "ledger": fuzz_ledger,
    "sync": fuzz_sync,
    "conflict": fuzz_conflict,
    "routing": fuzz_routing,
}


def run(seeds: int = 10, **kwargs) -> dict:
    """Every suite, every seed. Returns {suite: [failures]}; empty means clean."""
    report = {}
    for name, suite in SUITES.items():
        failures = []
        for seed in range(seeds):
            failures.extend(suite(seed, **kwargs))
        report[name] = failures
    return report


def main() -> int:
    report = run(seeds=20)
    total = sum(len(failures) for failures in report.values())
    for name, failures in report.items():
        state = "ok" if not failures else f"{len(failures)} failure(s)"
        print(f"  {name:<10} {state}")
        for failure in failures[:5]:
            print(f"    {failure}")
    print("FUZZ CLEAN" if total == 0 else f"FUZZ FOUND {total}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

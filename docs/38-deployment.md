# 38 - Deployment, and the rule that keeps this readable

**Status: Draft**

Two things that belong together: what it takes to run the reference core, and the
rule that every push updates this documentation and the landing page in the same
commit.

## The docs rule, enforced

> **Every major push updates `docs/`, `docs/index.md` and `docs/index.html` in the
> same commit.**

A rule that lives in a habit is a rule that survives until somebody is in a hurry,
so it lives in `scripts/check_docs.py` and CI runs it. It checks five things:

| Check | Catches |
|---|---|
| The test count in README matches the tests that exist | A count that drifted three commits ago |
| The test count on the landing page matches, in all three places it appears | A page that advertises yesterday's suite |
| Every numbered document is linked from `docs/index.md` | A document nobody can find |
| Every document `docs/index.md` links exists | A link to a document that was renamed |
| `VERSION` matches the newest `CHANGELOG` heading | A version that was never bumped |
| The document count in the landing page heading matches the documents that exist | A page that says "thirty-eight" with thirty-nine in the tree |

It found two stale things the moment it was written: `VERSION` said `1.1.0` while
the changelog was at `1.20.0`, and the landing page's document count had been
wrong since the previous push. Both are the exact class of drift the rule exists
to prevent, and neither was visible by reading.

## Running it

```
docker compose up --build
curl -s http://127.0.0.1:8080/health
```

```
{"status": "ok", "tenant": "018f0000-0000-7000-8000-000000000001", "auth_required": true}
```

No database, no queue, no object store: the reference core is a Python process and
a JSONL file, so the image is a base interpreter and the source.

## What the artefacts are, and what they are not

| Artefact | What it does | What it is not |
|---|---|---|
| `Dockerfile` | `python:3.12-slim`, non-root uid 10001, a healthcheck that makes a real request | A production image; there is no TLS, no proxy, no log shipping |
| `docker-compose.yml` | One service, read-only root, `cap_drop: ALL`, `no-new-privileges` | The four deployment profiles in [13-deployment.md](13-deployment.md) |
| `deploy/k8s.yaml` | Namespace, ConfigMap, Secret, Deployment, Service | A Helm chart, an operator, or anything with a rolling update story |

The manifests are hardened in the ways that are cheap and checked: non-root,
read-only root filesystem, all capabilities dropped, no privilege escalation,
resource limits, and readiness and liveness probes on the same real route. The
test asserts each of those, because a security context that is not asserted is a
security context somebody deletes.

**The image carries no token.** `TESSERA_TOKEN` comes from the environment, and
the Kubernetes Secret ships a `replace-me` placeholder that says so out loud
rather than a default that works.

## The entry point, and why `serve` was refactored

`python3 -m tessera.api` builds a demo workspace and serves it. The handler used
to be constructed inside `serve()`, which made the server testable only by
starting its own process; `handler_for(api)` returns the class, so the suite binds
a real server to port 0 and makes real HTTP requests. A server that is only
testable through its own process is a server nobody tests.

Seven tests now run against a live socket: health without a token, 401 without
one, 401 with a wrong one, the object list, the unified view, a 404, and the
handler being reusable.

## Deliverable 1, updated

| Criterion | State |
|---|---|
| Compose reaches a healthy state for all P0 services | **Unverified** - the compose file is validated, nothing here can run Docker |
| Manifests apply to a cluster with all pods ready | **Unverified** - the manifests are validated and hardened, nothing here has a cluster |
| No P0 service references S3, Neo4j, NATS or an AI container | Met - P0 is one process and a file |

Two of three criteria are unverified rather than met. Saying otherwise would be
the same overclaiming this repository spends its time catching.

## What is not here

- **No CI job that builds the image.** The Dockerfile is checked structurally.
- **No published image.** Nothing is pushed to a registry.
- **No TLS, no proxy, no auth provider.** The API speaks plain HTTP with a bearer
  token from an environment variable.
- **No persistence across a restart.** The demo ledger is in `/tmp`.

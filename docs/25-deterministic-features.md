# 25 - Deterministic features

**Status: Frozen**

These are never labelled AI, and they survive every AI switch being off. This is the register the AI contract
points at when it says the product is feature-complete without a model.

The right-hand column is the honest one: what exists in the reference core today, and what is still a
requirement.

| Feature | Mechanism | Specification | In the reference core |
|---|---|---|---|
| Relationship velocity score | Graph math over frequency, latency asymmetry, meeting density, centrality and decay | [10-metrics.md](10-metrics.md#relationship-velocity-score) | Implemented twice, agreeing to six decimals. The graph itself is not built |
| Forecast provenance | Every forecast number expands to its evidence tree | [10-metrics.md](10-metrics.md#forecast) | Weighted pipeline with overrides reported separately. The evidence tree is not built |
| Record history | Ledger checkpoints, diff and revert | [11-history-authority.md](11-history-authority.md) | Implemented |
| Branch what-if pipelines | A branch of the read model, no production mutation | [14-invention-register.md](14-invention-register.md) | Not built |
| Markdown mirror | Async projection, lag exposed as a metric | [24-history-projections.md](24-history-projections.md) | Implemented, local directory only |
| Review queue | Generic proposed-change surface with diffs | [12-ai-contract.md](12-ai-contract.md) | Not built |
| Bi-temporal records | Projection over the ledger | [24-history-projections.md](24-history-projections.md) | Implemented, both views |
| Identity spine and federated graph | UUIDv7, merge and split, per-cell provenance | [03-mesh.md](03-mesh.md) | Identity and provenance implemented; the graph is not |
| Local-first real-time | One sync protocol online and offline | [04-core.md](04-core.md) | Not built |
| Conversation to record | ICS, email headers, call metadata | [03-mesh.md](03-mesh.md) | Not built |
| Portable record contracts | Schema, export and a signed attestation | [14-invention-register.md](14-invention-register.md) | Schema and export path exist; the attestation does not |
| Edge sync with server-offloaded validation | SQLCipher, local validation, delta sync | [04-core.md](04-core.md) | Canonical validation exists; the client does not |

## Why this register matters

The AI contract says the product must be feature-complete with every model switched off. That is easy to claim
and easy to erode: the first feature that quietly depends on an embedding breaks it, and nobody notices until a
customer turns AI off.

The register is the checklist that erosion gets measured against. Six of the twelve exist in some form. Six do
not, and the document says which, rather than implying that a deterministic feature is present because it is
listed.

## The rule that keeps it honest

A row moves to "implemented" only when a test names it. The test names are in the acceptance criteria for the
relevant deliverable, not in this table, because a second place to record the same fact is how two sources of
truth start.

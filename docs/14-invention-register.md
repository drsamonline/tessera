# 14 - Invention register

**Status: Frozen**

Forty claims, reclassified against named prior systems. Adopt the prior art, build the novel, defer the
speculative. *(Closes G-06.)*

| No | Invention | Version | Class | Basis |
|---|---|---|---|---|
| 1 | Bi-temporal records | v1 | Prior art | Snodgrass 1994; implemented in XTDB, Datomic, SQL:2011 system-versioned tables. |
| 2 | Identity spine + federated relationship graph | v1 | Partly novel | Stable UUIDv7 + per-cell provenance + graph overlay is a distinct combination. |
| 3 | Local-first real-time as one sync problem | v1 | Prior art | Local-first literature; Replicache, ElectricSQL, Automerge. |
| 4 | ZK consent proofs | v2 | Research | No production precedent for DPDP consent at the stated timeframe. |
| 5 | Edge-sync with server-offloaded validation | v1 | Prior art | Offline-first plus transactional outbox is a standard pattern. |
| 6 | Conversation-to-record | v1 | Prior art | Email and ICS ingestion is table stakes in every CRM. |
| 7 | Autonomy-aware review queue | v1 | Partly novel | Approval queues are standard; binding them to seat autonomy tiers is not. |
| 8 | Portable record contracts | v1 | Partly novel | Data portability as a contractual artefact with signed attestation. |
| 9 | Seat-based versioned job descriptions | v1 | Novel framing | RBAC plus capacity plus versioning, framed as an org design object. |
| 10 | Mixed-fleet queues | v1 | Prior art | Workforce management plus agent orchestration. |
| 11 | Cost-aware routing | v2 | Prior art | Task routing and auction literature. |
| 12 | Escalation ladder as first-class object | v1 | Prior art | PagerDuty and ServiceNow escalation policies. |
| 13 | Handoff packets with full state and signature | v1 | Partly novel | Full-state handoff with signature is distinct; the concept is not. |
| 14 | Shadow mode / apprenticeship | v1 | Prior art | Shadow deployment and canary release. |
| 15 | AI shift scheduling | v1 | Prior art | Workforce management. |
| 16 | Playbook authoring with deterministic compilation | v1 | Partly novel | The AI-proposal-to-deterministic-workflow gate is distinct. |
| 17 | Workforce analytics with provenance | v2 | Prior art | Data lineage. |
| 18 | Agent-to-agent commerce | v2 | Contested | Active standardisation; A2A and MCP ecosystems. Not a moat. |
| 19 | Customer-side agent bridge | v2 | Speculative | No schema, no counterparty, no adoption path. |
| 20 | Cross-company relationship graph | v2 | Partly novel | Requires bilateral data sharing that no v1 customer has agreed to. |
| 21 | Marketplace with provenance + revenue share | v2 | Prior art | App marketplaces. |
| 22 | Company digital twin | v2 | Undefined | Term used without a model. |
| 23 | Outcome-based billing | v2 | Prior art | Usage and outcome billing exist in metering infrastructure. |
| 24 | Self-improving org | v2 | Speculative | Proposals only, no mechanism. |
| 25 | Protocol-based interop | v2 | Prior art | MCP, A2A, OpenAPI. |
| 26 | Sovereign deployment | v4 | Prior art | Self-hosted and air-gapped deployment. |
| 27 | Dream Layer | v2 | Undefined | Named once, never described. |
| 28 | Universal org chart protocol | v2 | Speculative | No schema given. |
| 29 | Reputation economy for seats | v4 | Partly novel | Trust score as a portable asset. |
| 30 | Sovereign pipeline | v4 | Narrative | A positioning claim, not an invention. |
| 31 | Federated CRM mesh | v1 | Partly novel | Data virtualisation exists; the ledger plus authority-map combination is distinct. |
| 32 | Cross-company chains | v3 | Speculative | No counterparty model. |
| 33 | Universal event ledger | v1 | Prior art | Event sourcing, audit logs, Kafka. |
| 34 | Capability-aware work router | v1 | Prior art | Capability-based routing is standard. |
| 35 | Zero-migration adoption | v1 | Prior art | Federation and virtualisation. |
| 36 | Cross-CRM conflict resolution with provenance | v1 | Partly novel | The combination with a logged authority map is distinct. |
| 37 | Chain-of-chains | v3 | Undefined | Named, never described. |
| 38 | Fair-share distribution | v3 | Prior art | Fair queuing. |
| 39 | Universal dispute trail | v3 | Speculative | No adjudication model. |
| 40 | Mesh-level digital twin | v3 | Speculative | No model. |

## What the counts mean

| Class | Count | What to do |
|---|---|---|
| Prior art | 18 | Adopt an existing implementation. Do not build. |
| Partly novel | 9 | Build the novel part; adopt the rest. |
| Novel framing | 1 | Build. This is a defensible claim. |
| Speculative | 6 | Roadmap only. No v1 obligation. |
| Undefined | 3 | Write the model or delete the claim. |
| Narrative | 1 | Not an invention. Delete from the list. |
| Research | 1 | No production precedent at the stated timeframe. |
| Contested | 1 | Active standardisation elsewhere; not a moat. |

The defensible claim is the eleven in the partly-novel and novel-framing rows. A claim of eleven
distinct mechanisms survives diligence; a claim of forty does not.

Named systems behind each classification: [prior art](research/prior-art.md).

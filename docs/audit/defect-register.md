# Defect register

**Status: Frozen**

Forty-three defects found in the source build prompt, each with location, impact and fix. All 43 are
closed in this repository. The count is the audit's claim; the register is its evidence.

Severity: **Blocker** - construction cannot proceed correctly; **Critical** - a stated guarantee has no
enforcement point; **Major** - the artefact is incomplete in a way a reviewer will find; **Minor** -
ambiguity that costs a decision, not a rewrite.

| ID | Severity | Area | Location | Defect | Impact | Fix |
|---|---|---|---|---|---|---|
| A-01 | **Blocker** | Architecture | Lines 15-26 | Layers 3, 4 and 5 are named in the layer table with target versions but have no section anywhere in the document. | Three of eight declared layers carry zero specification. The document is five written layers plus three placeholders. | Write entry/exit criteria and object models, or move them to a roadmap section and retitle the document. |
| A-02 | **Blocker** | Architecture | Line 4, 261 | 'Do not ask clarifying questions' is combined with roughly twelve undefined mechanisms: trust_score, RVS, both routing scores, history authority, revocation propagation, autonomy tier distinction. | The builder must invent unmarked design decisions, and every invention becomes an unlogged requirement deviation. | Replace with an assumption-register protocol: proceed, but record every assumption with a decision ID; stop only at irreversible or security-irreversible forks. |
| B-01 | **Blocker** | Metrics | Line 41 | Federated routing score is a bare sum of seven incommensurable terms plus two penalties. No weights, no units, no normalization, no tie-break rule. | 'Deterministic' is unfalsifiable. Two implementers produce two different routers from the same text. | Fixed weight vector, per-term [0,1] transform, versioned weights logged with every decision. |
| B-02 | **Blocker** | Metrics | Lines 33, 41, 45, 81 | trust_score is a routing input, an occupant attribute and a conflict tiebreaker, and is never computed. Conflict resolution consumes it; conflicts are its natural input. | Circular definition. The term cannot be implemented without inventing it. | Declare formula, observation window, minimum sample, prior and decay. |
| C-01 | **Blocker** | Runtime | Lines 56, 149, 154-161 | Markdown mirror needs S3, the graph sidecar needs Neo4j, RVS needs the graph. P0 Bare is 'Postgres + app + web' and must pass the full test suite. | Four v1 features cannot run in the profile that is required to pass its own gate. | Publish a per-profile degradation table and make the test suite profile-aware. |
| C-02 | **Blocker** | Runtime | Lines 58, 158 | 'Every write is a commit' against p95 write <50 ms local ack. A durable commit requires fsync plus object write. | Two hard requirements are mutually exclusive. Per-record commit throughput is orders of magnitude below the stated write rate. | Amortised commit model with a separate commit-latency budget. |
| G-01 | **Blocker** | Plan | Lines 189, 209-232 | Twenty-two deliverables, zero acceptance criteria. The build log requires an 'acceptance report' that reports against nothing. | 'Done' is undefined. Every batch is self-certified. | Attach a testable acceptance criterion to each deliverable. |
| A-03 | **Critical** | Architecture | Line 19, 70-89 | Layer 2 is labelled 'v1 simplified' but its object model is specified at full fidelity with no v1/v2 boundary. | Stage 3 cannot be scoped. The builder decides what 'simplified' cuts, and the decision is invisible. | Enumerate the v1 object subset explicitly. |
| A-04 | **Critical** | Architecture | Line 87 | Only one layer boundary has an interface contract ('assign_to_seat is the only bridge'). Mesh-to-core, core-to-experience and workforce-to-ledger have none. | The 'no bypass' and 'no AI in critical path' guarantees have no enforcement point. | Define one interface per layer boundary, each with an enforcement test. |
| B-03 | **Critical** | Metrics | Line 156 | Relationship Velocity Score is described as graph math over frequency, latency asymmetry, meeting density, centrality and decay, with no formula, scale, calibration set or decay constant. | Not reproducible. Any number satisfies the specification. | Publish the formula and a calibration fixture. |
| B-04 | **Critical** | Metrics | Lines 41, 81 | None of the eight routing terms or two penalty terms has a declared range or transform. utilization and cost_efficiency are open-ended. | Term dominance is arbitrary. Utilization alone can swamp capability match. | Declare a transform per term. |
| B-05 | **Critical** | Metrics | Lines 58, 66 | Latency targets state no concurrency, payload size, hardware class, index state, or cache condition. | Unmeasurable, therefore unverifiable at acceptance. | Attach a load model to every target. |
| C-03 | **Critical** | Runtime | Lines 34, 158, 162 | Three independent history mechanisms - bi-temporal columns, git commits, hash-chained events - with no authority rule for 'what each system knew at time T'. | The product's central query has three possible answers. | One authority, the others derived. See section 11. |
| C-04 | **Critical** | Runtime | Line 62 | 'Immutable audit log with SHA-256 chain' on append-only Postgres is tamper-evident only against a database owner who is not the attacker. No external anchor, no verification job, no fork or repair procedure. | The immutability claim fails the first serious audit. | Anchor the chain head externally on a schedule; publish the verification procedure. |
| C-05 | **Critical** | Runtime | Lines 152, 197 | P2 bundles the review queue with the MCP container and the local model, while Stage 3 (v1) requires both MCP tools and the review queue. | v1 cannot ship inside its own profile boundary without starting the containers the AI contract forbids by default. | Move the review queue to P1; keep MCP and models in P2. |
| D-01 | **Critical** | Workforce | Line 85 | v1 autonomy is 'shadow_only and confirm_then_run only', and 'all agent actions to review queue'. If every action goes to review, the two tiers are behaviourally identical. | The autonomy model has one effective state in v1. The tier field is decoration. | Define an observable difference, or collapse to one tier. |
| D-02 | **Critical** | Workforce | Line 89 | 'Removing human stops agent instantly' has no mechanism: no revocation path, no in-flight handling, no propagation deadline, no fail-closed rule. | A safety claim with no enforcement point. | Signed RevocationEvent, poll interval, in-flight abort policy, fail-closed default. |
| E-01 | **Critical** | Compliance | Line 62 | DSAR lifecycle is '30-day tracking', a GDPR transplant. DPDP does not set a 30-day DSAR deadline in that form. | A statutory clock is asserted without a statutory basis. | Parameterise per jurisdiction; confirm with counsel before shipping as a product claim. |
| E-02 | **Critical** | Compliance | Line 136 | 'AI Act classification per AI action (v2+)'. Transparency obligations are enforceable from 2 Aug 2026; Annex III high-risk rules apply from 2 Dec 2027 following the AI Omnibus. | v1 ships agent occupants unclassified during the transparency-obligation period. | Classify at v1; defer only high-risk conformity work. |
| F-01 | **Critical** | Product | Lines 7, 12 | Three incompatible ICPs in one v1: solo founder, 3-10 person B2B agency, 5,000-employee organisation. | Three different products, one backlog. Every prioritisation argument becomes unresolvable. | Name one primary, one secondary, one design constraint. |
| G-02 | **Critical** | Plan | Lines 191-203 | Thirty sprints with no team size, velocity or capacity assumption. | The schedule is unfalsifiable and will be missed silently. | State team shape and re-baseline. |
| A-05 | **Major** | Architecture | Lines 20, 132-136 | Cross-cutting concerns are three bullets, but deliverable 22 requires full specifications of them. | The largest surface - authn/authz, audit, residency - is promised and unspecified. | Promote to full sections. |
| A-06 | **Major** | Architecture | Line 39 | Connector interface lists eight methods with no error taxonomy, pagination contract, partial-failure semantics, or schema-drift detection. | Four connectors cannot be built to a common contract; drift will surface as production incidents. | Add error classes and drift detection to the interface. |
| B-06 | **Major** | Metrics | Lines 7, 58 | 'No perceptible slowdown as data grows' is unbounded and contradicts the 1M-record bound two pages later. | A 5,000-employee tenant exceeds the tested bound while the product claim survives it. | Replace with a stated scaling curve and a re-test trigger. |
| B-07 | **Major** | Metrics | Line 58 | No measurement harness, percentile window or regression gate is defined for any latency target. | Targets cannot regress-detect; performance drift is invisible until customers report it. | Define harness, window and CI gate. |
| C-06 | **Major** | Runtime | Lines 56, 148-152 | Flutter/SQLCipher mobile is a v1 deliverable and appears in no deployment profile. | Mobile has no runtime contract and no profile acceptance test. | Add mobile rows to the profile matrix. |
| C-07 | **Major** | Runtime | Line 152 | The review queue is a deterministic feature but is bundled into the AI profile, while the spec forbids labelling deterministic features as AI. | The product's own AI contract contradicts its deployment profile. | Decouple. |
| D-03 | **Major** | Workforce | Line 79 | Escalation ladders terminate at an unspecified state and can exhaust in a human-only deployment. | Tasks can hang in an undefined state with the SLA still running. | Declare terminal states and their SLA effect. |
| D-04 | **Major** | Workforce | Line 83 | 'SLA clock carries across handoffs' with no rule for a receiving seat that declares a different SLA. | The clock can expire against a seat that never accepted it. | Re-evaluate SLA at handoff; record both clocks. |
| D-05 | **Major** | Workforce | Line 75 | Seats are versioned, but there is no rule for in-flight tasks when permissions_scope or required_capabilities change. | A permission change can retroactively alter the authority of work already in progress. | Pin the task to the seat version at assignment. |
| E-03 | **Major** | Compliance | Line 136 | No DPIA, no record of processing, no sub-processor register, no residency option at v1, for a multi-tenant SaaS fanning contact data across four external nodes. | The compliance substrate is a feature list, not a control set. | Add the four artefacts as v1 deliverables. |
| E-04 | **Major** | Compliance | Line 62 | Consent is modelled as a field (consent_state), not as notice plus purpose-bound consent. | Purpose limitation cannot be enforced from a state field alone. | Model notice and purpose, not just state. |
| F-02 | **Major** | Product | Lines 12, 72 | Seat-based workforce value requires multi-occupant organisations. The stated primary ICP has one occupant. | The core differentiation is inert for the first customer. | State the solo-founder value path, or change the ICP. |
| F-03 | **Major** | Product | Line 11 | 'Aha moment at minute 4' has no event, no funnel step and no definition of the end state. | The central activation metric is unmeasurable. | Name the activation event. |
| G-03 | **Major** | Plan | Line 193 | Stage 1 builds the HubSpot connector before the canonical schema is versioned and before conflict resolution exists. | The schema will change under a live connector; rework is scheduled in, not budgeted. | Version the schema and land conflict resolution before the second connector. |
| G-04 | **Major** | Plan | Line 203 | External security audit sits in Stage 6 with no pre-audit hardening gate and no remediation sprint. | Audit findings land after launch assets are built and cannot be fixed before launch. | Add a hardening gate and reserve two sprints. |
| G-06 | **Major** | Plan | Lines 177-185 | Forty inventions claimed with no novelty audit. At least twenty are documented prior art. | The differentiator list overstates the product by roughly a factor of two, and investors will find it. | Reclassify every entry. See section 8. |
| H-01 | **Major** | Document | Whole document | Eleven wedge-and-moat triad constructions, nine one-line closers, fourteen subjectless imperatives, six unbounded absolutes ('never', 'instantly', 'always', 'no perceptible'). | Unbounded absolutes become untestable acceptance criteria; the triad pattern replaces argument with rhythm. | Rewrite absolutes as bounded claims; cut the triads. |
| D-06 | **Minor** | Workforce | Lines 77-78 | Task.handoff_chain and HandoffPacket have no declared relationship. | Ambiguous model; two reasonable schemas. | Declare the type. |
| E-05 | **Minor** | Compliance | Lines 209-232 | No LICENSE, SECURITY.md, DPA template or EULA among the 22 deliverables. | Enterprise procurement blocks on all four. | Add to Stage 5. |
| F-04 | **Minor** | Product | Lines 11, 116, 256 | Three clocks - 4-minute aha, 10-minute onboarding, 30-minute switching cost - with no stated relationship. | Ambiguous acceptance for the onboarding deliverable. | State which clock is the gate. |
| G-05 | **Minor** | Plan | Line 189 | Build-log fields are named with no format, schema or retention rule. | Seven fields per batch, seven formats. | Publish a schema. |
| H-02 | **Minor** | Document | Whole document | No version, author, date, status or change log on the document itself. | No way to tell which build used which prompt revision. | Add document control. |

## Counts

| Severity | Count |
|---|---|
| Blocker | 7 |
| Critical | 14 |
| Major | 17 |
| Minor | 5 |
| **Total** | **43** |

| Area | Count |
|---|---|
| Architecture | 6 |
| Metrics | 7 |
| Runtime | 7 |
| Workforce | 6 |
| Compliance | 5 |
| Product | 4 |
| Plan | 6 |
| Document | 2 |

How the audit was run: [method.md](method.md). Why the fixes are sequenced as they are:
[remediation-order.md](remediation-order.md).

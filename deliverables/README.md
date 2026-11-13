# Rendered deliverables

The same specification as circulation files, produced on 14 November 2026 under the working name **CRM Fabric**.
The product name in these files is the old one; the content matches the markdown in [../docs](../docs/index.md)
with that single difference.

| File | What it is | Pages |
|---|---|---|
| [CRM_Fabric_Audit.pdf](CRM_Fabric_Audit.pdf) | The audit report: 43 defects, seven undefined scores, the profile conflicts, the novelty reclassification | 11 |
| [CRM_Fabric_Spec_v1.1.docx](CRM_Fabric_Spec_v1.1.docx) | The restructured specification, gap-closed, with acceptance criteria | 20 |
| [CRM_Fabric_Traceability.xlsx](CRM_Fabric_Traceability.xlsx) | Eight matrices: defects, deliverables, inventions, metrics, profiles, stages, assumptions, live summary | 8 sheets |

## Which one wins

The markdown in `docs/` is the source of truth. If a rendered file disagrees with it, the markdown is right and
the rendered file is stale.

## Regenerating

There is no generator in this repository yet. The files were produced from the source document by a one-off
build, and the markdown was then written by hand from the same content. Adding a generator is a reasonable
future task; claiming one exists today would be false.

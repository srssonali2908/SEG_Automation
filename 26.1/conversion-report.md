# Conversion report: Smoke Test User Guide

## Source

| Item | Value |
| --- | --- |
| groupId (`ft:clusterId`) | `999001` |
| version | `26.1` |
| lastPublished (requested) | `2026-10-15T09:30:00Z` |
| lastPublished (pinned) | `2026-10-15T09:30:00+00:00` |
| snapshot id | `snap-2026-10-15` |
| root map | `maps/user-guide.ditamap` |
| `ft:originId` | `999002` |
| ID source | fixture (verified) |
| markdown mode | portable |

## Counts

| Metric | Count |
| --- | --- |
| Topic files written | 6 |
| Topicref occurrences (shared topics counted each time) | 7 |
| Nested maps | 1 |
| Navigation groups (topichead) | 1 |
| index.md files (incl. root) | 4 |
| Images in assets/ | 1 |
| Unresolved references | 2 |
| Warnings | 2 |

## Unresolved references

| Kind | Target | Source | Detail |
| --- | --- | --- | --- |
| xref | `does-not-exist.dita` | `topics/troubleshooting.dita` | target is not part of the converted publication |
| image | `images/missing.png` | `topics/troubleshooting.dita` | image not found in publication |

## Warnings

- topics/settings.dita: 1 code block(s) had no language; tagged 'text'.
- content_classification not provided; defaulting to 'confidential' (fail-safe).

## Open metadata items (resolve before production)

- Confirm content_classification (defaulted to confidential).
- Set author to the owner's email.
- Set prod_publishers (comma-separated GitHub usernames).

## Standing notes

- No DITAVAL/conditional filtering is applied by this converter; the pinned published snapshot is used as-is.
- Task section labels (Before you begin / Result / What to do next) follow DITA-OT defaults.
- Relative links between topic files are used for modularity; confirm they render in the Dev preview.
- Technical content is not rewritten; unsupported elements are emitted as their text and listed above.

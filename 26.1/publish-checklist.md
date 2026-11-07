# Publish checklist: Smoke Test User Guide

Generated for groupId `999001`, version `26.1`.
`ft:clusterId: 999001` / `ft:originId: 999002` (verified against Document Number Control; source: fixture).

> [!IMPORTANT]
> This output is **published: false** (Dev preview only). The converter never publishes and never
> sets `published: true`; a human does that after the gates below pass.

## Items the converter flagged

  - [ ] Confirm content_classification (defaulted to confidential).
  - [ ] Set author to the owner's email.
  - [ ] Set prod_publishers (comma-separated GitHub usernames).

## Steps

1. [ ] **Confirm or create Asset IDs** in Document Number Control
   (`https://seg.altera.com:3033/doc-control`). `ft:clusterId` is the group ID (shared by all versions);
   `ft:originId` is this version's ID. Do not invent or hand-edit IDs; the publisher verifies that the
   origin belongs to the cluster.
2. [ ] **Verify the metadata block** at the top of `index.md`: `title`, `description`, `family: NA`,
   `category`, `content_classification` (`public`/`confidential`; missing or invalid is treated as
   confidential), `design_type: NA`, `quartus_version` (`x.x` or `x.x.x`, `Pro`/`Standard` prefix OK),
   `author`, `prod_publishers`. The block must be at the very top and not inside `<!-- -->`.
3. [ ] **Preview** in the Altera Markdown Publisher (Documentation Hub -> Altera Markdown at docs.altera.com
   -> Single Document), run the built-in quality check, then **Publish to Dev**.
   - [ ] Confirm the Single Document flow follows the relative links from `index.md` into the nested
     folders and `assets/`. If it only renders the picked file, stop and ask the publisher owners how
     modular sources should be supplied (do not flatten without approval).
4. [ ] **Review** the Dev rendering (content, formatting, links, images, metadata). Fix and re-preview
   until clean. Review `conversion-report.md` (unresolved references, warnings).
5. [ ] **Production only when every gate passes** (enforced server-side):
   - [ ] Your GitHub user is in `prod_publishers` (or you are an admin)
   - [ ] `published: true` set **by a human** in the entry metadata
   - [ ] Valid `quartus_version`
   - [ ] Asset IDs verified (cluster exists, origin belongs to it)
   - [ ] Technical Writer sign-off (required on first publish, or for a major update: >= 300 changed
     lines, Quartus version change, classification change, or title change)
   - [ ] Editorial quality gate passed (blocking high-severity issues such as broken links or references
     to undefined figures/tables must be fixed)
6. [ ] **Archive:** after a successful production publish the app automatically saves a dated snapshot and
   `record.json` to `altera-innersource/documentation.fpga.modular` under
   `<userguides|release-notes>/<ft:clusterId>/<ft:originId>/<version>/<MM-DD-YYYY-NN>/`. You need
   collaborator write access to that repository.

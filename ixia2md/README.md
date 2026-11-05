# ixia2md: IXIA CCMS to Markdown

Takes a document ID, an origin ID and an optional version, fetches the matching published snapshot from IXIA CCMS, converts the DITA to Markdown with DITA-OT, checks the result, and returns an output folder (also as a ZIP). With no version it uses the latest published snapshot. A web app for seg.altera.com sits on top.

## Run it

```bash
pip install -r requirements.txt            # requests, lxml
export CCMS_URL=... CCMS_USER=... CCMS_PASSWORD=...      # from your secret manager, never in git
export DITA_OT_HOME=/path/to/dita-ot-4.3.4               # needs Java 17+

python -m ixia2md.cli --doc-id /Content/Guide/guide.ditamap --origin-id ORIG-1          # latest published
python -m ixia2md.cli --doc-id /Content/Guide/guide.ditamap --version 3 --flavor markdown_gitbook
python -m ixia2md.app --port 8080                                                       # the web app
```

Try it without a real CCMS: `python -m ixia2md.mock_ccms --port 8099` (user demo / password demo), then set `CCMS_URL=http://127.0.0.1:8099`.

Tests: `DITA_OT_HOME=... python -m pytest tests`. Docker: `docker build -t ixia2md .` (bundles Java and DITA-OT).

## Output folder

```
output/
  index.md  <topic>.md ...   Markdown (index.md carries front matter: document, origin, version, snapshot)
  images/                    figures
  manifest.json              what was built, counts, quality tally
  quality-report.md          the checks below
  conversion.log             DITA-OT log
```

## What is verified and what is not

Verified: the whole pipeline runs end to end against the **mock** CCMS (12 tests pass), with DITA-OT 4.3.4 and a small sample map.

**Not verified against a real CCMS.** Everything marked ASSUMPTION needs confirming with IXIASOFT, and each sits in one place:

| Assumption | Where to change it |
|---|---|
| Sign-in is `POST /sessions/authorize` with a JSON body `{userName, password}` returning an `IxiaAuth` cookie (the docs name the path only) | `CCMS_LOGIN_*` settings, `CcmsClient.login` |
| Snapshot list and snapshot contents JSON shapes (`result`, `objects`, `documentIdentifier`, `genericObjectType`) | `parse_snapshot_list`, `parse_snapshot_objects` in `ccms.py` |
| "Published" means `currentStatus` is `Published` | `CCMS_PUBLISHED_STATUSES` |
| Snapshot version and origin are properties named `version` and `originIdentifier` | `CCMS_VERSION_FIELD`, `CCMS_ORIGIN_FIELD` |
| The Document ID you enter is the map's repository path | `resolve.py` |
| `GET /files?url=` returns an object as it was in the snapshot | check with IXIASOFT |

## Quality checks

Scored against a baseline built from the DITA source (sections, tables, figures, notes, related-information blocks, symbols). Fail: missing sections, tables or figures, leaked page furniture, raw DITA tags, broken links or images, garbled characters. Warn: skipped heading levels, missing alt text, missing front matter. A reference baseline can replace the source-derived one: `tools/build_pdf_baseline.py reference.txt baseline.json`, then `QA_BASELINE=baseline.json` (`tools/baseline_gts_sample.json` is the GTS sample).

DITA-OT drops table titles in Markdown output, so a preparation step turns table and figure titles into visible captions before conversion.

## Before production

- Put the app behind company SSO. It reads the user from `X-Forwarded-User` or `X-Auth-Request-Email` and logs each run, but does no sign-in itself.
- It is a standard-library server with in-memory job state: fine for a team tool, put it behind a proper server and a queue before heavy use.
- Runs expire after 24 hours. Source drafts (for example "Draft Copy, Do Not Distribute") stay on the server only for that time.
- Add the Altera logo and the Myriad Pro font from your brand team; the app uses the theme colors and a font fallback.

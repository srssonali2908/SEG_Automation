# SEG_Automation

Internal Altera Scale Enablement Group (SEG) automation. This repository contains:

- **AssetTool**, a Windows asset-ID registrar
- **BrokenLinkChecker**, a PDF hyperlink checker ([see below](#brokenlinkchecker))

## What AssetTool does

AssetTool issues unique IDs for SEG documentation assets and records each request.

Every asset has:

- **Cluster ID** — the asset itself
- **Origin ID** — one instance or version of that asset

A new asset gets both IDs. An existing asset keeps its Cluster ID and gets a new Origin ID.

Supported asset types:

| Type | ID prefix | Example |
|---|---|---|
| DITA | `D` | `D157193` |
| Resource | `R` | `R117428` |
| Markdown | `M` | `M877819` |

Each ID is a prefix plus 6 random digits. The script checks Excel so the same ID is not reused.

## How it works

1. Double-click `AssetTool.bat` (runs `AssetTool.vbs` with `cscript`).
2. On first run, enter your email. It is saved to `C:\AssetTool\user_config.txt` and reused later.

3. Writers have Sharepoint synced in there local machine as shown below , actual sharepoint location is **https://altera.sharepoint.com/:x:/r/sites/psg-CIG/Shared%20Documents/PSG%20Spin%20Off/AssetID/AssetData.xlsx?d=wb922c52e1f314f8ebfcbf7efb4a15805&csf=1&web=1&e=EXJRyv**

   
5. Excel opens in the background:
   `C:\Users\<you>\Altera\Scale Enablement Group (SEG) - AssetID\AssetData.xlsx`
6. Choose **1** (new asset) or **2** (existing asset).
7. The script writes a new Excel row:

   | Column | Field |
   |---|---|
   | 1 | Cluster ID |
   | 2 | Origin ID |
   | 3 | Asset type |
   | 4 | Title |
   | 5 | Requester email |
   | 6 | Architect email |

8. A receipt is saved as `C:\AssetTool\entries\Asset_<ClusterID>_<OriginID>.txt`.
9. Outlook sends mail to the requester and CCs the architect.

### New asset (choice 1)

Asks for asset type and title, then generates a unique Cluster ID and Origin ID.

### Existing asset (choice 2)

Asks for an existing Cluster ID, title, and type for the new origin. If the Cluster ID is not in Excel, the script stops. If it is found, only a new Origin ID is created.

## Requirements

- Windows
- Microsoft Excel
- Microsoft Outlook
- Access to the SEG AssetID Excel location

## Files

| File | Purpose |
|---|---|
| `AssetTool.bat` | Launcher |
| `AssetTool.vbs` | Main registrar script |
| `entries/` | Text receipts for created IDs |

`user_config.txt` is local-only and is not committed.

## BrokenLinkChecker

`BrokenLinkChecker/` checks every external hyperlink in a PDF and produces a CSV report (`broken-links-<pdf name>.csv`). Internal document anchors are skipped, and each distinct URL is checked once, in parallel.

### Running it

Requires Python 3.8+.

- **Web page:** double-click `BrokenLinkChecker\BrokenLinkChecker.bat`. It installs the dependencies, starts the app, and opens http://127.0.0.1:5000. Upload a PDF and the CSV downloads automatically.
- **Command line:**

  ```
  cd BrokenLinkChecker
  pip install -r requirements.txt
  python link_checker.py "My Guide.pdf" -o report.csv
  ```

### Report columns

| Column | Meaning |
|---|---|
| Page Number | PDF page the link is on |
| Original Link | URL as written in the PDF |
| Status / Error Code | `200 OK`, `HTTP <code>`, `Connection Failed`, `Corporate Network Required`, or `Request Error` |
| Redirect History (From -> To) | Final URL after redirects, or `None` if the link did not redirect |
| Contains Intel? | `Yes` if the link points at `intel.com` |
| Broken? | `No` for `200 OK`, `Unverified (VPN)` for corporate links that could not be reached, otherwise `Yes` |

### Intel / Altera handling

- `corpredirect.intel.com` 404-redirector links are unwrapped and the embedded target is checked.
- Known looping directory pages (for example `https://www.altera.com/design`) are mapped to their public equivalents.
- If a host is unreachable, a `/programmable/<doc id>` link is retried at `https://docs.altera.com/r/docs/<doc id>/current`.
- Unreachable `intel.com` / `altera.com` hosts are reported as `Corporate Network Required` rather than broken. Run the checker on VPN to verify those links.

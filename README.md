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

### Standalone app (recommended)

`BrokenLinkChecker.exe` is a single Windows program. It needs no Python, installer or browser.

1. Get the exe:
   - From the repo's **Releases** page, or
   - From **Actions → Build BrokenLinkChecker.exe →** latest run **→ Artifacts → BrokenLinkChecker** (download and unzip).
2. Double-click `BrokenLinkChecker.exe`. You can also drop a PDF onto the exe icon.
3. Click **Choose PDF...**, then **Check links**.
4. Review the results: broken links are red and links that need VPN are yellow. Tick **Show only problems** to filter, or double-click a row to open the link.
5. Click **Save CSV report...** to export.

Windows SmartScreen may warn the first time because the exe isn't code-signed. Choose **More info → Run anyway**.

**Building the exe yourself:** on a Windows PC with Python 3.10+, double-click `BrokenLinkChecker\build_exe.bat`. The result is `BrokenLinkChecker\dist\BrokenLinkChecker.exe`. The GitHub workflow also builds it on every change to `BrokenLinkChecker/`. Pushing a tag such as `blc-v1.0` publishes it as a release.

### Other ways to run it (Python 3.10+)

- **Desktop app from source:** `python gui.py`
- **Web page:** double-click `BrokenLinkChecker\BrokenLinkChecker.bat`. It installs the dependencies, starts the app, and opens http://127.0.0.1:5000. Upload a PDF and the CSV downloads automatically.
- **Command line:**

  ```
  cd BrokenLinkChecker
  pip install -r requirements.txt
  python link_checker.py "My Guide.pdf" -o report.csv
  ```

### Hosting it on a web2py server (for example seg.altera.com)

The `web2py/` folder adds the checker as a page in an existing web2py application. It works on Python 3 and on Python 2.7, with either `pypdf` or `PyPDF2`. Copy three files into the application (`applications/<app>/`):

| From this repo | To the web2py application |
|---|---|
| `BrokenLinkChecker/link_checker.py` | `modules/link_checker.py` |
| `BrokenLinkChecker/web2py/controllers/broken_link_checker.py` | `controllers/broken_link_checker.py` |
| `BrokenLinkChecker/web2py/views/broken_link_checker/index.html` | `views/broken_link_checker/index.html` |

The server needs `requests` and either `pypdf` (Python 3) or `PyPDF2` (Python 2.7). The page is then served at `https://<server>/<app>/broken_link_checker/index`.

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

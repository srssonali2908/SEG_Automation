# SEG_Automation

Internal Altera Scale Enablement Group (SEG) automation. This repository currently contains **AssetTool**, a Windows asset-ID registrar.

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
3. Excel opens in the background:
   `C:\Users\<you>\Altera\Scale Enablement Group (SEG) - AssetID\AssetData.xlsx`
4. Choose **1** (new asset) or **2** (existing asset).
5. The script writes a new Excel row:

   | Column | Field |
   |---|---|
   | 1 | Cluster ID |
   | 2 | Origin ID |
   | 3 | Asset type |
   | 4 | Title |
   | 5 | Requester email |
   | 6 | Architect email |

6. A receipt is saved as `C:\AssetTool\entries\Asset_<ClusterID>_<OriginID>.txt`.
7. Outlook sends mail to the requester and CCs the architect.

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

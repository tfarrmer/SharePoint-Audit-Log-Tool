# Tool User Guide

## What This Tool Does

This tool takes data exported from the Microsoft 365 admin center and Microsoft Purview, combines it, and generates a single Excel report with three tabs:

- **User Summary** — shows every licensed user, how many files they've uploaded, modified, and deleted on SharePoint, and their total upload volume
- **File Activity Log** — a detailed log of every file upload, modification, deletion, move, and rename across SharePoint over the past 6 months
- **All Licensed Users** — shows every user's Microsoft 365 license assignments for SharePoint and Teams, along with their last activity dates

---

## What You Need Before Running the Tool

### Software (one-time setup)

1. **Python 3.10 or higher** — download from https://www.python.org/downloads/
   - During installation, check "Add Python to environment variables" (also called "Add to PATH")
2. **Required Python libraries** — open a terminal and run:
   ```
   python -m pip install pandas openpyxl
   ```
3. **VS Code** or any other terminal, but VS Code is easiest to use.

### Data Exports (every time you run the tool)

You need three sets of data. All are exported from Microsoft web portals.

**Export 1 — Office 365 Active User Detail**
- Go to https://admin.microsoft.com
- Navigate to Reports → Usage
- Click "View more" under "Active users — Microsoft 365 Services" (left card)
- Click the "Active Users" tab
- Click Export
- This file will be named something like `Office365ActiveUserDetail6_15_2026 1_53_22 PM.xlsx`

**Export 2 — SharePoint Site Usage Detail**
- Go to https://admin.microsoft.com
- Navigate to Reports → Usage → SharePoint site usage
- Click the Export button at the bottom left of the page (not the individual chart exports)
- This file will be named something like `SharePointSiteUsageDetail6_15_2026 1_34_35 PM.csv`

**Export 3 — Purview Audit Logs**
- Go to https://compliance.microsoft.com
- Navigate to Audit
- Create searches in 1-month intervals over the past 6 months:
  - Dec 12 – Jan 12
  - Jan 12 – Feb 12
  - Feb 12 – Mar 12
  - Mar 12 – Apr 12
  - Apr 12 – May 12
  - May 12 – Jun 12
- For each search, set the Workload filter to "SharePoint"
- Once each search completes, export the results as a CSV
- You will have 6 CSV files

**Why 1-month intervals?** Purview times out on large date ranges. Breaking into monthly chunks ensures each search completes successfully.

---

## Folder Setup

Place everything in one folder like this:

```
Scripts/
├── audit_final.py                              ← the tool
├── Office365ActiveUserDetail6_15_2026...xlsx   ← Export 1 (any name starting with Office365ActiveUserDetail)
├── SharePointSiteUsageDetail6_15_2026...csv    ← Export 2 (any name starting with SharePointSiteUsageDetail)
└── purview/                                    ← create this folder
    ├── dec-jan.csv                             ← Export 3 (all Purview CSVs go here)
    ├── jan-feb.csv
    ├── feb-mar.csv
    ├── mar-apr.csv
    ├── apr-may.csv
    └── may-jun.csv
```

**You do not need to rename any files.** The tool auto-detects files by their prefix. As long as the file name starts with `Office365ActiveUserDetail` or `SharePointSiteUsageDetail`, the tool will find it. Both `.csv` and `.xlsx` formats are supported.

The Purview CSVs can have any name — the tool reads every `.csv` file inside the `purview` folder.

---

## How to Run the Tool

1. Open a terminal in the Scripts folder
   
2. Run the command:
   ```
   python audit_final.py
   ```
3. The tool will print its progress:
   ```
   Reading M365 exports...
   Found: Office365ActiveUserDetail6_15_2026 1_53_22 PM.xlsx
   Found: SharePointSiteUsageDetail6_15_2026 1_34_35 PM.csv
   Reading Purview audit logs...
     Loaded dec-jan.csv: 50000 rows
     Loaded jan-feb.csv: 50000 rows
     ...
   Parsing audit log details...
   Building User Summary tab...
   Building Licensed Users tab...
   Writing report...
   Formatting...
   Done! Report saved to: M365_Audit_Report.xlsx
   ```
4. Open `M365_Audit_Report.xlsx` in Excel — your report is ready

---

## Understanding the Report

### Tab 1 — User Summary

Each row is one user. Sorted by heaviest uploaders at the top.

| Column | What it means |
|--------|--------------|
| Display Name | The user's name |
| Email | Their Microsoft 365 email address |
| Has SharePoint License | Whether they are licensed for SharePoint |
| SharePoint Last Active | The last date they used SharePoint |
| Files Uploaded | Number of files they uploaded in the past 6 months |
| Files Modified | Number of files they modified in the past 6 months |
| Files Deleted | Number of files they deleted in the past 6 months |
| Total Actions | Total file operations (uploads + modifications + deletions + moves + renames) |
| Total Upload Volume (MB) | Total size of files they uploaded/modified, in megabytes |
| Sites Owned | Number of SharePoint sites they own |
| SharePoint Storage (GB) | Storage consumed by sites they own (not personal usage) |
| Total Files | Total file count across sites they own |

### Tab 2 — File Activity Log

Each row is one file action. Sorted by most recent first.

| Column | What it means |
|--------|--------------|
| Date/Time | When the action happened |
| User | Who performed the action |
| Action | What they did (FileUploaded, FileModified, FileDeleted, etc.) |
| File Name | Name of the file |
| File Extension | File type (xlsx, docx, pdf, etc.) |
| Folder Path | The folder location within the SharePoint site |
| Site URL | Which SharePoint site it happened on |
| File Size (Bytes) | File size in bytes (blank for some operation types) |
| File Size (MB) | File size in megabytes (blank for some operation types) |

### Tab 3 — All Licensed Users

Each row is one user. Shows licensing status.

| Column | What it means |
|--------|--------------|
| Display Name | The user's name |
| Email | Their Microsoft 365 email address |
| Assigned Products | What Microsoft 365 licenses they have |
| Has SharePoint License | Whether they are licensed for SharePoint |
| Has Teams License | Whether they are licensed for Teams |
| SharePoint Last Active | Last date they used SharePoint |
| Teams Last Active | Last date they used Teams |
| Is Deleted | Whether the account has been deleted |

---

## Troubleshooting- 

**"Python was not found"**
Python is not on your PATH. Reinstall Python and check "Add Python to environment variables" during setup.

**"No module named 'pandas'"**
Run `python -m pip install pandas openpyxl` to install the required libraries.

**"Could not find a file starting with..."**
The tool cannot find one of the required export files. Make sure the file is in the same folder as the script and its name starts with the expected prefix.

**"No CSV files found in 'purview/' folder"**
Create a folder called `purview` in the same directory as the script and place your Purview export CSVs inside it.

**Blank file sizes in the activity log**
This is a Microsoft limitation. Purview does not include file size data for all operation types. File sizes are most consistently available for FileUploaded and FileModified actions.

---

## Permissions Required

To export the data, you need:

- **M365 Admin Center exports**: Global Reader + Reports Reader roles in Entra ID
- **Purview audit log exports**: View-Only Audit Logs role (or equivalent) in the compliance portal

If you cannot access either portal, contact your Entra ID administrator.

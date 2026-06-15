# M365 SharePoint Audit Tool

A Python-based audit tool that tracks Microsoft 365 licensing and SharePoint storage activity across an organization. Built during an IT internship at Axion BioSystems to give IT administrators visibility into who is consuming shared storage, what files they are uploading, and whether licensed users are actively using their assigned services.

## What It Does

- Identifies all licensed M365 users and their SharePoint/Teams license status
- Reports per-user SharePoint file activity — uploads, modifications, deletions — over a 6-month window
- Calculates total upload volume per user from Purview audit log data
- Combines licensing, storage, and activity data into a single Excel report

## Output

The tool generates `M365_Audit_Report.xlsx` with three tabs:

| Tab | Description |
|-----|-------------|
| **User Summary** | Each user's upload volume, file activity counts, SharePoint license status, and last activity date. Sorted by heaviest uploaders. |
| **File Activity Log** | Every file upload, modification, deletion, move, and rename with timestamps, file names, folder paths, and site URLs |
| **All Licensed Users** | Full licensing overview showing SharePoint and Teams license status and last activity per service |

## Requirements

- Python 3.10+
- pandas
- openpyxl

Install dependencies:
```bash
python -m pip install pandas openpyxl
```

## Usage

### 1. Export your data

**From admin.microsoft.com → Reports → Usage:**
- Office 365 Active User Detail (Services → Active Users tab → Export)
- SharePoint Site Usage Detail (SharePoint site usage → Export at bottom left)

**From compliance.microsoft.com → Audit:**
- Run 6 monthly searches (1-month intervals) with SharePoint workload filter
- Export each as a CSV

### 2. Set up your folder

```
project/
├── audit_final.py
├── Office365ActiveUserDetail[timestamp].xlsx
├── SharePointSiteUsageDetail[timestamp].csv
└── purview/
    ├── month1.csv
    ├── month2.csv
    └── ...
```

No renaming required — the script auto-detects files by prefix.

### 3. Run the tool

```bash
python audit_final.py
```

The report saves to the same folder as the script.

## Architecture

```
audit_final.py          # Core logic — file detection, data processing, report generation
.gitignore              # Prevents CSV/XLSX data files from being committed
TOOL_GUIDE.md           # End-user instructions for running the tool
```

### Data flow

1. **Office 365 Active User Detail** → licensing status and last activity dates per service
2. **SharePoint Site Usage Detail** → storage per site and site ownership
3. **Purview Audit Logs** → individual file operations parsed from JSON AuditData field
4. **pandas** → cross-references and merges all three sources on user email (UPN)
5. **openpyxl** → formats and outputs the final Excel report

### Purview chunking

Purview times out on large date ranges. The tool is designed to accept multiple monthly CSV exports from the `purview/` folder, which are combined automatically at runtime.


## Security Notes

- No API keys or credentials in this repository
- All CSV/XLSX data files are excluded via `.gitignore`
- Phase 2 credentials will be stored in a `.env` file (also excluded from git)

## Author

Travis Farmer - Comp Sci Student @ Georgia State University and IT Intern @ Axion BioSystems

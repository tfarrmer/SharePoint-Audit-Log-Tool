# M365 SharePoint Audit Tool

A Python-based audit tool that tracks Microsoft 365 licensing and SharePoint storage activity across an organization. Built during an IT internship at Axion BioSystems to give IT administrators visibility into who is consuming shared storage, what files they are uploading, and whether licensed users are actively using their assigned services.

## What It Does

- Authenticates to Microsoft Graph API via OAuth 2.0 and pulls all data automatically — no manual exports required
- Identifies all licensed M365 users and their SharePoint/Teams license status
- Reports per-user SharePoint file activity — uploads, modifications, deletions — over a rolling 30-day window
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
- requests
- python-dotenv

Install dependencies:
```bash
python -m pip install pandas openpyxl requests python-dotenv
```

## Setup

### 1. Configure credentials

Create a `.env` file in the project folder:

```
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
```

These credentials come from an app registration in Microsoft Entra ID with the following permissions:
- `Reports.Read.All` (Microsoft Graph, Application)
- `AuditLogsQuery.Read.All` (Microsoft Graph, Application)

Both permissions require admin consent from a tenant administrator.

### 2. Run the tool

```bash
python audit_final.py
```

The tool will:
1. Authenticate to Microsoft Graph API
2. Pull Office 365 Active User Detail and SharePoint Site Usage reports
3. Run a Purview audit log search for the past 30 days (SharePoint file activity)
4. Generate `M365_Audit_Report.xlsx` in the same folder

## Architecture

```
audit_final.py      # Core logic — data processing and report generation
data_fetcher.py     # API layer — authenticates and pulls all three data sources
.env                # Credentials (excluded from git)
.gitignore          # Prevents sensitive files from being committed
TOOL_GUIDE.md       # End-user instructions
```

### Data flow

1. **data_fetcher.py** authenticates via OAuth 2.0 client credentials flow
2. **Graph Reports API** → Office 365 Active User Detail + SharePoint Site Usage Detail
3. **Purview Audit Search API** → SharePoint file activity logs (paginated, handles token refresh automatically)
4. **audit_final.py** normalizes and merges all three sources on user email (UPN)
5. **openpyxl** formats and outputs the final Excel report

### Key engineering decisions

- **Monthly chunking:** Purview times out on large date ranges. The tool searches in 1-month intervals and polls all searches simultaneously, reducing wait time from sequential hours to the duration of the longest single search.
- **Automatic token refresh:** Microsoft Graph access tokens expire after 1 hour. The tool detects 401 errors and re-authenticates automatically without interrupting long-running searches.
- **Pagination:** The Purview API returns results in pages of 150 records. The tool fetches all pages automatically, bypassing the 50,000-row cap of manual CSV exports.
- **Retry logic:** 429 (rate limit) and 504 (server timeout) errors are caught and retried automatically with a delay.

## Security Notes

- No API keys or credentials in this repository
- All CSV/XLSX data files are excluded via `.gitignore`
- `.env` file is excluded from version control
- Each user should create their own client secret under the shared app registration

## Phase 3 (Planned)

- tkinter GUI with report destination picker
- Standalone `.exe` packaging via PyInstaller
- Windows Task Scheduler integration for monthly automated runs

## Author

Travis Farmer — CS Student @ Georgia State University | IT Intern @ Axion BioSystems

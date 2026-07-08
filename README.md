# M365 SharePoint Audit Tool

A Python-based audit tool that automatically tracks Microsoft 365 licensing and SharePoint storage activity across an organization. Built during an IT internship at Axion BioSystems to give IT administrators visibility into who is consuming shared storage, what files they are uploading, and whether licensed users are actively using their assigned services.

## What It Does

- Authenticates to Microsoft Graph API via OAuth 2.0 client credentials flow — no manual exports required
- Pulls M365 licensing data and SharePoint site usage directly from the Graph Reports API
- Searches Microsoft Purview audit logs for 30 days of SharePoint file activity (uploads, modifications, deletions)
- Combines all three data sources into a formatted three-tab Excel report
- Emails the report automatically via Microsoft Graph `sendMail` API when complete
- Provides a GUI so non-technical users can generate reports without touching a terminal

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

Copy `.env.example` to `.env` and fill in your values:

```
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
SENDER_EMAIL=it@yourcompany.com
RECIPIENT_EMAIL=recipient@yourcompany.com
```

These credentials come from an app registration in Microsoft Entra ID with the following permissions:
- `Reports.Read.All` (Microsoft Graph, Application)
- `AuditLogsQuery.Read.All` (Microsoft Graph, Application)
- `Mail.Send` (Microsoft Graph, Application)

All three permissions require admin consent from a tenant administrator.

### 2. Run the tool

**GUI (recommended):**
```bash
python audit_gui.py
```

**Command line:**
```bash
python audit_final.py
```

The tool will:
1. Authenticate to Microsoft Graph API
2. Pull Office 365 Active User Detail and SharePoint Site Usage reports
3. Create a Purview audit log search for the past 30 days (SharePoint file activity)
4. Wait for the search to complete and fetch all results
5. Generate `M365_Audit_Report.xlsx`
6. Email the report to the configured recipient

**Note:** Purview audit searches take 1–2.5 hours to complete on Microsoft's servers. Run the tool in the evening or overnight for best results.

## Architecture

```
audit_final.py      # Core logic — data processing and report generation
audit_gui.py        # tkinter GUI wrapper with real-time log streaming
data_fetcher.py     # API layer — authenticates and pulls all three data sources
.env                # Credentials (excluded from git)
.env.example        # Template showing required environment variables
.gitignore          # Prevents sensitive files from being committed
TOOL_GUIDE.md       # End-user instructions
```

### Data flow

1. **data_fetcher.py** authenticates via OAuth 2.0 client credentials flow
2. **Graph Reports API** → Office 365 Active User Detail + SharePoint Site Usage Detail
3. **Purview Audit Search API** → SharePoint file activity logs (paginated, handles token refresh automatically)
4. **audit_final.py** normalizes and merges all three sources on user email (UPN)
5. **openpyxl** formats and outputs the final Excel report
6. **Graph sendMail API** → emails the report as an attachment

### Key engineering decisions

- **Monthly chunking:** Purview times out on large date ranges. The tool searches in monthly intervals and polls all searches simultaneously, reducing wait time to the duration of the slowest single search.
- **Parallel polling with timeout:** All Purview searches are polled simultaneously every 30 seconds. A 3-hour hard timeout prevents the tool from running indefinitely if Microsoft's servers are unresponsive.
- **Automatic token refresh:** Microsoft Graph access tokens expire after 1 hour. The tool detects 401 errors and re-authenticates automatically without interrupting long-running searches.
- **Pagination:** The Purview API returns results in pages of 150 records. The tool fetches all pages automatically, bypassing the 50,000-row cap of manual CSV exports.
- **Retry logic:** 429 (rate limit) and 504 (server timeout) errors are caught and retried automatically with a delay.
- **Graceful empty handling:** If Purview returns 0 records (due to timeout or no activity), the report still generates with licensing and storage data intact.

## Known Limitations

- Purview audit searches are processed on Microsoft's servers and can take 1–2.5 hours. On rare occasions, searches may not complete within the 3-hour timeout, resulting in an empty File Activity Log tab. Re-running the tool usually resolves this.
- File size data is not available for all Purview operation types (`FileSyncUploadedFull`, `FileRenamed`, etc.). Blank file size cells in the activity log are a Microsoft platform limitation.
- The Purview Audit Search API is currently on the `/beta` endpoint and is subject to change by Microsoft.

## Security Notes

- No API keys or credentials in this repository
- All data files are excluded via `.gitignore`
- `.env` file is excluded from version control
- Each user should create their own client secret under the shared app registration in Entra ID

## Extra Mile To Accommodate Non-Technical Staff

- Standalone `.exe` packaging via PyInstaller
- Windows Task Scheduler integration for monthly automated runs

## Author

Travis Farmer — CS Student @ Georgia State University | IT Intern @ Axion BioSystems

# M365 SharePoint Audit Tool — User Guide

## What This Tool Does

This tool automatically pulls data from Microsoft 365 via API and generates a single Excel report with three tabs:

- **User Summary** — shows every licensed user, how many files they've uploaded, modified, and deleted on SharePoint, and their total upload volume over the past 30 days
- **File Activity Log** — a detailed log of every file upload, modification, deletion, move, and rename across SharePoint over the past 30 days
- **All Licensed Users** — shows every user's Microsoft 365 license assignments for SharePoint and Teams, along with their last activity dates

No manual exports required. The tool pulls everything automatically and emails the report when complete.

---

## One-Time Setup

### 1. Install Python

Download from https://www.python.org/downloads/ and install Python 3.10 or higher.
During installation, check **"Add Python to environment variables"**.

### 2. Install required libraries

Open a terminal and run:
```
python -m pip install pandas openpyxl requests python-dotenv
```

### 3. Create your credentials file

Copy `.env.example` to a new file called `.env` in the same folder as the tool and fill in your values:

```
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
SENDER_EMAIL=it@yourcompany.com
RECIPIENT_EMAIL=recipient@yourcompany.com
```

Your IT administrator can provide the Tenant ID, Client ID, and a Client Secret from the app registration in Microsoft Entra ID. Each person running the tool should have their own Client Secret.

---

## How to Run the Tool

**Option 1 — GUI (recommended, no terminal needed):**

Double-click `audit_gui.exe` if you have the packaged version, or run:
```
python audit_gui.py
```

Click **Generate Report**. The tool will show live progress in the log window and email the report automatically when done.

**Option 2 — Command line:**
```
python audit_final.py
```

The tool will print its progress as it runs:
```
Authenticating...
Authentication successful!

Fetching M365 reports...
  Fetched getOffice365ActiveUserDetail: 271 rows
  Fetched getSharePointSiteUsageDetail: 222 rows

Fetching Purview audit logs (monthly intervals)...
  Created search: Jun 07 - Jul 07 SharePoint
  Polling all searches simultaneously...
  ✓ 'Jun 07 - Jul 07 SharePoint' completed
  Fetching records...

Parsing API audit records...
Building User Summary tab...
Building Licensed Users tab...
Writing report...
Formatting...

Done! Report saved to: M365_Audit_Report.xlsx

Sending report to recipient@yourcompany.com...
Report sent successfully.
```

The tool typically takes **1–2.5 hours** to complete due to the time required for Purview audit log searches to process on Microsoft's servers. **Run it in the evening or overnight for best results** — Microsoft's servers process searches faster during off-peak hours.

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
| Files Uploaded | Number of files they uploaded in the past 30 days |
| Files Modified | Number of files they modified in the past 30 days |
| Files Deleted | Number of files they deleted in the past 30 days |
| Total Actions | Total file operations (uploads + modifications + deletions + moves + renames) |
| Total Upload Volume (MB) | Total size of files they uploaded/modified, in megabytes |
| Sites Owned | Number of SharePoint sites they own |
| SharePoint Storage (GB) | Storage consumed by sites they own |
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

## Troubleshooting

**"Python was not found"**
Python is not on your PATH. Reinstall Python and check "Add Python to environment variables" during setup.

**"No module named 'pandas'" or similar**
Run `python -m pip install pandas openpyxl requests python-dotenv` to install the required libraries.

**"Authentication failed"**
Your credentials in the `.env` file are incorrect or the Client Secret has expired. Check the values and contact your administrator to generate a new secret if needed.

**"ERROR: Failed to fetch report"**
The API permissions may not be granted. Contact your administrator to confirm `Reports.Read.All`, `AuditLogsQuery.Read.All`, and `Mail.Send` have admin consent in Entra ID.

**File Activity Log tab is empty**
The Purview search timed out after 3 hours without completing. This is a Microsoft server-side issue. Re-run the tool, preferably in the evening or overnight when servers are less loaded. The rest of the report (User Summary and All Licensed Users) is still accurate.

**Blank file sizes in the activity log**
This is a Microsoft limitation. Purview does not include file size data for all operation types. File sizes are most consistently available for FileUploaded and FileModified actions.

**Tool takes longer than expected**
Purview audit log searches run on Microsoft's servers and typically take 1–2 hours. This is normal. Do not close the terminal or let the computer sleep while the tool is running. For best results, run it after business hours.

**Email not received**
Check that `SENDER_EMAIL` and `RECIPIENT_EMAIL` are correctly set in your `.env` file. Confirm the `Mail.Send` permission has admin consent in Entra ID. Check your spam folder.

---

## Credentials — For New Users

If you need to run this tool and don't have a `.env` file:

1. Go to **entra.microsoft.com** → App registrations → Licensing and SharePoint Audit Tool
2. Under **Certificates & secrets**, click **New client secret**
3. Give it a description and set expiration to 24 months
4. Copy the **Value** immediately — it only shows once
5. Create a `.env` file using `.env.example` as a template
6. The Tenant ID and Client ID are visible on the app registration overview page

---

## Permissions Required

The app registration requires the following Microsoft Graph application permissions with admin consent:

- `Reports.Read.All` — reads M365 usage reports
- `AuditLogsQuery.Read.All` — searches Purview audit logs
- `Mail.Send` — sends the report via email

Contact your Entra ID administrator if these are not already configured.

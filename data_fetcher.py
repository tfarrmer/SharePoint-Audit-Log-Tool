#Import and credentials setup
import os # lets Python interact with the operating system. 
import base64 # used to encode the Excel file into text before attaching it to an email. Email APIs can't send raw binary files, so you convert them to base64 text first
import time #gives access to time.sleep() which pauses the script for a set number of seconds. Used when waiting between retries and polling
import requests #the library that makes HTTP requests to Microsoft's API. Without this, the script can't talk to the internet
import pandas as pd #data manipulation library. Used to turn CSV responses from the API into DataFrames
from io import StringIO #lets you treat a string of text as if it were a file. Microsoft's reports API returns CSV text, and pandas needs a file-like object to read it
from datetime import datetime, timedelta, timezone #datetime handles dates and times, timedelta calculates time differences (like "30 days ago"), timezone ensures dates are in UTC format which Microsoft requires
from dotenv import load_dotenv #reads your .env file and loads the credentials into the environment

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

GRAPH_BASE = "https://graph.microsoft.com" # a constant string storing the base URL for all Microsoft Graph API calls. Defined once so you never hardcode the URL in multiple places
_current_token = None


#Authentication function, sends credentials to get an access token and if fails, it prints the error message and exits.
def get_access_token():
    response = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
    )
    if response.status_code != 200: #an integer representing the HTTP response code. 200 means success, anything else means failure
        print(f"ERROR: Authentication failed ({response.status_code})")
        print(response.json().get("error_description", ""))
        exit(1)
    return response.json()["access_token"]


def _api(method, url, **kwargs): #Helper function. It wraps every API call so you don't repeat authentication logic everywhere
    """Make an authenticated API request, refreshing the token once on 401."""
    global _current_token
    if _current_token is None:
        _current_token = get_access_token()
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {_current_token}"
    response = getattr(requests, method)(url, headers=headers, **kwargs)
    if response.status_code == 401: #401 means Unauthorized. The token expired. Get a new one and retry once
        print("  Token expired, refreshing...")
        _current_token = get_access_token()
        headers["Authorization"] = f"Bearer {_current_token}"
        response = getattr(requests, method)(url, headers=headers, **kwargs)
    return response


#Report function: gives a report name and it calls the Graph API, gets back CSV text, and converts it to a pandas DataFrame
def fetch_report(token, report_name, period="D180"):
    url = f"{GRAPH_BASE}/v1.0/reports/{report_name}(period='{period}')"

    response = _api("get", url)

    if response.status_code != 200:
        print(f"ERROR: Failed to fetch {report_name} ({response.status_code})")
        print(response.text[:500])
        return None
#graph reports api turns csv text
    csv_data = response.text
    if csv_data.startswith("\ufeff"):
        csv_data = csv_data[1:]

    df = pd.read_csv(StringIO(csv_data))
    print(f"  Fetched {report_name}: {len(df)} rows")
    return df

def fetch_active_user_detail(token):
    return fetch_report(token, "getOffice365ActiveUserDetail")

def fetch_sharepoint_site_usage(token):
    return fetch_report(token, "getSharePointSiteUsageDetail")


#Purview Audit Logs
def create_audit_search(token, start_date, end_date, search_name):
    """Create a Purview audit log search query."""
    url = f"{GRAPH_BASE}/beta/security/auditLog/queries"
    body = {
        "displayName": search_name,
        "filterStartDateTime": start_date.strftime("%Y-%m-%dT00:00:00Z"),
        "filterEndDateTime": end_date.strftime("%Y-%m-%dT00:00:00Z"),
        "recordTypeFilters": ["sharePointFileOperation"],
        "operationFilters": [
            "FileUploaded", "FileModified", "FileModifiedExtended",
            "FileDeleted", "FileDeletedFirstStageRecycleBin", "FileRecycled",
            "FileMoved", "FileRenamed", "FileCopied",
            "FileSyncUploadedFull", "FileVersionsAllDeleted"
        ]
    }

    for attempt in range(3): #tries up to 3 times
        response = _api("post", url, headers={"Content-Type": "application/json"}, json=body)
        if response.status_code in (429, 504): #429 means rate limited, 504 means server timeout
            print(f"  Rate limited or timeout ({response.status_code}), retrying in 60s... (attempt {attempt + 1}/3)")
            time.sleep(60) #pauses 60 seconds before retrying
            continue
        break

    if response.status_code in (200, 201): #200 means OK, 201 means Created. Both indicate success
        query = response.json()
        print(f"  Created search: {search_name} (ID: {query['id']})")
        return query["id"]
    else:
        print(f"  ERROR: Failed to create search '{search_name}' ({response.status_code})")
        print(f"  {response.text[:500]}")
        return None
    

def poll_audit_search(token, query_id, search_name, poll_interval=30, max_wait=10800): #checks every 30 seconds and will give up after 3 hours by default
    """Poll a Purview audit search until it completes."""
    url = f"{GRAPH_BASE}/beta/security/auditLog/queries/{query_id}"

    elapsed = 0
    while elapsed < max_wait: #keeps it running as long as we have exceeded 10800 seconds (3 hours)
        response = _api("get", url)
        if response.status_code != 200:
            print(f"  ERROR: Failed to check status for '{search_name}' ({response.status_code})")
            return False

        status = response.json().get("status", "") #safely gets the status field from the response. If status doesn't exist, returns an empty string "" instead of crashing

        if status == "succeeded":
            print(f"  Search '{search_name}' completed")
            return True
        elif status in ("failed", "cancelled"):
            print(f"  Search '{search_name}' {status}")
            return False
        else:
            print(f"  Search '{search_name}' status: {status} (waiting {poll_interval}s...)")
            time.sleep(poll_interval)
            elapsed += poll_interval

    print(f"  Search '{search_name}' timed out after {max_wait}s")
    return False



def fetch_audit_records(token, query_id, search_name):
    """Fetch all records from a completed audit search."""
    url = f"{GRAPH_BASE}/beta/security/auditLog/queries/{query_id}/records"

    all_records = [] #an empty list that accumulates all records across pages
    page = 1

    while url:
        response = _api("get", url)
        if response.status_code in (429, 504):
            print(f"  ERROR: {response.status_code} on page {page}, retrying in 30s...")
            time.sleep(30)
            continue
        if response.status_code != 200:
            print(f"  ERROR: Failed to fetch records for '{search_name}' ({response.status_code})")
            print(f"  {response.text[:500]}")
            break

        data = response.json()
        records = data.get("value", [])
        all_records.extend(records)
        print(f"  Page {page}: fetched {len(records)} records (total: {len(all_records)})")

        url = data.get("@odata.nextLink", None)
        page += 1

    print(f"  Total records for '{search_name}': {len(all_records)}")
    return all_records



def fetch_purview_audit_logs(token, months_back=1):
    """Run monthly audit searches and combine all results."""
    print("\nFetching Purview audit logs (monthly intervals)...")

    end_date = datetime.now(tz=timezone.utc)
    all_records = []
# create the monthly searches
    searches = []
    for i in range(months_back):
        month_end = end_date - timedelta(days=30 * i)
        month_start = end_date - timedelta(days=30 * (i + 1))
        search_name = f"{month_start.strftime('%b %d')} - {month_end.strftime('%b %d')} SharePoint"

        query_id = create_audit_search(token, month_start, month_end, search_name)
        if query_id:
            searches.append((query_id, search_name))
        time.sleep(15) #waits 15 seconds between creating searches to avoid rate limiting

    if not searches:
        print("ERROR: No audit searches were created successfully.")
        return []

    # Poll all searches in parallel — check each one every 30s until all complete
    print("\n  Polling all searches simultaneously...")
    pending = list(searches)
    completed = []

    while pending:
        still_pending = []
        for query_id, search_name in pending:
            url = f"{GRAPH_BASE}/beta/security/auditLog/queries/{query_id}"
            response = _api("get", url)

            if response.status_code != 200:
                print(f"  ERROR: Failed to check '{search_name}' ({response.status_code})")
                still_pending.append((query_id, search_name))
                continue

            status = response.json().get("status", "")

            if status == "succeeded":
                print(f"  ✓ '{search_name}' completed")
                completed.append((query_id, search_name))
            elif status in ("failed", "cancelled"):
                print(f"  ✗ '{search_name}' {status} — skipping")
            else:
                print(f"  '{search_name}' status: {status}")
                still_pending.append((query_id, search_name))

        pending = still_pending
        if pending:
            print(f"  {len(pending)} searches still running — waiting 30s...")
            time.sleep(30)

    # Fetch results from all completed searches
    for query_id, search_name in completed:
        print(f"\n  Fetching records for '{search_name}'...")
        records = fetch_audit_records(token, query_id, search_name)
        all_records.extend(records)

    print(f"\nTotal Purview records fetched: {len(all_records)}")
    return all_records


def send_report_email(report_path):
    """Email the finished report via Microsoft Graph sendMail. Returns True on success."""
    sender = SENDER_EMAIL
    recipient = RECIPIENT_EMAIL

    if not sender or not recipient:
        print("ERROR: SENDER_EMAIL and RECIPIENT_EMAIL must be set in .env to send the report.")
        return False

    print(f"Sending report to {recipient}...")

    try:
        with open(report_path, "rb") as f:
            content_bytes = base64.b64encode(f.read()).decode("utf-8")
    except OSError as exc:
        print(f"ERROR: Could not read report file: {exc}")
        return False

    subject = f"M365 SharePoint Audit Report — {datetime.now().strftime('%B %Y')}"
    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": "Please find attached the monthly M365 SharePoint audit report.",
            },
            "toRecipients": [{"emailAddress": {"address": recipient}}],
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": "M365_Audit_Report.xlsx",
                    "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "contentBytes": content_bytes,
                }
            ],
        }
    }

    url = f"{GRAPH_BASE}/v1.0/users/{sender}/sendMail"
    response = _api("post", url, headers={"Content-Type": "application/json"}, json=payload)

    if response.status_code == 202: #202 means "Accepted." Microsoft uses 202 (not 200) for successful email sends
        print("Report sent successfully.")
        return True

    print(f"ERROR: Failed to send email ({response.status_code})")
    print(response.text[:500])
    return False


#fetch everything
def fetch_all():
    """Authenticate and fetch all three data sources."""
    print("Authenticating...")
    token = get_access_token()
    print("Authentication successful!\n")

    print("Fetching M365 reports...")
    services = fetch_active_user_detail(token)
    sp_storage = fetch_sharepoint_site_usage(token)

    if services is None or sp_storage is None:
        print("ERROR: Failed to fetch one or more reports.")
        exit(1)

    audit_records = fetch_purview_audit_logs(token)

    return services, sp_storage, audit_records

if __name__ == "__main__":
    services, sp_storage, audit_records = fetch_all()
    print(f"\n=== Summary ===")
    print(f"Active User Detail: {len(services)} rows")
    print(f"SharePoint Site Usage: {len(sp_storage)} rows")
    print(f"Purview Audit Records: {len(audit_records)} records")
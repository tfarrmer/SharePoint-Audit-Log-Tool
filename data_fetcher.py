#Import and credentials setup
import os
import time
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

GRAPH_BASE = "https://graph.microsoft.com"
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
    if response.status_code != 200:
        print(f"ERROR: Authentication failed ({response.status_code})")
        print(response.json().get("error_description", ""))
        exit(1)
    return response.json()["access_token"]


def _api(method, url, **kwargs):
    """Make an authenticated API request, refreshing the token once on 401."""
    global _current_token
    if _current_token is None:
        _current_token = get_access_token()
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {_current_token}"
    response = getattr(requests, method)(url, headers=headers, **kwargs)
    if response.status_code == 401:
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

    response = _api("post", url, headers={"Content-Type": "application/json"}, json=body)

    if response.status_code in (200, 201):
        query = response.json()
        print(f"  Created search: {search_name} (ID: {query['id']})")
        return query["id"]
    else:
        print(f"  ERROR: Failed to create search '{search_name}' ({response.status_code})")
        print(f"  {response.text[:500]}")
        return None
    

def poll_audit_search(token, query_id, search_name, poll_interval=30, max_wait=10800):
    """Poll a Purview audit search until it completes."""
    url = f"{GRAPH_BASE}/beta/security/auditLog/queries/{query_id}"

    elapsed = 0
    while elapsed < max_wait:
        response = _api("get", url)
        if response.status_code != 200:
            print(f"  ERROR: Failed to check status for '{search_name}' ({response.status_code})")
            return False

        status = response.json().get("status", "")

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

    all_records = []
    page = 1

    while url:
        response = _api("get", url)
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



def fetch_purview_audit_logs(token, months_back=6):
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
        time.sleep(15)

    if not searches:
        print("ERROR: No audit searches were created successfully.")
        return []

    for query_id, search_name in searches:
        print(f"\n  Waiting for '{search_name}'...")
        success = poll_audit_search(token, query_id, search_name)
        if success:
            records = fetch_audit_records(token, query_id, search_name)
            all_records.extend(records)

    print(f"\nTotal Purview records fetched: {len(all_records)}")
    return all_records


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
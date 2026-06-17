#Import and credentials setup
import os
import time
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

GRAPH_BASE = "https://graph.microsoft.com"


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


#Report function: gives a report name and it calls the Graph API, gets back CSV text, and converts it to a pandas DataFrame
def fetch_report(token, report_name, period="D180"):
    url = f"{GRAPH_BASE}/v1.0/reports/{report_name}(period='{period}')"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)

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



def create_audit_search(token, start_date, end_date, search_name):
    """Create a Purview audit log search query."""
    url = f"{GRAPH_BASE}/beta/security/auditLog/queries"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
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

    response = requests.post(url, headers=headers, json=body)

    if response.status_code in (200, 201):
        query = response.json()
        print(f"  Created search: {search_name} (ID: {query['id']})")
        return query["id"]
    else:
        print(f"  ERROR: Failed to create search '{search_name}' ({response.status_code})")
        print(f"  {response.text[:500]}")
        return None
    

def poll_audit_search(token, query_id, search_name, poll_interval=30, max_wait=3600):
    """Poll a Purview audit search until it completes."""
    url = f"{GRAPH_BASE}/beta/security/auditLog/queries/{query_id}"
    headers = {"Authorization": f"Bearer {token}"}

    elapsed = 0
    while elapsed < max_wait:
        response = requests.get(url, headers=headers)
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
    headers = {"Authorization": f"Bearer {token}"}

    all_records = []
    page = 1

    while url:
        response = requests.get(url, headers=headers)
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
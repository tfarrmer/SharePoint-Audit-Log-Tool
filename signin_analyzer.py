import os
import requests
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

Tenant_ID = os.getenv("TENANT_ID")
SIGNIN_CLIENT_ID = os.getenv("SIGNIN_CLIENT_ID")
SIGNIN_CLIENT_SECRET = os.getenv("SIGNIN_CLIENT_SECRET")

Graph_Base = "https://graph.microsoft.com"

def get_signin_access_token():
    #Authenticate the signin monitoring app registration
    response = requests.post(
        f"https://login.microsoftonline.com/{Tenant_ID}/oauth2/v2.0/token",
        data={
            "client_id": SIGNIN_CLIENT_ID,
            "client_secret": SIGNIN_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
    )
    if response.status_code != 200:
        print(f"ERROR: Authentication failed ({response.status_code})")
        print(response.json().get("error_description", ""))
        return None
    return response.json()["access_token"]


def fetch_signin_logs(months_back=1):
    #Pulls sign-in logs for the given number of months back, handles pagination and retries
    token = get_signin_access_token()
    if not token:
        print("ERROR: Could not authenticate. Aborting sign-in log fetch.")
        return []

    end_date = datetime.now(tz=timezone.utc)
    start_date = end_date - timedelta(days=30 * months_back)

    filter_str = (
        f"createdDateTime ge {start_date.strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"and createdDateTime le {end_date.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )
    url = f"{Graph_Base}/v1.0/auditLogs/signIns?$filter={filter_str}&$top=999"

    all_records = []
    page = 1
    connection_retries = 0
    max_connection_retries = 5

    headers = {"Authorization": f"Bearer {token}"}

    while url:
        try:
            response = requests.get(url, headers=headers)
        except requests.exceptions.RequestException as exc:
            connection_retries += 1
            if connection_retries > max_connection_retries:
                print(f"ERROR: Connection failed {max_connection_retries} times on page {page}, giving up: {exc}")
                break
            print(f"Connection error on page {page}, retrying in 30s... (attempt {connection_retries}/{max_connection_retries})")
            time.sleep(30)
            continue

        connection_retries = 0

        if response.status_code in (429, 502, 503, 504):
            print(f"{response.status_code} on page {page}, retrying in 30s...")
            time.sleep(30)
            continue
        if response.status_code != 200:
            print(f"ERROR: Failed to fetch sign-in logs ({response.status_code})")
            print(response.text[:500])
            break

        data = response.json()
        records = data.get("value", [])
        all_records.extend(records)
        print(f"Page {page}: fetched {len(records)} records (total: {len(all_records)})")

        url = data.get("@odata.nextLink", None)
        page += 1

    print(f"Total sign-in records fetched: {len(all_records)}")
    return all_records


if __name__ == "__main__":
    records = fetch_signin_logs(months_back=1)
    print(f"\nDone. {len(records)} total records ready for analysis.")
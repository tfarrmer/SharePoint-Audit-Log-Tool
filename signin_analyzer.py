import os
import requests
import time
from collections import defaultdict
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

Tenant_ID = os.getenv("TENANT_ID")
SIGNIN_CLIENT_ID = os.getenv("SIGNIN_CLIENT_ID")
SIGNIN_CLIENT_SECRET = os.getenv("SIGNIN_CLIENT_SECRET")

LOCATION_GROUP_US = os.getenv("LOCATION_GROUP_US_ID")
LOCATION_GROUP_UK = os.getenv("LOCATION_GROUP_UK_ID")
LOCATION_GROUP_EH = os.getenv("LOCATION_GROUP_EH_ID")

LOCATION_GROUPS = {
    LOCATION_GROUP_US: "US",
    LOCATION_GROUP_UK: "GB",
    LOCATION_GROUP_EH: "NL",
}

Graph_Base = "https://graph.microsoft.com"

# Detection thresholds — see scope doc for justification
CREDENTIAL_FAILURE_CODE = 50126  # Invalid username or password

BRUTE_FORCE_THRESHOLD = 10
BRUTE_FORCE_WINDOW_MINUTES = 10

SPRAY_MIN_ACCOUNTS = 5
SPRAY_MAX_ATTEMPTS_PER_ACCOUNT = 3
SPRAY_WINDOW_MINUTES = 60


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


def _parse_timestamp(record):
    #Converts Microsoft's timestamp format into a real datetime object
    return datetime.fromisoformat(record.get("createdDateTime").replace("Z", "+00:00"))


def detect_brute_force(records):
    #Groups failed sign-ins by user, checks for 10+ failures in any 10-minute sliding window
    by_user = defaultdict(list)

    for r in records:
        error_code = r.get("status", {}).get("errorCode")
        if error_code == CREDENTIAL_FAILURE_CODE:
            upn = r.get("userPrincipalName", "unknown")
            by_user[upn].append(_parse_timestamp(r))

    flags = []
    window = timedelta(minutes=BRUTE_FORCE_WINDOW_MINUTES)

    for upn, timestamps in by_user.items():
        timestamps = sorted(timestamps)
        for i in range(len(timestamps)):
            window_end = timestamps[i] + window
            count_in_window = sum(1 for t in timestamps[i:] if t <= window_end)
            if count_in_window >= BRUTE_FORCE_THRESHOLD:
                flags.append({
                    "User": upn,
                    "Failed Attempts": count_in_window,
                    "Window Start": timestamps[i],
                    "Window End": window_end,
                })
                break

    return flags





# ============================================================
# TEMPORARY TEST BLOCK — for development only.
# This will be replaced later with proper Excel report output,
# same pattern as run_audit() in the existing tool.
# ============================================================
if __name__ == "__main__":
    records = fetch_signin_logs(months_back=1)
    print(f"\nDone. {len(records)} total records ready for analysis.")

    brute_force_flags = detect_brute_force(records)
    spray_flags = detect_password_spray(records)

    print(f"\nBrute force flags: {len(brute_force_flags)}")
    for f in brute_force_flags:
        print(f"  {f}")

    print(f"\nPassword spray flags: {len(spray_flags)}")
    for f in spray_flags:
        print(f"  {f}")
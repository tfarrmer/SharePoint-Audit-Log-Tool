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
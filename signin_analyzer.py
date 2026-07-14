import os
import requests
from dotenv import load_dotenv

load_dotenv()

Tenant_ID = os.getenv("TENANT_ID")
SIGNIN_CLIENT_ID = os.getenv("SIGNIN_CLIENT_ID")
SIGNIN_CLIENT_SECRET = os.getenv("SIGNIN_CLIENT_SECRET")

Graph_Base = "https://graph.microsoft.com"

def get_signin_access_token():
    #Authenticcate the signin monitoring app registration 
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

if __name__ == "__main__":
    token = get_signin_access_token()
    if token:
        print("Successfuly obtained a token.")
        print(f"First 20 characters: {token[:20]}...")
    else:
        print("Failed to obtain a token.")
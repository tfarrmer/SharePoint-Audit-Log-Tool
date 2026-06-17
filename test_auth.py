import os
import requests
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Get access token
token_response = requests.post(
    f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
    data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
)

if token_response.status_code == 200:
    print("Authentication successful!")
    token = token_response.json()["access_token"]
    print(f"Token starts with: {token[:20]}...")
else:
    print(f"Authentication failed: {token_response.status_code}")
    print(token_response.json())
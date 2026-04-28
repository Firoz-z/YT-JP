"""
Run this ONCE locally to obtain your YouTube OAuth refresh token
for the JAPANESE channel.

Steps:
  1. Make sure you're signed into the JAPANESE YouTube channel's Google account
  2. Go to https://console.cloud.google.com/
  3. Use a project with "YouTube Data API v3" enabled
  4. Credentials → Create OAuth client ID → Desktop app
  5. Download the JSON and save as  client_secret.json  in this folder
  6. Run:  python setup_oauth.py
  7. Browser opens — sign in with your JAPANESE channel's Google account
  8. Copy the three values printed at the end into GitHub Secrets
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

print("\n=== Add these three values to GitHub → Settings → Secrets ===\n")
print(f"YOUTUBE_CLIENT_ID={creds.client_id}")
print(f"YOUTUBE_CLIENT_SECRET={creds.client_secret}")
print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
print("\nDone — you can delete client_secret.json now.\n")

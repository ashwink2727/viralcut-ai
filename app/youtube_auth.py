
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Project folders
PROJECT_DIR = Path(__file__).resolve().parent.parent

CLIENT_SECRET_FILE = PROJECT_DIR / "youtube_client_secret.json"
TOKEN_FILE = PROJECT_DIR / "youtube_token.json"

# Read-only access to the user's YouTube account
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]


def get_youtube_service():
    """Authorize the user and return a YouTube API service."""

    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError(
            f"OAuth credentials not found: {CLIENT_SECRET_FILE}"
        )

    credentials = None

    # Reuse an existing login if available
    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    # Refresh or request authorization
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    elif not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE), SCOPES
        )

        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            open_browser=True
        )

    # Save authorization for future runs
    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=credentials)


def get_active_live_stream(youtube):
    """Find the user's currently active YouTube live broadcast."""

    response = youtube.liveBroadcasts().list(
        part="id,snippet,contentDetails",
        broadcastStatus="active",
    ).execute()

    broadcasts = response.get("items", [])

    if not broadcasts:
        return None

    broadcast = broadcasts[0]

    return {
        "video_id": broadcast["id"],
        "title": broadcast["snippet"]["title"],
        "live_chat_id": broadcast.get(
            "snippet", {}
        ).get("liveChatId")
    }


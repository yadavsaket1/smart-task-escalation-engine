"""
Gmail Service
─────────────
Sends real emails via Gmail API using OAuth2.

First run:
  A browser window opens for Google sign-in.
  After login, token.pickle is saved and reused for all future sends.

Email format:  firstname.lastname.powerweave@yopmail.com
Credentials:   Set GMAIL_CREDENTIALS_PATH in .env
"""

import os
import pickle
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("gmail_service")

# Gmail OAuth scopes — send only, no read access needed
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _get_credentials():
    """
    Loads or refreshes OAuth2 credentials.
    Opens browser on first run for Google login.
    Saves token.pickle for subsequent runs.
    Returns credentials object or None on failure.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        logger.error("Google API packages not installed. Run: pip install -r requirements.txt")
        return None

    creds = None
    token_path = "token.pickle"
    credentials_path = os.getenv(
        "GMAIL_CREDENTIALS_PATH",
        "client_secret_101723841283-2v9k975bu43ba2v9glhok8hu8dj2tu8i.apps.googleusercontent.com.json"
    )

    # Load existing token if present
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    # Refresh or re-authenticate if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}. Re-authenticating...")
                creds = None

        if not creds:
            if not os.path.exists(credentials_path):
                logger.error(
                    f"Gmail credentials file not found: {credentials_path}\n"
                    f"Download it from Google Cloud Console → APIs & Services → Credentials."
                )
                return None

            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save for next run
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    return creds


def _build_service():
    """Builds and returns the Gmail API service client."""
    try:
        from googleapiclient.discovery import build
        creds = _get_credentials()
        if not creds:
            return None
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error(f"Failed to build Gmail service: {e}")
        return None


def name_to_email(full_name: str) -> str:
    """
    Converts a full name to Powerweave yopmail address.

    Examples:
      "Vikram Nair"   → "vikram.nair.powerweave@yopmail.com"
      "Arjun Kapoor"  → "arjun.kapoor.powerweave@yopmail.com"
    """
    parts = full_name.strip().lower().split()
    return ".".join(parts) + ".powerweave@yopmail.com"


def send_email(to_name: str, subject: str, body: str) -> dict:
    """
    Sends a real email via Gmail API.

    Args:
        to_name:  Recipient's full name (email derived as name.surname.powerweave@yopmail.com)
        subject:  Email subject line
        body:     Plain text email body

    Returns:
        dict with keys: success (bool), email (str), error (str or None)
    """
    to_email = name_to_email(to_name)
    result   = {"success": False, "email": to_email, "error": None}

    # Simulation mode — skip real send, log only
    if os.getenv("GMAIL_SIMULATION_MODE", "false").lower() == "true":
        logger.info(f"[SIMULATION] Email to {to_email} | Subject: {subject}")
        result["success"] = True
        result["error"]   = "simulation mode"
        return result

    try:
        service = _build_service()
        if not service:
            result["error"] = "Gmail service unavailable — check credentials"
            return result

        msg = MIMEMultipart()
        msg["to"]      = to_email
        msg["subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()

        logger.info(f"Email sent → {to_email} | {subject}")
        result["success"] = True

    except Exception as e:
        logger.error(f"Email send failed → {to_email}: {e}")
        result["error"] = str(e)

    return result

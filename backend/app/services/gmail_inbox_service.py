from __future__ import annotations

import base64
import json
import os
from email.message import EmailMessage as MimeEmailMessage
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.models.email_ops import EmailThread

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except Exception:  # pragma: no cover
    Request = None  # type: ignore
    Credentials = None  # type: ignore
    InstalledAppFlow = None  # type: ignore
    build = None  # type: ignore


DEFAULT_SECRET_DIR = Path.home() / ".openclaw" / "secrets"
DEFAULT_SECRET_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CLIENT_FILE = DEFAULT_SECRET_DIR / "gmail_oauth_client.json"
DEFAULT_TOKEN_FILE = DEFAULT_SECRET_DIR / "gmail_oauth_token.json"
DEFAULT_ACCOUNT_EMAIL = "neo512235@gmail.com"
DEFAULT_QUERY = "in:inbox"
DEFAULT_MAX_RESULTS = 50


class GmailInboxConfigurationError(RuntimeError):
    """Raised when Gmail inbox configuration is incomplete."""


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def gmail_drafts_enabled() -> bool:
    return _truthy(os.getenv("GOOGLE_GMAIL_ENABLE_DRAFTS"))


def gmail_send_enabled() -> bool:
    return _truthy(os.getenv("GOOGLE_GMAIL_ENABLE_SEND"))


def gmail_scopes() -> list[str]:
    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    if gmail_drafts_enabled():
        scopes.append("https://www.googleapis.com/auth/gmail.compose")
    if gmail_send_enabled():
        scopes.append("https://www.googleapis.com/auth/gmail.send")
    return scopes


def gmail_account_email() -> str:
    return (os.getenv("GOOGLE_GMAIL_ACCOUNT_EMAIL") or DEFAULT_ACCOUNT_EMAIL).strip()


def gmail_client_file_path() -> Path:
    raw = (os.getenv("GOOGLE_GMAIL_OAUTH_CLIENT_FILE") or "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_CLIENT_FILE


def gmail_token_file_path() -> Path:
    raw = (os.getenv("GOOGLE_GMAIL_OAUTH_TOKEN_FILE") or "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_TOKEN_FILE


def gmail_sync_query() -> str:
    return (os.getenv("GOOGLE_GMAIL_SYNC_QUERY") or DEFAULT_QUERY).strip() or DEFAULT_QUERY


def gmail_sync_max_results() -> int:
    raw = (os.getenv("GOOGLE_GMAIL_SYNC_MAX_RESULTS") or "").strip()
    if not raw:
        return DEFAULT_MAX_RESULTS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_RESULTS
    return max(1, min(100, value))


def _client_config_from_env_or_file() -> Optional[dict[str, Any]]:
    raw_json = (os.getenv("GOOGLE_GMAIL_OAUTH_CLIENT_JSON") or "").strip()
    if raw_json:
        return json.loads(raw_json)

    path = gmail_client_file_path()
    if path.exists():
        return json.loads(path.read_text())

    return None


def _token_payload_from_env_or_file() -> tuple[Optional[dict[str, Any]], Optional[str]]:
    raw_json = (os.getenv("GOOGLE_GMAIL_OAUTH_TOKEN_JSON") or "").strip()
    if raw_json:
        return json.loads(raw_json), "env"

    path = gmail_token_file_path()
    if path.exists():
        return json.loads(path.read_text()), "file"

    return None, None


def _save_token_payload(payload: dict[str, Any]) -> None:
    if (os.getenv("GOOGLE_GMAIL_OAUTH_TOKEN_JSON") or "").strip():
        return
    path = gmail_token_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _load_credentials() -> Credentials:
    if Credentials is None or Request is None:
        raise GmailInboxConfigurationError(
            "Google Gmail OAuth dependencies are unavailable. Install google-auth-oauthlib and google-auth-httplib2."
        )

    scopes = gmail_scopes()
    token_payload, token_source = _token_payload_from_env_or_file()
    if token_payload is None:
        raise GmailInboxConfigurationError(
            "Gmail token not found. Set GOOGLE_GMAIL_OAUTH_TOKEN_JSON or "
            f"place the OAuth token JSON at {gmail_token_file_path()}."
        )

    creds = Credentials.from_authorized_user_info(token_payload, scopes)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if token_source == "file":
                _save_token_payload(json.loads(creds.to_json()))
        else:
            raise GmailInboxConfigurationError(
                "Stored Gmail token is invalid and cannot be refreshed. Re-run the Gmail connection script."
            )
    return creds


def gmail_connection_status() -> dict[str, Any]:
    client_path = gmail_client_file_path()
    token_path = gmail_token_file_path()
    client_config = None
    token_payload = None
    client_error = None

    try:
        client_config = _client_config_from_env_or_file()
    except Exception as exc:  # pragma: no cover
        client_error = str(exc)

    token_error = None
    try:
        token_payload, _ = _token_payload_from_env_or_file()
    except Exception as exc:  # pragma: no cover
        token_error = str(exc)

    configured = client_config is not None
    token_present = token_payload is not None
    connected = False
    refreshable = False
    error = client_error or token_error

    if token_present and Credentials is not None:
        try:
            creds = Credentials.from_authorized_user_info(token_payload or {}, gmail_scopes())
            refreshable = bool(creds.refresh_token)
            connected = bool(creds.valid or creds.refresh_token)
        except Exception as exc:  # pragma: no cover
            error = str(exc)

    dependencies_ready = all(dependency is not None for dependency in (Request, Credentials, InstalledAppFlow, build))

    return {
        "configured": configured,
        "connected": connected and configured and dependencies_ready,
        "dependencies_ready": dependencies_ready,
        "drafts_enabled": gmail_drafts_enabled(),
        "send_enabled": gmail_send_enabled(),
        "account_email": gmail_account_email(),
        "client_file": str(client_path),
        "token_file": str(token_path),
        "token_present": token_present,
        "refreshable": refreshable,
        "sync_query": gmail_sync_query(),
        "max_results": gmail_sync_max_results(),
        "scopes": gmail_scopes(),
        "error": error,
    }


def authorize_gmail_account(open_browser: bool = True, port: int = 0) -> dict[str, Any]:
    if InstalledAppFlow is None:
        raise GmailInboxConfigurationError(
            "Google Gmail OAuth dependencies are unavailable. Install google-auth-oauthlib and google-auth-httplib2."
        )

    client_config = _client_config_from_env_or_file()
    if client_config is None:
        raise GmailInboxConfigurationError(
            "Gmail OAuth client configuration not found. Set GOOGLE_GMAIL_OAUTH_CLIENT_JSON or "
            f"place the OAuth client JSON at {gmail_client_file_path()}."
        )

    flow = InstalledAppFlow.from_client_config(client_config, gmail_scopes())
    creds = flow.run_local_server(
        host="localhost",
        port=port,
        open_browser=open_browser,
        authorization_prompt_message="Open this URL in your browser to authorize Gmail access: {url}",
        success_message="Gmail authorization complete. You can close this window.",
        access_type="offline",
        prompt="consent",
    )
    _save_token_payload(json.loads(creds.to_json()))
    return gmail_connection_status()


def fetch_gmail_threads() -> list[dict[str, Any]]:
    if build is None:
        raise GmailInboxConfigurationError(
            "google-api-python-client is unavailable. Gmail fetch cannot run."
        )

    creds = _load_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    query = gmail_sync_query()
    max_results = gmail_sync_max_results()
    labels_response = service.users().labels().list(userId="me").execute()
    label_name_by_id = {
        str(item.get("id") or ""): str(item.get("name") or "").strip().lower()
        for item in (labels_response.get("labels", []) or [])
        if item.get("id") and item.get("name")
    }

    response = (
        service.users()
        .threads()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    thread_refs = response.get("threads", []) or []
    items: list[dict[str, Any]] = []
    for thread_ref in thread_refs:
        thread_id = thread_ref.get("id")
        if not thread_id:
            continue
        item = (
            service.users()
            .threads()
            .get(
                userId="me",
                id=thread_id,
                format="full",
            )
            .execute()
        )
        label_names: set[str] = set()
        for message in item.get("messages", []) or []:
            for label_id in message.get("labelIds", []) or []:
                label_name = label_name_by_id.get(str(label_id))
                if label_name:
                    label_names.add(label_name)
        item["_openclaw_label_names"] = sorted(label_names)
        items.append(item)
    return items


def save_gmail_draft(thread: "EmailThread", *, overwrite_existing: bool = True) -> dict[str, Any]:
    if build is None:
        raise GmailInboxConfigurationError("google-api-python-client is unavailable. Gmail draft save cannot run.")
    if not gmail_drafts_enabled():
        raise GmailInboxConfigurationError(
            "Gmail draft persistence is disabled. Enable GOOGLE_GMAIL_ENABLE_DRAFTS and reconnect the Gmail account with compose scope."
        )
    if thread.provider != "gmail":
        raise ValueError("Only Gmail-backed threads can be saved into Gmail Drafts.")
    if not thread.provider_thread_id:
        raise ValueError("Gmail thread id is missing for this thread.")
    if not thread.draft_body:
        raise ValueError("No draft body exists on this thread yet.")

    creds = _load_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw_message = _build_gmail_draft_message(thread)
    message_payload = {
        "raw": raw_message,
        "threadId": thread.provider_thread_id,
    }
    if thread.provider_draft_id and overwrite_existing:
        response = (
            service.users()
            .drafts()
            .update(
                userId="me",
                id=thread.provider_draft_id,
                body={
                    "id": thread.provider_draft_id,
                    "message": message_payload,
                },
            )
            .execute()
        )
        action = "updated"
    else:
        response = (
            service.users()
            .drafts()
            .create(
                userId="me",
                body={
                    "message": message_payload,
                },
            )
            .execute()
        )
        action = "created"

    message = response.get("message") or {}
    return {
        "action": action,
        "draft_id": str(response.get("id") or ""),
        "message_id": str(message.get("id") or ""),
        "thread_id": str(message.get("threadId") or thread.provider_thread_id or ""),
    }


def _build_gmail_draft_message(thread: "EmailThread") -> str:
    mime = MimeEmailMessage()
    mime["From"] = gmail_account_email()
    recipients = _draft_recipients(thread)
    if not recipients:
        raise ValueError("Could not determine a recipient address for this Gmail draft.")
    mime["To"] = ", ".join(recipients)
    mime["Subject"] = thread.draft_subject or f"Re: {thread.subject}"

    latest_inbound = _latest_inbound_message(thread)
    if latest_inbound and latest_inbound.internet_message_id:
        mime["In-Reply-To"] = latest_inbound.internet_message_id
    references = _references_header(latest_inbound)
    if references:
        mime["References"] = references

    mime.set_content(thread.draft_body or "")
    return base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8").rstrip("=")


def _latest_inbound_message(thread: "EmailThread"):
    inbound = [message for message in thread.messages if str(getattr(message, "direction", "inbound")) == "inbound"]
    if inbound:
        return max(inbound, key=lambda item: item.received_at)
    if thread.messages:
        return max(thread.messages, key=lambda item: item.received_at)
    return None


def _draft_recipients(thread: "EmailThread") -> list[str]:
    latest_inbound = _latest_inbound_message(thread)
    if latest_inbound and latest_inbound.from_address:
        return [latest_inbound.from_address]
    if thread.from_address:
        return [thread.from_address]
    return []


def _references_header(message) -> str:
    if message is None:
        return ""
    references = str(getattr(message, "references_header", "") or "").strip()
    internet_message_id = str(getattr(message, "internet_message_id", "") or "").strip()
    if references and internet_message_id and internet_message_id not in references:
        return f"{references} {internet_message_id}".strip()
    if references:
        return references
    return internet_message_id

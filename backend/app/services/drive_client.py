import io
import json
import os
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from PyPDF2 import PdfReader

from app.services.parsers import pptx_parser


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"


class DriveConfigurationError(RuntimeError):
    """Raised when the Google Drive client is not configured."""


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str


class GoogleDriveClient:
    def __init__(self) -> None:
        print("🔑 Building Drive credentials...", flush=True)
        self._credentials = self._build_credentials()
        print("✅ Credentials built, creating session...", flush=True)
        self._session = requests.Session()
        print("✅ Drive client initialized", flush=True)

    @staticmethod
    def _build_credentials():
        raw_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT")
        json_path = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE")

        if raw_json:
            info = json.loads(raw_json)
            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        if json_path:
            return service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)

        raise DriveConfigurationError(
            "Google Drive credentials not configured. Set GOOGLE_DRIVE_SERVICE_ACCOUNT or "
            "GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE."
        )

    def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self._credentials.valid:
            self._credentials.refresh(Request())
        return self._credentials.token

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated request to the Drive API."""
        url = f"{DRIVE_API_BASE}/{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._get_access_token()}"
        # Add timeout to prevent hanging (30 seconds for downloads, 10 for regular requests)
        timeout = kwargs.pop("timeout", 30 if kwargs.get("stream") else 10)
        response = self._session.request(method, url, headers=headers, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    def list_files(self, folder_id: str, page_size: int = 100) -> List[DriveFile]:
        try:
            params = {
                "q": f"'{folder_id}' in parents and trashed=false",
                "fields": "files(id, name, mimeType)",
                "pageSize": page_size,
            }
            response = self._make_request("GET", "files", params=params)
            data = response.json()
            files = data.get("files", [])
            return [DriveFile(id=file["id"], name=file["name"], mime_type=file["mimeType"]) for file in files]
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to list files from folder {folder_id}: {exc}") from exc

    def _download_file_to_bytes(self, file_id: str) -> bytes:
        """Download a file from Drive as bytes using the media endpoint."""
        print(f"  → Downloading file {file_id} from Drive...", flush=True)
        try:
            params = {"alt": "media"}
            # Use a longer timeout for file downloads (60 seconds)
            url = f"{DRIVE_API_BASE}/files/{file_id}"
            headers = {"Authorization": f"Bearer {self._get_access_token()}"}
            response = self._session.get(url, params=params, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            # Read content in chunks when streaming
            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
            print(f"  → Download complete, size: {len(content)} bytes", flush=True)
            return content
        except requests.Timeout as exc:
            print(f"  → ❌ Download timed out after 60 seconds", flush=True)
            raise RuntimeError(f"Download timed out for file {file_id}") from exc
        except requests.RequestException as exc:
            print(f"  → ❌ Download failed: {exc}", flush=True)
            raise RuntimeError(f"Failed to download file {file_id}: {exc}") from exc

    def _download_file_to_temp(self, file_id: str, suffix: str) -> tempfile.NamedTemporaryFile:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_file.write(self._download_file_to_bytes(file_id))
        tmp_file.flush()
        return tmp_file

    def _export_google_doc(self, file_id: str, mime_type: str = "text/plain") -> str:
        """Export a Google Doc/Slides file as text using the export endpoint."""
        try:
            params = {"mimeType": mime_type}
            response = self._make_request("GET", f"files/{file_id}/export", params=params)
            return response.text
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to export Google Doc {file_id}: {exc}") from exc

    def extract_text(self, file: DriveFile) -> str:
        mime_type = file.mime_type
        if mime_type in {
            "application/vnd.google-apps.document",
            "application/vnd.google-apps.presentation",
        }:
            return self._export_google_doc(file.id)

        if mime_type == "application/pdf" or file.name.lower().endswith(".pdf"):
            pdf_bytes = self._download_file_to_bytes(file.id)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        if mime_type in {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        }:
            tmp_file = self._download_file_to_temp(file.id, suffix=".pptx")
            try:
                return pptx_parser.extract_text_from_pptx(tmp_file.name)
            finally:
                tmp_file.close()
                os.unlink(tmp_file.name)

        if mime_type in {"text/plain"}:
            return self._download_file_to_bytes(file.id).decode("utf-8", errors="ignore")

        return ""


def get_drive_client() -> GoogleDriveClient:
    return GoogleDriveClient()

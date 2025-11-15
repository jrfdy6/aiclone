import io
import json
import os
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from PyPDF2 import PdfReader

from app.services.parsers import pptx_parser


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class DriveConfigurationError(RuntimeError):
    """Raised when the Google Drive client is not configured."""


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str


class GoogleDriveClient:
    def __init__(self) -> None:
        self._service = self._build_service()

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

    def _build_service(self):
        credentials = self._build_credentials()
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    def list_files(self, folder_id: str, page_size: int = 100) -> List[DriveFile]:
        try:
            response = (
                self._service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    fields="files(id, name, mimeType)",
                    pageSize=page_size,
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"Failed to list files from folder {folder_id}: {exc}") from exc

        files = response.get("files", [])
        return [DriveFile(id=file["id"], name=file["name"], mime_type=file["mimeType"]) for file in files]

    def _download_file_to_bytes(self, file_id: str) -> bytes:
        request = self._service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        return fh.read()

    def _download_file_to_temp(self, file_id: str, suffix: str) -> tempfile.NamedTemporaryFile:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_file.write(self._download_file_to_bytes(file_id))
        tmp_file.flush()
        return tmp_file

    def _export_google_doc(self, file_id: str, mime_type: str = "text/plain") -> str:
        try:
            exported = (
                self._service.files()
                .export(fileId=file_id, mimeType=mime_type)
                .execute()
            )
            return exported.decode("utf-8", errors="ignore")
        except HttpError as exc:
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

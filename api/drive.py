"""
api/drive.py — Google Drive & Docs integration (Andrii's module).

Implements ApiClientProtocol defined in core/orchestrator.py.
Uses OAuth 2.0 (installed-app flow) stored in token.json.
"""

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models import Employee, OrderType

# ─── OAuth scopes ─────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TOKEN_PATH = _PROJECT_ROOT / "token.json"
_CREDS_PATH = _PROJECT_ROOT / "client_secret_59362188699_09m2vh4m2o8698t40c74ofpd4sbb5ihd_apps.json"

# Fallback: підтримуємо також старий credentials.json
if not _CREDS_PATH.exists():
    _CREDS_PATH = _PROJECT_ROOT / "credentials.json"


# ─── Auth helper ──────────────────────────────────────────────────────────────

def _get_credentials() -> Credentials:
    """
    Load saved credentials from token.json, refresh if expired,
    or run the OAuth browser flow on the first launch.
    """
    creds: Credentials | None = None

    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _CREDS_PATH.exists():
                raise FileNotFoundError(
                    f"OAuth credentials file not found: {_CREDS_PATH}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Зберігаємо токен для наступних запусків
        with open(_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds


# ─── DriveClient ──────────────────────────────────────────────────────────────

class DriveClient:
    """
    Production implementation of ApiClientProtocol.

    Connects to Google Drive and Docs to:
    - discover HR order templates by order type
    - copy a template into an employee's Orders/ subdirectory
    - substitute {{markers}} with real employee data
    """

    def __init__(self) -> None:
        creds = _get_credentials()
        self._drive = build("drive", "v3", credentials=creds)
        self._docs  = build("docs",  "v1", credentials=creds)
        self._templates_folder_id = os.getenv("TEMPLATES_FOLDER_ID", "")

    # ── ApiClientProtocol ─────────────────────────────────────────────────────

    def get_templates(self) -> dict[str, str]:
        """
        Scan the Templates folder on Drive and return {order_type_value: file_id}.

        Matches by file name keyword (case-insensitive):
          hire      → contains "прийн" or "hire"
          vacation  → contains "відпуст" or "vacation"
          dismiss   → contains "звільн" or "dismiss"
        """
        if not self._templates_folder_id:
            raise ValueError(
                "TEMPLATES_FOLDER_ID is not set in .env. "
                "Copy .env.example → .env and fill in the folder IDs."
            )

        try:
            resp = self._drive.files().list(
                q=(
                    f"'{self._templates_folder_id}' in parents "
                    "and mimeType='application/vnd.google-apps.document' "
                    "and trashed=false"
                ),
                fields="files(id, name)",
                pageSize=50,
            ).execute()
        except HttpError as exc:
            raise RuntimeError(f"Drive API error while listing templates: {exc}") from exc

        files = resp.get("files", [])

        mapping: dict[str, str] = {}
        for f in files:
            name_lower = f["name"].lower()
            if "прийн" in name_lower or "hire" in name_lower or "прийом" in name_lower:
                mapping[OrderType.HIRE.value] = f["id"]
            elif "відпуст" in name_lower or "vacation" in name_lower:
                mapping[OrderType.VACATION.value] = f["id"]
            elif "звільн" in name_lower or "dismiss" in name_lower:
                mapping[OrderType.DISMISS.value] = f["id"]

        return mapping

    def create_order(
        self, template_id: str, employee: Employee, folder_path: str
    ) -> str:
        """
        1. Copy the template to the target Drive folder.
        2. Fill {{markers}} with employee data.
        3. Return a browser-ready URL to the created document.
        """
        doc_name = _build_doc_name(employee, template_id)

        # ── Step 1: copy ──────────────────────────────────────────────────────
        try:
            new_file = self._drive.files().copy(
                fileId=template_id,
                body={"name": doc_name, "parents": [folder_path]},
                fields="id",
            ).execute()
        except HttpError as exc:
            raise RuntimeError(
                f"Failed to copy template '{template_id}' for {employee.short_name}: {exc}"
            ) from exc

        doc_id: str = new_file["id"]

        # ── Step 2: fill markers ──────────────────────────────────────────────
        substitutions = employee.to_template_dict()
        requests = [
            {
                "replaceAllText": {
                    "containsText": {"text": marker, "matchCase": True},
                    "replaceText": str(value),
                }
            }
            for marker, value in substitutions.items()
        ]

        try:
            self._docs.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests},
            ).execute()
        except HttpError as exc:
            # Document was created — return URL even if fill partially failed
            return f"https://docs.google.com/document/d/{doc_id}/edit"

        return f"https://docs.google.com/document/d/{doc_id}/edit"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_doc_name(employee: Employee, template_id: str) -> str:
    """Generate a human-readable document name."""
    # Визначаємо тип наказу з template_id або за замовчуванням
    label_map = {
        OrderType.HIRE.value:     "Наказ_про_прийняття",
        OrderType.VACATION.value: "Наказ_про_відпустку",
        OrderType.DISMISS.value:  "Наказ_про_звільнення",
    }
    # Якщо template_id не містить ключового слова — використовуємо загальну назву
    prefix = "Наказ"
    for key, name in label_map.items():
        if key in template_id.lower():
            prefix = name
            break

    return f"{prefix}_{employee.last_name}_{employee.first_name}"

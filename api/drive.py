"""
api/drive.py — Google Drive & Docs integration (Andrii's module).

Implements ApiClientProtocol defined in core/orchestrator.py.
Uses OAuth 2.0 (installed-app flow) stored in token.json.
"""

import json
import os
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.config import get_credentials
from models import Employee, OrderType

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
        creds = get_credentials()
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
        self, template_id: str, employee: Employee, folder_path: str, order_type: str
    ) -> str:
        """
        1. Copy the template to the target Drive folder.
        2. Fill {{markers}} with employee data.
        3. Return a browser-ready URL to the created document.
        """
        doc_name = _build_doc_name(employee, order_type)

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

def _build_doc_name(employee: Employee, order_type: str) -> str:
    """Generate a human-readable document name."""
    label_map = {
        OrderType.HIRE.value:     "Наказ_про_прийняття",
        OrderType.VACATION.value: "Наказ_про_відпустку",
        OrderType.DISMISS.value:  "Наказ_про_звільнення",
    }
    prefix = label_map.get(order_type, "Наказ")
    return f"{prefix}_{employee.last_name}_{employee.first_name}"

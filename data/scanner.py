"""
data/scanner.py — Google Drive scanner & employee data manager (Misha's module).

Implements DataManagerProtocol defined in core/orchestrator.py.
"""

import json
import os
import uuid
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.config import get_credentials
from models import Employee


# ─── DataManager ─────────────────────────────────────────────────────────────

class DataManager:
    """
    Production implementation of DataManagerProtocol.

    Scans the Employees/ folder on Google Drive.
    Each employee has their own sub-folder containing a profile.json.
    Manages the Orders/<year>/<month>/<employee_id>/ directory structure.
    """

    def __init__(self) -> None:
        creds = get_credentials()
        self._drive = build("drive", "v3", credentials=creds)
        self._employees_folder_id = os.getenv("EMPLOYEES_FOLDER_ID", "")
        self._orders_folder_id    = os.getenv("ORDERS_FOLDER_ID", "")

    # ── DataManagerProtocol ───────────────────────────────────────────────────

    def scan_employees(self) -> list[Employee]:
        """
        List all sub-folders in Employees/, then look for profile.json inside each.
        Falls back to reading folder metadata if profile.json is missing.
        """
        if not self._employees_folder_id:
            raise ValueError(
                "EMPLOYEES_FOLDER_ID is not set in .env. "
                "Copy .env.example → .env and fill in the folder IDs."
            )

        # 1. List all employee folders
        try:
            resp = self._drive.files().list(
                q=(
                    f"'{self._employees_folder_id}' in parents "
                    "and mimeType='application/vnd.google-apps.folder' "
                    "and trashed=false"
                ),
                fields="files(id, name)",
                pageSize=200,
                orderBy="name",
            ).execute()
        except HttpError as exc:
            raise RuntimeError(f"Failed to list employee folders: {exc}") from exc

        employees: list[Employee] = []
        for folder in resp.get("files", []):
            emp = self._load_employee_from_folder(folder["id"], folder["name"])
            if emp:
                employees.append(emp)

        return employees

    def ensure_order_directory(
        self, employee_id: str, year: int, month: int
    ) -> str:
        """
        Create (if needed) Orders/<year>/<month:02d>/<employee_id>/ on Drive.
        Returns the folder ID of the leaf directory.
        """
        if not self._orders_folder_id:
            raise ValueError("ORDERS_FOLDER_ID is not set in .env.")

        year_folder  = self._get_or_create_folder(str(year),        self._orders_folder_id)
        month_folder = self._get_or_create_folder(f"{month:02d}",   year_folder)
        emp_folder   = self._get_or_create_folder(employee_id,       month_folder)
        return emp_folder

    def create_employee(self, employee: Employee) -> Employee:
        """
        Create a sub-folder in Employees/ and write profile.json into it.
        Returns the Employee with the assigned folder_id.
        """
        if not self._employees_folder_id:
            raise ValueError("EMPLOYEES_FOLDER_ID is not set in .env.")

        from models import _format_date  # avoid circular at module level

        folder_name = f"{employee.last_name} {employee.first_name} ({employee.employee_id})"
        folder_id   = self._get_or_create_folder(folder_name, self._employees_folder_id)

        profile = {
            "employee_id": employee.employee_id,
            "last_name":   employee.last_name,
            "first_name":  employee.first_name,
            "middle_name": employee.middle_name,
            "position":    employee.position,
            "department":  employee.department,
            "hire_date":   _format_date(employee.hire_date),
            "birth_date":  _format_date(employee.birth_date),
            "email":       employee.email  or "",
            "phone":       employee.phone  or "",
        }
        self._upload_json(profile, "profile.json", folder_id)

        from dataclasses import replace
        return replace(employee, folder_id=folder_id)


    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_employee_from_folder(
        self, folder_id: str, folder_name: str
    ) -> Employee | None:
        """Try to read profile.json; fall back to parsing the folder name."""
        try:
            # Look for profile.json inside this folder
            resp = self._drive.files().list(
                q=(
                    f"'{folder_id}' in parents "
                    "and name='profile.json' "
                    "and trashed=false"
                ),
                fields="files(id)",
                pageSize=1,
            ).execute()

            files = resp.get("files", [])
            if files:
                content = (
                    self._drive.files()
                    .get_media(fileId=files[0]["id"])
                    .execute()
                )
                profile = json.loads(content)
                return Employee.from_profile(profile, folder_id=folder_id)

        except (HttpError, json.JSONDecodeError):
            pass  # Fall through to name-based parsing

        # Best-effort: parse "Прізвище Ім'я (EMP001)" from folder name
        return _employee_from_folder_name(folder_name, folder_id)

    def _get_or_create_folder(self, name: str, parent_id: str) -> str:
        """Return the ID of an existing folder or create a new one."""
        try:
            resp = self._drive.files().list(
                q=(
                    f"'{parent_id}' in parents "
                    f"and name='{name}' "
                    "and mimeType='application/vnd.google-apps.folder' "
                    "and trashed=false"
                ),
                fields="files(id)",
                pageSize=1,
            ).execute()
            existing = resp.get("files", [])
            if existing:
                return existing[0]["id"]

            # Create it
            folder = self._drive.files().create(
                body={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                },
                fields="id",
            ).execute()
            return folder["id"]

        except HttpError as exc:
            raise RuntimeError(f"Failed to get/create folder '{name}': {exc}") from exc

    def _upload_json(self, data: dict, filename: str, parent_id: str) -> str:
        """Upload a dict as a JSON file to Drive. Returns the file ID."""
        import io
        from googleapiclient.http import MediaIoBaseUpload

        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype="application/json",
            resumable=False,
        )

        # Check if file already exists — update instead of duplicating
        resp = self._drive.files().list(
            q=f"'{parent_id}' in parents and name='{filename}' and trashed=false",
            fields="files(id)",
            pageSize=1,
        ).execute()
        existing = resp.get("files", [])

        if existing:
            self._drive.files().update(
                fileId=existing[0]["id"],
                media_body=media,
            ).execute()
            return existing[0]["id"]
        else:
            file = self._drive.files().create(
                body={"name": filename, "parents": [parent_id]},
                media_body=media,
                fields="id",
            ).execute()
            return file["id"]


# ─── Name-parsing fallback ────────────────────────────────────────────────────

def _employee_from_folder_name(folder_name: str, folder_id: str) -> Employee | None:
    """
    Parse an Employee from a folder name like:
      "Коваленко Олексій Іванович (EMP001)"
      "Коваленко Олексій (EMP001)"
    Returns None if the name does not match the expected pattern.
    """
    import re
    match = re.match(r"^(.+?)\s*\((\w+)\)\s*$", folder_name.strip())
    if not match:
        return None

    name_part, emp_id = match.group(1).strip(), match.group(2).strip()
    parts = name_part.split()

    last_name   = parts[0] if len(parts) > 0 else ""
    first_name  = parts[1] if len(parts) > 1 else ""
    middle_name = parts[2] if len(parts) > 2 else ""

    return Employee(
        employee_id=emp_id,
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        position="",
        department="",
        folder_id=folder_id,
    )

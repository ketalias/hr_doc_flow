"""Shared data contract. All modules import from here — do not duplicate."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class OrderType(str, Enum):
    """Supported HR order types. Value matches the template key in Drive."""

    HIRE = "hire"
    VACATION = "vacation"
    DISMISS = "dismiss"

    def label(self) -> str:
        """Human-readable Ukrainian label shown in the UI."""
        return {
            OrderType.HIRE:     "Наказ про прийняття на роботу",
            OrderType.VACATION: "Наказ про відпустку",
            OrderType.DISMISS:  "Наказ про звільнення",
        }[self]


@dataclass
class Employee:
    """
    Single source of truth for an employee record.

    Produced by data.scanner, consumed by api.drive and core.orchestrator.
    All fields must be present; folder_id and email may be empty strings when
    working with local mock data.
    """

    employee_id: str
    last_name: str
    first_name: str
    middle_name: str
    position: str
    department: str
    hire_date: Optional[str] = None
    birth_date: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    folder_id: str = field(default="")

    @property
    def full_name(self) -> str:
        """Прізвище Ім'я По-батькові."""
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()

    @property
    def short_name(self) -> str:
        """Прізвище І. Б. — used in order titles and table rows."""
        initials = ""
        if self.first_name:
            initials += f"{self.first_name[0]}."
        if self.middle_name:
            initials += f" {self.middle_name[0]}."
        return f"{self.last_name}{(' ' + initials.strip()) if initials else ''}".strip()

    def __str__(self) -> str:
        return f"{self.short_name} [{self.employee_id}] — {self.position}"

    def to_template_dict(self) -> dict:
        """Повертає словник для підстановки у шаблони Google Docs."""
        today = date.today()
        data = {
            "{{employee_id}}": self.employee_id,
            "{{first_name}}": self.first_name,
            "{{last_name}}": self.last_name,
            "{{full_name}}": self.full_name,
            "{{position}}": self.position,
            "{{department}}": self.department,
            "{{date}}": today.strftime("%d.%m.%Y"),
        }
        if self.hire_date:
            data["{{hire_date}}"] = self.hire_date
        if self.birth_date:
            data["{{birth_date}}"] = self.birth_date
        if self.email:
            data["{{email}}"] = self.email
        if self.phone:
            data["{{phone}}"] = self.phone
        return data

    @classmethod
    def from_profile(cls, profile: dict, folder_id: str = None) -> "Employee":
        """Створює Employee з даних profile.json."""
        return cls(
            employee_id=profile.get("employee_id", ""),
            first_name=profile.get("first_name", ""),
            last_name=profile.get("last_name", ""),
            middle_name=profile.get("middle_name", ""),
            position=profile.get("position", ""),
            department=profile.get("department", ""),
            hire_date=profile.get("hire_date"),
            birth_date=profile.get("birth_date"),
            email=profile.get("email"),
            phone=profile.get("phone"),
            folder_id=folder_id or "",
        )


def get_employee_mock(emp_id: str) -> Employee:
    """Тимчасова заглушка для тестування без Google Drive."""
    return Employee(
        employee_id=emp_id,
        first_name="Іван",
        last_name="Франко",
        middle_name="Якович",
        position="Junior QA",
        department="Engineering",
        hire_date="2026-06-01",
        birth_date="1990-05-15",
    )

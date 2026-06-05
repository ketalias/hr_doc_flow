"""Shared data contract. All modules import from here — do not duplicate."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


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
    hire_date: date
    birth_date: date
    folder_id: str = field(default="")
    email: str = field(default="")

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
def get_employee_mock(emp_id: str) -> Employee:
    """
    Тимчасова функція-заглушка для тестування генерації документів,
    поки не готова справжня логіка читання з Google Drive.
    """
    return Employee(
        employee_id=emp_id,
        first_name="Іван",
        last_name="Франко",
        position="Junior QA",
        department="Engineering",
        hire_date="2026-06-01")
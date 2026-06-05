from dataclasses import dataclass, field
from typing import Optional
from datetime import date


@dataclass
class Employee:
    employee_id: str
    first_name: str
    last_name: str
    position: str
    department: str
    hire_date: Optional[str] = None
    birth_date: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    folder_id: Optional[str] = None

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}"

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
            position=profile.get("position", ""),
            department=profile.get("department", ""),
            hire_date=profile.get("hire_date"),
            birth_date=profile.get("birth_date"),
            email=profile.get("email"),
            phone=profile.get("phone"),
            folder_id=folder_id,
        )


def get_employee_mock(emp_id: str) -> Employee:
    """Тимчасова заглушка для тестування без Google Drive."""
    return Employee(
        employee_id=emp_id,
        first_name="Іван",
        last_name="Франко",
        position="Junior QA",
        department="Engineering",
        hire_date="2026-06-01",
        birth_date="1990-05-15",
    )
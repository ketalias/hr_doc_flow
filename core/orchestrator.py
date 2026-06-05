"""Orchestrator: coordinates Data Manager and API Client.

Defines Protocol interfaces so this module compiles and tests independently
of Andrii's and Misha's implementations.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol, runtime_checkable

from models import Employee, OrderType


# ─── Interfaces (structural typing via Protocol) ──────────────────────────────

@runtime_checkable
class DataManagerProtocol(Protocol):
    """Contract expected from Misha's data module."""

    def scan_employees(self) -> list[Employee]:
        """Return all employees found in the Employees folder."""
        ...

    def ensure_order_directory(
        self, employee_id: str, year: int, month: int
    ) -> str:
        """
        Create (if needed) and return the target path/folder ID for an order.

        Expected path format: Orders/<year>/<month:02d>/<employee_id>/
        """
        ...

    def create_employee(self, employee: Employee) -> Employee:
        """
        Persist a new employee record (Drive folder + profile.json).

        Returns the saved Employee, potentially with an assigned folder_id.
        """
        ...


@runtime_checkable
class ApiClientProtocol(Protocol):
    """Contract expected from Andrii's API module."""

    def get_templates(self) -> dict[str, str]:
        """Return {order_type_value: template_id} for all available templates."""
        ...

    def create_order(
        self, template_id: str, employee: Employee, folder_path: str
    ) -> str:
        """
        Copy the template, substitute {{markers}}, save to folder_path.

        Returns the URL or ID of the newly created document.
        """
        ...


# ─── Result type for bulk operations ─────────────────────────────────────────

@dataclass
class BulkResult:
    """Outcome for one employee in a bulk order generation run."""

    employee: Employee
    doc_url: Optional[str]
    error: Optional[Exception]

    @property
    def ok(self) -> bool:
        return self.error is None


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class Orchestrator:
    """
    Central coordinator. Owns no data, calls no APIs directly.
    All side effects go through the injected data_manager and api_client.
    """

    def __init__(
        self,
        data_manager: DataManagerProtocol,
        api_client: ApiClientProtocol,
    ) -> None:
        self._data = data_manager
        self._api = api_client
        self._log = logging.getLogger("hr_doc_flow.orchestrator")

    # ── Queries ───────────────────────────────────────────────────────────────

    def list_employees(self) -> list[Employee]:
        """Scan and return all employees."""
        self._log.info("Scanning employee folders…")
        employees = self._data.scan_employees()
        self._log.info(
            f"Found [bold]{len(employees)}[/bold] employee(s)."
        )
        return employees

    def search_employees(
        self, query: str, employees: list[Employee]
    ) -> list[Employee]:
        """Case-insensitive filter by full name or employee ID."""
        q = query.strip().lower()
        return [
            e for e in employees
            if q in e.full_name.lower() or q in e.employee_id.lower()
        ]

    # ── Commands ──────────────────────────────────────────────────────────────

    def generate_order(
        self, employee: Employee, order_type: OrderType
    ) -> str:
        """
        Full order generation pipeline:

        1. Resolve the correct template from Drive.
        2. Ensure the target Orders/ subdirectory exists.
        3. Copy template → substitute markers → save to target folder.

        Returns the URL of the created document.
        Raises ValueError if the template for the given order_type is missing.
        """
        today = date.today()

        self._log.info(
            f"Generating [bold]{order_type.label()}[/bold] "
            f"for [italic]{employee.short_name}[/italic]…"
        )

        templates = self._api.get_templates()
        template_id = templates.get(order_type.value)
        if not template_id:
            raise ValueError(
                f"No template registered for order type '{order_type.value}'. "
                "Check the Templates folder in Drive."
            )

        folder_path = self._data.ensure_order_directory(
            employee.employee_id,
            today.year,
            today.month,
        )

        doc_url = self._api.create_order(template_id, employee, folder_path)

        self._log.info(
            f"Document saved → [bold]{folder_path}[/bold]"
        )
        return doc_url

    def generate_orders_bulk(
        self, employees: list[Employee], order_type: OrderType
    ) -> list[BulkResult]:
        """
        Generate the same order type for a list of employees.

        Never raises — each failure is captured in BulkResult.error so the
        caller can display per-employee success/failure without crashing.
        """
        self._log.info(
            f"Bulk [bold]{order_type.label()}[/bold] "
            f"for [bold]{len(employees)}[/bold] employee(s)…"
        )
        results: list[BulkResult] = []
        for emp in employees:
            try:
                url = self.generate_order(emp, order_type)
                results.append(BulkResult(employee=emp, doc_url=url, error=None))
            except Exception as exc:
                self._log.warning(
                    f"Failed for [italic]{emp.short_name}[/italic]: {exc}"
                )
                results.append(BulkResult(employee=emp, doc_url=None, error=exc))
        return results

    def create_employee(self, employee: Employee) -> Employee:
        """Persist a new employee via data manager and return the saved record."""
        self._log.info(f"Creating employee [italic]{employee.short_name}[/italic]…")
        saved = self._data.create_employee(employee)
        self._log.info(
            f"Employee [bold]{saved.employee_id}[/bold] created."
        )
        return saved

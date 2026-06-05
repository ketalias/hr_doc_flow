"""Entry point. Wires all modules together and drives the main menu loop."""

import sys
import logging

from dotenv import load_dotenv

from core.logger import get_logger
from core.orchestrator import Orchestrator
from core import ui
from models import OrderType


# ─── Dependency injection: real modules or mocks ─────────────────────────────
# When Andrii / Misha finish their modules, replace these imports.
# The Orchestrator only cares about the Protocol interface, not the class name.

try:
    from api.drive import DriveClient as _ApiClient          # type: ignore[import]
    _MOCK_API = False
except ImportError:
    from mocks.mock_api import MockApiClient as _ApiClient   # type: ignore[assignment]
    _MOCK_API = True

try:
    from data.scanner import DataManager as _DataManager         # type: ignore[import]
    _MOCK_DATA = False
except ImportError:
    from mocks.mock_data import MockDataManager as _DataManager  # type: ignore[assignment]
    _MOCK_DATA = True


# ─── Action handlers ──────────────────────────────────────────────────────────

def _action_list(orchestrator: Orchestrator) -> None:
    employees = orchestrator.list_employees()
    if employees:
        ui.display_employees_table(employees)
    else:
        ui.display_info("Список працівників порожній.")


def _action_create(orchestrator: Orchestrator) -> None:
    employees = orchestrator.list_employees()

    employee = ui.prompt_select_employee(employees)
    if employee is None:
        return

    order_type = ui.prompt_select_order_type()
    if order_type is None:
        return

    confirmed = ui.prompt_confirm(
        f"Створити «{order_type.label()}» для {employee.short_name}?"
    )
    if not confirmed:
        ui.display_info("Скасовано.")
        return

    try:
        doc_url = orchestrator.generate_order(employee, order_type)
        ui.display_success(f"Документ створено: {doc_url}")
    except ValueError as exc:
        ui.display_error(str(exc))
    except Exception as exc:
        logging.getLogger("hr_doc_flow").exception("Unexpected error during order creation")
        ui.display_error(f"Помилка: {exc}")


def _action_search(orchestrator: Orchestrator) -> None:
    query = ui.prompt_search_query()
    if not query:
        return

    employees = orchestrator.list_employees()
    results = orchestrator.search_employees(query, employees)

    if results:
        ui.display_employees_table(results)
    else:
        ui.display_info(f"Не знайдено за запитом: «{query}»")


def _action_bulk_create(orchestrator: Orchestrator) -> None:
    employees = orchestrator.list_employees()

    selected = ui.prompt_select_employees_multi(employees)
    if not selected:
        ui.display_info("Нікого не вибрано.")
        return

    order_type = ui.prompt_select_order_type()
    if order_type is None:
        return

    confirmed = ui.prompt_confirm(
        f"Створити «{order_type.label()}» для {len(selected)} працівника(-ів)?"
    )
    if not confirmed:
        ui.display_info("Скасовано.")
        return

    results = []
    with ui.make_bulk_progress() as progress:
        task = progress.add_task("Підготовка…", total=len(selected))
        for emp in selected:
            progress.update(task, description=emp.short_name)
            result = orchestrator.generate_orders_bulk([emp], order_type)[0]
            results.append(result)
            progress.advance(task)

    ok  = [r for r in results if r.ok]
    bad = [r for r in results if not r.ok]

    if ok:
        ui.display_success(f"Успішно створено {len(ok)} з {len(results)} наказів.")
    for r in bad:
        ui.display_error(f"{r.employee.short_name}: {r.error}")


def _action_add_employee(orchestrator: Orchestrator) -> None:
    employee = ui.prompt_new_employee()
    if employee is None:
        ui.display_info("Скасовано.")
        return

    confirmed = ui.prompt_confirm(
        f"Зберегти нового працівника {employee.short_name} [{employee.employee_id}]?"
    )
    if not confirmed:
        ui.display_info("Скасовано.")
        return

    try:
        saved = orchestrator.create_employee(employee)
        ui.display_success(
            f"Працівника [bold]{saved.full_name}[/bold] додано  (ID: {saved.employee_id})"
        )
    except Exception as exc:
        logging.getLogger("hr_doc_flow").exception("Failed to create employee")
        ui.display_error(f"Помилка збереження: {exc}")


_ACTIONS = {
    "list":         _action_list,
    "create":       _action_create,
    "bulk":         _action_bulk_create,
    "search":       _action_search,
    "add_employee": _action_add_employee,
}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    load_dotenv()
    log = get_logger()

    orchestrator = Orchestrator(
        data_manager=_DataManager(),
        api_client=_ApiClient(),
    )

    ui.display_animated_banner()

    if _MOCK_API or _MOCK_DATA:
        log.warning(
            "Running in [bold yellow]mock mode[/bold yellow] — "
            "no Google Drive connection. "
            f"({'api' if _MOCK_API else ''}"
            f"{' + ' if _MOCK_API and _MOCK_DATA else ''}"
            f"{'data' if _MOCK_DATA else ''} module(s) missing)"
        )

    log.info("System ready.")

    while True:
        choice = ui.display_main_menu()

        if choice is None or choice == "exit":
            log.info("Session ended.")
            break

        handler = _ACTIONS.get(choice)
        if handler:
            handler(orchestrator)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        sys.exit(0)

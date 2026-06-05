"""All user-facing output and input prompts live here.

Single responsibility: translate between Python objects and the terminal.
No business logic — that belongs in orchestrator.py.
"""

import time
from datetime import date, datetime
from typing import Optional

import questionary
from rich import box
from rich.align import Align
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table
from rich.text import Text

from core.logger import console
from models import Employee, OrderType


# ─── questionary colour scheme ────────────────────────────────────────────────

_STYLE = questionary.Style([
    ("qmark",       "fg:#5f87ff bold"),
    ("question",    "bold"),
    ("answer",      "fg:#5f87ff bold"),
    ("pointer",     "fg:#5f87ff bold"),
    ("highlighted", "fg:#5f87ff bold"),
    ("selected",    "fg:#5f87ff"),
    ("separator",   "fg:#555555"),
    ("instruction", "fg:#555555 italic"),
])


# ─── Animated banner ──────────────────────────────────────────────────────────

_LOGO = [
    "╦ ╦╦═╗  ╔╦╗╔═╗╔═╗  ╔═╗╦  ╔═╗╦ ╦",
    "╠═╣╠╦╝   ║║║ ║║    ╠╣ ║  ║ ║║║║",
    "╩ ╩╩╚═  ═╩╝╚═╝╚═╝  ╚  ╩═╝╚═╝╚╩╝",
]

# Deep blue → sky blue → white → sky blue → deep blue wave
_WAVE = [
    "#0f2057", "#162d7a", "#1e52c0", "#2563eb",
    "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe",
    "#dbeafe", "#bfdbfe", "#93c5fd", "#60a5fa",
    "#3b82f6", "#2563eb", "#1e52c0", "#162d7a",
]


def _banner_frame(offset: int) -> Panel:
    body = Text(justify="center")
    for line in _LOGO:
        for j, ch in enumerate(line):
            color = _WAVE[(j + offset) % len(_WAVE)]
            body.append(ch, style=f"bold {color}")
        body.append("\n")
    body.append("\n")
    body.append(
        "Система автоматизованого кадрового документообігу",
        style="dim white",
    )
    border_col = _WAVE[(offset * 2) % len(_WAVE)]
    return Panel(Align.center(body), border_style=border_col, padding=(1, 6))


def display_animated_banner(duration: float = 2.2, fps: int = 20) -> None:
    """Roll a colour wave across the ASCII logo, then leave the final frame in place."""
    n = int(duration * fps)
    with Live(console=console, refresh_per_second=fps) as live:
        for i in range(n):
            live.update(_banner_frame(i))
            time.sleep(1.0 / fps)
    console.print()


# ─── Main menu ────────────────────────────────────────────────────────────────

def display_main_menu() -> Optional[str]:
    """
    Render the main action menu.

    Returns one of: 'list' | 'create' | 'bulk' | 'search'
                    | 'add_employee' | 'exit' | None (Ctrl+C).
    """
    return questionary.select(
        "Оберіть дію:",
        choices=[
            questionary.Choice("  Список працівників",  value="list"),
            questionary.Choice("  Створити наказ",      value="create"),
            questionary.Choice("  Масовий наказ",       value="bulk"),
            questionary.Choice("  Знайти працівника",   value="search"),
            questionary.Separator(),
            questionary.Choice("  Додати працівника",   value="add_employee"),
            questionary.Separator(),
            questionary.Choice("  Вихід",               value="exit"),
        ],
        style=_STYLE,
        use_indicator=True,
    ).ask()


# ─── Employee prompts ─────────────────────────────────────────────────────────

def prompt_select_employee(employees: list[Employee]) -> Optional[Employee]:
    """Single employee selection. Returns None if cancelled or list is empty."""
    if not employees:
        display_info("Список працівників порожній.")
        return None
    return questionary.select(
        "Оберіть працівника:",
        choices=[questionary.Choice(title=str(emp), value=emp) for emp in employees],
        style=_STYLE,
        use_indicator=True,
    ).ask()


def prompt_select_employees_multi(employees: list[Employee]) -> list[Employee]:
    """
    Checkbox multi-select for bulk operations.
    Space to toggle, Enter to confirm. Returns empty list if cancelled.
    """
    if not employees:
        display_info("Список працівників порожній.")
        return []
    result = questionary.checkbox(
        "Оберіть працівників  [Пробіл — вибрати / Enter — підтвердити]:",
        choices=[questionary.Choice(title=str(emp), value=emp) for emp in employees],
        style=_STYLE,
    ).ask()
    return result or []


def prompt_select_order_type() -> Optional[OrderType]:
    """Order type selection."""
    return questionary.select(
        "Тип наказу:",
        choices=[questionary.Choice(title=ot.label(), value=ot) for ot in OrderType],
        style=_STYLE,
        use_indicator=True,
    ).ask()


def prompt_confirm(message: str) -> bool:
    """Binary yes/no. Defaults to No."""
    result = questionary.confirm(message, style=_STYLE, default=False).ask()
    return bool(result)


def prompt_search_query() -> str:
    """Free-text search input."""
    result = questionary.text("Пошуковий запит (прізвище або ID):", style=_STYLE).ask()
    return result or ""


# ─── Add Employee form ────────────────────────────────────────────────────────

def _parse_date(value: str) -> Optional[date]:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _validate_date(value: str) -> "bool | str":
    return True if _parse_date(value) else "Формат: ДД.ММ.РРРР  (наприклад: 15.03.1990)"


def _validate_required(value: str) -> "bool | str":
    return True if value.strip() else "Поле обов'язкове"


def prompt_new_employee() -> Optional[Employee]:
    """
    Interactive multi-field form for creating a new employee record.
    Each field is validated inline. Returns None if the user cancels (Ctrl+C).
    """
    console.print()
    console.print(Panel(
        "[bold #5f87ff]  Додавання нового працівника[/bold #5f87ff]",
        border_style="#5f87ff",
        padding=(0, 2),
    ))
    console.print()

    def ask(prompt_fn) -> Optional[str]:
        return prompt_fn()   # None = Ctrl+C at this field

    last_name = ask(lambda: questionary.text(
        "Прізвище:", validate=_validate_required, style=_STYLE).ask())
    if last_name is None:
        return None

    first_name = ask(lambda: questionary.text(
        "Ім'я:", validate=_validate_required, style=_STYLE).ask())
    if first_name is None:
        return None

    middle_name = ask(lambda: questionary.text(
        "По батькові (необов'язково):", style=_STYLE).ask())
    if middle_name is None:
        return None

    position = ask(lambda: questionary.text(
        "Посада:", validate=_validate_required, style=_STYLE).ask())
    if position is None:
        return None

    department = ask(lambda: questionary.text(
        "Відділ:", validate=_validate_required, style=_STYLE).ask())
    if department is None:
        return None

    birth_raw = ask(lambda: questionary.text(
        "Дата народження  (ДД.ММ.РРРР):",
        validate=_validate_date,
        style=_STYLE,
    ).ask())
    if birth_raw is None:
        return None

    hire_raw = ask(lambda: questionary.text(
        "Дата прийняття   (ДД.ММ.РРРР):",
        default=date.today().strftime("%d.%m.%Y"),
        validate=_validate_date,
        style=_STYLE,
    ).ask())
    if hire_raw is None:
        return None

    emp_id_default = f"EMP{datetime.now().strftime('%m%d%H%M')}"
    employee_id = ask(lambda: questionary.text(
        "ID працівника:", default=emp_id_default, style=_STYLE).ask())
    if employee_id is None:
        return None

    return Employee(
        employee_id=employee_id.strip(),
        last_name=last_name.strip(),
        first_name=first_name.strip(),
        middle_name=middle_name.strip(),
        position=position.strip(),
        department=department.strip(),
        birth_date=_parse_date(birth_raw),   # type: ignore[arg-type]
        hire_date=_parse_date(hire_raw),     # type: ignore[arg-type]
    )


# ─── Bulk progress bar ────────────────────────────────────────────────────────

def make_bulk_progress() -> Progress:
    """Pre-configured Rich Progress bar for bulk order generation."""
    return Progress(
        SpinnerColumn(style="#5f87ff"),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=28, style="#1e3a6e", complete_style="#3b82f6"),
        TaskProgressColumn(),
        console=console,
        transient=False,
    )


# ─── Display helpers ──────────────────────────────────────────────────────────

def display_employees_table(employees: list[Employee]) -> None:
    """Render a list of employees as a Rich table."""
    table = Table(
        box=box.SIMPLE_HEAD,
        border_style="dim",
        header_style="bold #5f87ff",
        show_edge=False,
        pad_edge=True,
        row_styles=["", "dim"],
    )
    table.add_column("ID",          style="dim",  width=10)
    table.add_column("ПІБ",                       min_width=26)
    table.add_column("Посада",                    min_width=22)
    table.add_column("Відділ",                    min_width=14)
    table.add_column("Прийнятий",  style="dim",   width=12)

    for emp in employees:
        table.add_row(
            emp.employee_id,
            emp.full_name,
            emp.position,
            emp.department,
            emp.hire_date.strftime("%d.%m.%Y"),
        )

    console.print()
    console.print(table)


def display_success(message: str) -> None:
    console.print(Panel(
        f"[bold green]{message}[/bold green]",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()


def display_error(message: str) -> None:
    console.print(Panel(
        f"[bold red]{message}[/bold red]",
        border_style="red",
        padding=(0, 2),
    ))
    console.print()


def display_info(message: str) -> None:
    console.print(f"  [dim]{message}[/dim]")

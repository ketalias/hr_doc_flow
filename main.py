"""
Система автоматичного документообігу для кадрового обліку.
Головний модуль: Console UI + координація модулів.
"""

import sys
from models import Employee, get_employee_mock
from data_manager import DataManager
from logger import setup_logger, log_order_created, log_order_failed

# Ці ID потрібно встановити відповідно до вашого Google Drive
EMPLOYEES_FOLDER_ID = "YOUR_EMPLOYEES_FOLDER_ID"
TEMPLATES_FOLDER_ID = "YOUR_TEMPLATES_FOLDER_ID"
ORDERS_FOLDER_ID = "YOUR_ORDERS_FOLDER_ID"

logger = setup_logger()


# ── Допоміжні функції UI ──

def print_header(title: str):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")


def print_menu():
    print_header("Кадровий документообіг")
    print("  1. Показати список працівників")
    print("  2. Пошук працівника")
    print("  3. Створити наказ для працівника")
    print("  4. Масове створення наказів")
    print("  5. Оновити список працівників")
    print("  0. Вихід")
    print("-" * 50)


def display_employees(employees: list):
    if not employees:
        print("\n  Список працівників порожній. Оберіть пункт 5 для сканування.")
        return
    print(f"\n  {'№':<4} {'ID':<12} {'ПІБ':<30} {'Посада':<20}")
    print("  " + "-" * 66)
    for i, emp in enumerate(employees, 1):
        print(f"  {i:<4} {emp.employee_id:<12} {emp.full_name:<30} {emp.position:<20}")


def select_employee(employees: list) -> Employee | None:
    """Вибір працівника зі списку за номером."""
    display_employees(employees)
    if not employees:
        return None
    try:
        choice = int(input("\n  Оберіть номер працівника (0 — скасувати): "))
        if choice == 0:
            return None
        if 1 <= choice <= len(employees):
            return employees[choice - 1]
        print("  Невірний номер.")
    except ValueError:
        print("  Введіть число.")
    return None


def select_template(templates: list) -> dict | None:
    """Вибір шаблону зі списку."""
    if not templates:
        print("\n  Шаблони не знайдено. Перевірте папку Templates на Google Drive.")
        return None
    print(f"\n  {'№':<4} {'Назва шаблону':<40}")
    print("  " + "-" * 44)
    for i, tmpl in enumerate(templates, 1):
        print(f"  {i:<4} {tmpl['name']:<40}")
    try:
        choice = int(input("\n  Оберіть номер шаблону (0 — скасувати): "))
        if choice == 0:
            return None
        if 1 <= choice <= len(templates):
            return templates[choice - 1]
        print("  Невірний номер.")
    except ValueError:
        print("  Введіть число.")
    return None


# ── Основні операції ──

def action_search(data_mgr: DataManager):
    """Пошук працівника за ID або прізвищем."""
    query = input("\n  Введіть ID або прізвище для пошуку: ").strip()
    if not query:
        return

    # Спочатку шукаємо за ID
    emp = data_mgr.find_by_id(query)
    if emp:
        display_employees([emp])
        return

    # Потім за ім'ям/прізвищем
    results = data_mgr.find_by_name(query)
    if results:
        display_employees(results)
    else:
        print(f"  Працівника за запитом '{query}' не знайдено.")


def action_create_order(drive_service, docs_service, data_mgr: DataManager, templates: list):
    """Створення наказу для одного працівника."""
    from document_generator import copy_template, fill_document

    employee = select_employee(data_mgr.employees)
    if not employee:
        return

    template = select_template(templates)
    if not template:
        return

    # Маршрутизація: Orders/<Рік>/<Місяць>/<EmployeeID>/
    dest_folder_id = data_mgr.get_or_create_order_path(ORDERS_FOLDER_ID, employee.employee_id)
    if not dest_folder_id:
        print("  Помилка: не вдалося створити папку для наказу.")
        log_order_failed(logger, employee.full_name, template["name"], "Не вдалося створити папку")
        return

    doc_name = f"{template['name']}_{employee.last_name}_{employee.first_name}"

    # Копіюємо шаблон
    new_doc_id = copy_template(drive_service, template["id"], dest_folder_id, doc_name)
    if not new_doc_id:
        log_order_failed(logger, employee.full_name, template["name"], "Не вдалося скопіювати шаблон")
        return

    # Заповнюємо маркери даними працівника
    success = fill_document(docs_service, new_doc_id, employee)
    if success:
        print(f"\n  Наказ успішно створено! ID документа: {new_doc_id}")
        log_order_created(logger, employee.full_name, template["name"], new_doc_id)
    else:
        print(f"\n  Документ створено (ID: {new_doc_id}), але виникли помилки при заповненні.")
        log_order_failed(logger, employee.full_name, template["name"], "Помилка заповнення тексту")


def action_bulk_orders(drive_service, docs_service, data_mgr: DataManager, templates: list):
    """Масове створення наказів для групи працівників."""
    from document_generator import copy_template, fill_document

    template = select_template(templates)
    if not template:
        return

    display_employees(data_mgr.employees)
    if not data_mgr.employees:
        return

    raw = input("\n  Введіть номери працівників через кому (або 'all' для всіх): ").strip()

    if raw.lower() == "all":
        selected = list(data_mgr.employees)
    else:
        try:
            indices = [int(x.strip()) for x in raw.split(",")]
            selected = []
            for idx in indices:
                if 1 <= idx <= len(data_mgr.employees):
                    selected.append(data_mgr.employees[idx - 1])
                else:
                    print(f"  Пропущено невірний номер: {idx}")
        except ValueError:
            print("  Помилка введення.")
            return

    if not selected:
        print("  Не обрано жодного працівника.")
        return

    confirm = input(f"\n  Створити '{template['name']}' для {len(selected)} працівників? (y/n): ")
    if confirm.lower() != "y":
        print("  Скасовано.")
        return

    success_count = 0
    for emp in selected:
        dest_folder_id = data_mgr.get_or_create_order_path(ORDERS_FOLDER_ID, emp.employee_id)
        if not dest_folder_id:
            log_order_failed(logger, emp.full_name, template["name"], "Не вдалося створити папку")
            continue

        doc_name = f"{template['name']}_{emp.last_name}_{emp.first_name}"
        new_doc_id = copy_template(drive_service, template["id"], dest_folder_id, doc_name)
        if not new_doc_id:
            log_order_failed(logger, emp.full_name, template["name"], "Не вдалося скопіювати шаблон")
            continue

        if fill_document(docs_service, new_doc_id, emp):
            log_order_created(logger, emp.full_name, template["name"], new_doc_id)
            success_count += 1
        else:
            log_order_failed(logger, emp.full_name, template["name"], "Помилка заповнення")

    print(f"\n  Готово! Успішно створено: {success_count}/{len(selected)} наказів.")


# ── Точка входу ──

def main():
    from document_generator import authenticate_google_services

    print_header("Ініціалізація системи")

    drive_service, docs_service = authenticate_google_services()
    if not drive_service or not docs_service:
        print("Не вдалося авторизуватися. Перевірте credentials.json.")
        sys.exit(1)

    data_mgr = DataManager(drive_service)

    # Початкове сканування
    print("\nСканування працівників...")
    data_mgr.scan_employees(EMPLOYEES_FOLDER_ID)

    print("\nЗавантаження шаблонів...")
    templates = data_mgr.scan_templates(TEMPLATES_FOLDER_ID)
    print(f"Знайдено шаблонів: {len(templates)}")

    logger.info("Систему запущено.")

    # Головний цикл меню
    while True:
        print_menu()
        choice = input("  Ваш вибір: ").strip()

        if choice == "1":
            display_employees(data_mgr.employees)
        elif choice == "2":
            action_search(data_mgr)
        elif choice == "3":
            action_create_order(drive_service, docs_service, data_mgr, templates)
        elif choice == "4":
            action_bulk_orders(drive_service, docs_service, data_mgr, templates)
        elif choice == "5":
            print("\nОновлення списку працівників...")
            data_mgr.scan_employees(EMPLOYEES_FOLDER_ID)
            templates = data_mgr.scan_templates(TEMPLATES_FOLDER_ID)
        elif choice == "0":
            logger.info("Систему завершено.")
            print("\nДо побачення!")
            break
        else:
            print("  Невірний вибір. Спробуйте ще раз.")


if __name__ == "__main__":
    main()

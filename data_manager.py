import json
from datetime import date
from typing import List, Optional
from googleapiclient.errors import HttpError
from models import Employee


class DataManager:
    """
    Пункт 2: Бізнес-логіка та обробка даних.
    Сканування працівників, парсинг profile.json,
    маршрутизація збереження наказів.
    """

    def __init__(self, drive_service):
        self.drive = drive_service
        self._employees: List[Employee] = []

    # ── 4.2.1 Сканування структури Employees ──

    def scan_employees(self, employees_folder_id: str) -> List[Employee]:
        """
        Зчитує всі підпапки з папки Employees,
        знаходить profile.json у кожній, формує список Employee.
        """
        self._employees = []

        subfolders = self._list_subfolders(employees_folder_id)

        for folder in subfolders:
            folder_id = folder["id"]
            folder_name = folder["name"]

            profile_data = self._read_profile_json(folder_id)
            if profile_data is None:
                print(f"  [!] Папка '{folder_name}' не містить profile.json — пропущено.")
                continue

            employee = Employee.from_profile(profile_data, folder_id=folder_id)
            self._employees.append(employee)
            print(f"  [+] Знайдено працівника: {employee.full_name} ({employee.employee_id})")

        print(f"\nВсього знайдено працівників: {len(self._employees)}")
        return self._employees

    def _list_subfolders(self, parent_folder_id: str) -> list:
        """Повертає список підпапок у вказаній папці Google Drive."""
        query = (
            f"'{parent_folder_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )
        try:
            results = self.drive.files().list(
                q=query,
                fields="files(id, name)",
                orderBy="name",
            ).execute()
            return results.get("files", [])
        except HttpError as e:
            print(f"Помилка при читанні папок: {e}")
            return []

    def _read_profile_json(self, folder_id: str) -> Optional[dict]:
        """Знаходить та зчитує profile.json у папці працівника."""
        query = (
            f"'{folder_id}' in parents "
            f"and name='profile.json' "
            f"and trashed=false"
        )
        try:
            results = self.drive.files().list(
                q=query,
                fields="files(id)",
            ).execute()
            files = results.get("files", [])

            if not files:
                return None

            file_id = files[0]["id"]
            content = self.drive.files().get_media(fileId=file_id).execute()
            return json.loads(content)

        except (HttpError, json.JSONDecodeError) as e:
            print(f"Помилка при читанні profile.json: {e}")
            return None

    # ── Пошук працівника ──

    @property
    def employees(self) -> List[Employee]:
        return self._employees

    def find_by_id(self, employee_id: str) -> Optional[Employee]:
        """Пошук працівника за ID."""
        for emp in self._employees:
            if emp.employee_id == employee_id:
                return emp
        return None

    def find_by_name(self, query: str) -> List[Employee]:
        """Пошук працівників за прізвищем або ім'ям (часткове співпадіння)."""
        query_lower = query.lower()
        return [
            emp for emp in self._employees
            if query_lower in emp.last_name.lower()
            or query_lower in emp.first_name.lower()
        ]

    # ── 3.3 Маршрутизація збереження (Orders/<Рік>/<Місяць>/<EmployeeID>/) ──

    def get_or_create_order_path(self, orders_folder_id: str, employee_id: str) -> Optional[str]:
        """
        Створює структуру Orders/<Рік>/<Місяць>/<EmployeeID>/
        та повертає ID кінцевої папки.
        """
        today = date.today()
        year_str = str(today.year)
        month_str = f"{today.month:02d}"

        year_folder_id = self._get_or_create_folder(year_str, orders_folder_id)
        if not year_folder_id:
            return None

        month_folder_id = self._get_or_create_folder(month_str, year_folder_id)
        if not month_folder_id:
            return None

        emp_folder_id = self._get_or_create_folder(employee_id, month_folder_id)
        return emp_folder_id

    def _get_or_create_folder(self, name: str, parent_id: str) -> Optional[str]:
        """Знаходить або створює папку з вказаним ім'ям у батьківській папці."""
        query = (
            f"'{parent_id}' in parents "
            f"and name='{name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )
        try:
            results = self.drive.files().list(
                q=query,
                fields="files(id)",
            ).execute()
            files = results.get("files", [])

            if files:
                return files[0]["id"]

            # Папка не знайдена — створюємо
            metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }
            folder = self.drive.files().create(
                body=metadata,
                fields="id",
            ).execute()
            return folder.get("id")

        except HttpError as e:
            print(f"Помилка при створенні папки '{name}': {e}")
            return None

    # ── Сканування шаблонів ──

    def scan_templates(self, templates_folder_id: str) -> list:
        """Зчитує список шаблонів з папки Templates."""
        query = (
            f"'{templates_folder_id}' in parents "
            f"and mimeType='application/vnd.google-apps.document' "
            f"and trashed=false"
        )
        try:
            results = self.drive.files().list(
                q=query,
                fields="files(id, name)",
                orderBy="name",
            ).execute()
            return results.get("files", [])
        except HttpError as e:
            print(f"Помилка при читанні шаблонів: {e}")
            return []

"""MockDataManager — stand-in for Misha's data.scanner module."""

from models import Employee


class MockDataManager:
    """Returns hard-coded employees and no-op directory management."""

    def scan_employees(self) -> list[Employee]:
        return [
            Employee(
                employee_id="EMP001",
                last_name="Коваленко",
                first_name="Олексій",
                middle_name="Іванович",
                position="Розробник програмного забезпечення",
                department="IT",
                hire_date="2022-03-15",
                birth_date="1990-07-20",
                folder_id="mock_folder_001",
                email="kovalenko@company.ua",
            ),
            Employee(
                employee_id="EMP002",
                last_name="Шевченко",
                first_name="Марія",
                middle_name="Петрівна",
                position="HR-менеджер",
                department="HR",
                hire_date="2021-01-10",
                birth_date="1988-04-05",
                folder_id="mock_folder_002",
                email="shevchenko@company.ua",
            ),
            Employee(
                employee_id="EMP003",
                last_name="Бойко",
                first_name="Дмитро",
                middle_name="Олегович",
                position="Бухгалтер",
                department="Фінанси",
                hire_date="2019-09-01",
                birth_date="1985-12-30",
                folder_id="mock_folder_003",
                email="boyko@company.ua",
            ),
        ]

    def ensure_order_directory(
        self, employee_id: str, year: int, month: int
    ) -> str:
        """Returns a fake folder path string (no actual FS operations)."""
        return f"mock_orders/{year}/{month:02d}/{employee_id}"

    def create_employee(self, employee: Employee) -> Employee:
        """Mock: assigns a fake folder_id and returns the employee unchanged."""
        from dataclasses import replace
        return replace(employee, folder_id=f"mock_folder_{employee.employee_id}")

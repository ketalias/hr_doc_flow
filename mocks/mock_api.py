"""MockApiClient — stand-in for Andrii's api.drive module."""

from models import Employee, OrderType


class MockApiClient:
    """Simulates Drive operations without any network calls."""

    def get_templates(self) -> dict[str, str]:
        return {
            OrderType.HIRE.value:     "mock_template_hire",
            OrderType.VACATION.value: "mock_template_vacation",
            OrderType.DISMISS.value:  "mock_template_dismiss",
        }

    def create_order(
        self, template_id: str, employee: Employee, folder_path: str
    ) -> str:
        """Returns a fake Google Docs URL."""
        return (
            f"https://docs.google.com/document/d/"
            f"mock_{employee.employee_id}_{template_id}/edit"
        )

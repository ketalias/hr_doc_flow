import logging
from datetime import datetime


def setup_logger(log_file: str = "app.log") -> logging.Logger:
    """Налаштовує логер для запису дій системи у файл та консоль."""
    logger = logging.getLogger("hr_doc_flow")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Файловий обробник
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Консольний обробник
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def log_order_created(logger: logging.Logger, employee_name: str, template_name: str, doc_id: str):
    """Логує створення наказу."""
    logger.info(
        f"Створено документ: шаблон='{template_name}', "
        f"працівник='{employee_name}', doc_id='{doc_id}'"
    )


def log_order_failed(logger: logging.Logger, employee_name: str, template_name: str, error: str):
    """Логує невдалу генерацію наказу."""
    logger.error(
        f"Помилка генерації: шаблон='{template_name}', "
        f"працівник='{employee_name}', причина: {error}"
    )

"""
core/config.py — Configuration Manager.

Manages platform-specific application directory, interactive Setup Wizard
to obtain Google Drive Folder IDs/URLs, and loads/manages Google API credentials.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional

import questionary
from dotenv import load_dotenv, set_key
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ─── Config Directories & Files ──────────────────────────────────────────────

# Home-directory based configuration folder (~/.logicnest_hr or %APPDATA%\.logicnest_hr)
CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home()) / ".logicnest_hr"
ENV_PATH = CONFIG_DIR / ".env"
TOKEN_PATH = CONFIG_DIR / "token.json"
CREDS_PATH = CONFIG_DIR / "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

# Bundled Client Credentials for ТОВ «ЛоджікНест»
DEFAULT_CLIENT_CONFIG = {
    "installed": {
        "client_id": "59362188699-09m2vh4m2o8698t40c74ofpd4sbb5ihd.apps.googleusercontent.com",
        "project_id": "docflow-cli",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": ["http://localhost"]
    }
}


# ─── Helper Functions ────────────────────────────────────────────────────────

def extract_folder_id(input_str: str) -> str:
    """Extract folder ID if the user pasted a full Google Drive URL."""
    input_str = input_str.strip()
    match = re.search(r"folders/([a-zA-Z0-9-_]+)", input_str)
    if match:
        return match.group(1)
    return input_str


def run_setup_wizard() -> None:
    """Run an interactive wizard in the terminal to configure folder IDs."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ENV_PATH.touch(exist_ok=True)

    print("\n" + "=" * 60)
    print("=== Вітаємо в системі автоматизації ТОВ «ЛоджікНест» ===")
    print("Схоже, це ваш перший запуск або конфігурацію скинуто.")
    print("Будь ласка, вкажіть ID папок Google Drive (можна вставляти посилання повністю):\n")

    emp_input = questionary.text(
        "1. Папка працівників (Employees):",
        instruction="Вставте ID папки або повне посилання з браузера"
    ).ask()
    if not emp_input:
        print("Налаштування скасовано.")
        sys.exit(0)

    tmpl_input = questionary.text(
        "2. Папка шаблонів наказів (Templates):",
        instruction="Вставте ID папки або повне посилання з браузера"
    ).ask()
    if not tmpl_input:
        print("Налаштування скасовано.")
        sys.exit(0)

    orders_input = questionary.text(
        "3. Папка для збереження наказів (Orders):",
        instruction="Вставте ID папки або повне посилання з браузера"
    ).ask()
    if not orders_input:
        print("Налаштування скасовано.")
        sys.exit(0)

    # Clean IDs
    emp_id = extract_folder_id(emp_input)
    tmpl_id = extract_folder_id(tmpl_input)
    orders_id = extract_folder_id(orders_input)

    # Save to home .env
    set_key(str(ENV_PATH), "EMPLOYEES_FOLDER_ID", emp_id)
    set_key(str(ENV_PATH), "TEMPLATES_FOLDER_ID", tmpl_id)
    set_key(str(ENV_PATH), "ORDERS_FOLDER_ID", orders_id)
    set_key(str(ENV_PATH), "LOG_LEVEL", "INFO")

    print("\n[УСПІХ] Налаштування успішно збережено в домашній каталог!")
    print(f"Конфігураційний файл: {ENV_PATH}")
    print("=" * 60 + "\n")


import shutil

def _migrate_local_files_if_exist() -> bool:
    """
    Check if config files exist in the current working directory, and migrate
    them to the home profile directory so the user gets a seamless transition.
    Returns True if successfully migrated.
    """
    local_env = Path(".env")
    if local_env.exists():
        # Temporarily load to check if valid
        load_dotenv(local_env, override=True)
        if (
            os.getenv("EMPLOYEES_FOLDER_ID")
            and os.getenv("TEMPLATES_FOLDER_ID")
            and os.getenv("ORDERS_FOLDER_ID")
        ):
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(local_env, ENV_PATH)

            local_token = Path("token.json")
            if local_token.exists():
                shutil.copy(local_token, TOKEN_PATH)

            local_creds = Path("credentials.json")
            if local_creds.exists():
                shutil.copy(local_creds, CREDS_PATH)

            print(f"[INFO] Автоматично перенесено локальні налаштування у ваш профіль: {CONFIG_DIR}")
            return True
    return False


def ensure_config_loaded() -> None:
    """Ensure that the platform-specific config directory exists and variables are loaded."""
    # If the user profile config doesn't exist or is incomplete, launch wizard
    needs_setup = True
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)
        # Check if all required folder variables are loaded
        if (
            os.getenv("EMPLOYEES_FOLDER_ID")
            and os.getenv("TEMPLATES_FOLDER_ID")
            and os.getenv("ORDERS_FOLDER_ID")
        ):
            needs_setup = False

    if needs_setup:
        if not _migrate_local_files_if_exist():
            run_setup_wizard()
        load_dotenv(ENV_PATH, override=True)


def get_credentials() -> Credentials:
    """
    Get or authenticate Google OAuth credentials.
    Saves and loads token from user profile config folder (~/.logicnest_hr).
    Uses bundled Google App credentials if credentials.json is not found.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    creds: Optional[Credentials] = None

    # Try loading token from config directory
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            creds = None

    # If no token, or invalid, do flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        # If refresh failed or was not possible, do browser login
        if not creds:
            # Check for local credentials.json in config folder or project root
            if CREDS_PATH.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            elif Path("credentials.json").exists():
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            else:
                # Fallback to embedded credentials
                flow = InstalledAppFlow.from_client_config(DEFAULT_CLIENT_CONFIG, SCOPES)
            
            creds = flow.run_local_server(port=0)

        # Save credentials token
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds

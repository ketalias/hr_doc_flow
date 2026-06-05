# HR Doc Flow

> Automated HR document management system integrated with Google Workspace.

A Python 3.11+ CLI application that automates the creation of HR orders (hiring, vacation, dismissal) by copying Google Docs templates and substituting employee data — no manual copy-paste required.

---

## Architecture

The system is built from three independent, parallel-developed modules that communicate through a shared data contract (`models.py`):

```
┌──────────────────────────────────────────────────────────────────┐
│                          main.py (entry point)                   │
│                        Orchestrator (core/)                      │
│                    ┌──────────┴──────────┐                       │
│              api/  │                     │  data/                │
│           (Andrii) │                     │  (Misha)              │
│      ─────────────────────    ────────────────────────           │
│      Google Drive/Docs API    FS scanner + profile.json          │
└──────────────────────────────────────────────────────────────────┘
```

| Module | Developer | Responsibility |
|--------|-----------|----------------|
| `api/` | Andrii | Google Drive & Docs API: copy templates, replace `{{markers}}`, save to Drive |
| `data/` | Misha | Scan `Employees/` folders, parse `profile.json`, manage `Orders/` directory tree |
| `core/` | Roma | CLI (`questionary` + `rich`), structured logging, orchestration |

### Shared Data Contract — `models.py`

All three modules import from here. Changing these types requires team consensus.

```python
@dataclass
class Employee:
    employee_id: str
    last_name: str
    first_name: str
    ...

class OrderType(str, Enum):
    HIRE     = "hire"
    VACATION = "vacation"
    DISMISS  = "dismiss"
```

---

## Google Drive Structure

```
My Drive/
├── Employees/
│   └── Kovalenko Oleksiy (EMP001)/
│       ├── profile.json
│       └── documents/          ← personal docs (passport, contracts…)
├── Templates/
│   ├── Наказ_на_прийняття      ← Google Doc with {{field}} markers
│   ├── Наказ_на_звільнення
│   └── Наказ_на_відпустку
└── Orders/
    └── 2025/
        └── 06/
            └── EMP001/
                └── Наказ_про_прийняття_Коваленко.docx
```

---

## Installation

### Prerequisites

- Python 3.11+
- Google Cloud project with **Drive API** and **Docs API** enabled
- OAuth 2.0 Desktop credentials (`credentials.json`)

### Steps

```bash
# 1. Clone
git clone https://github.com/<your-org>/hr_doc_flow.git
cd hr_doc_flow

# 2. Virtual environment
python -m venv venv
source venv/bin/activate      # macOS / Linux
# venv\Scripts\activate       # Windows

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment variables
cp .env.example .env
# Open .env and paste your Google Drive folder IDs

# 5. OAuth credentials
# Download credentials.json from Google Cloud Console → APIs & Services → Credentials
# Place credentials.json in the project root (it is git-ignored)

# 6. Run
python main.py
```

### First Run (OAuth)

On the very first launch the app opens a browser window for Google OAuth consent.
After approving, `token.json` is written to the project root and reused automatically.

---

## Configuration

```env
# .env — copy from .env.example and fill in your IDs
# Folder IDs are found in the Drive URL:
# https://drive.google.com/drive/folders/<FOLDER_ID>

EMPLOYEES_FOLDER_ID=
TEMPLATES_FOLDER_ID=
ORDERS_FOLDER_ID=
LOG_LEVEL=INFO
```

---

## CLI Usage

```
╭────────────────────────────────────────────────────────╮
│                      HR DOC FLOW                       │
│     Система автоматизованого кадрового документообігу  │
╰────────────────────────────────────────────────────────╯

? Оберіть дію:
  ❯ 📋  Список працівників
    📄  Створити наказ
    🔍  Знайти працівника
    ──────────────────────────────
    🚪  Вихід
```

Keyboard: `↑↓` to navigate, `Enter` to select, `Ctrl+C` to cancel.

---

## Running Without Google Credentials (Mock Mode)

The app falls back to built-in mock data when `api/` or `data/` modules are not yet implemented. This lets Roma develop and test the UI independently:

```bash
python main.py          # mock mode auto-detected
```

---

## Project Structure

```
hr_doc_flow/
├── api/                    # Andrii — Google Drive/Docs API
│   ├── __init__.py
│   └── drive.py
├── data/                   # Misha — FS scanner & directory manager
│   ├── __init__.py
│   └── scanner.py
├── core/                   # Roma — UI, logging, orchestration
│   ├── __init__.py
│   ├── logger.py           # Rich RichHandler + file handler
│   ├── ui.py               # All questionary menus + Rich display helpers
│   └── orchestrator.py     # Business logic coordinator
├── mocks/                  # Stand-ins until api/ and data/ are ready
│   ├── mock_api.py
│   └── mock_data.py
├── logs/                   # Auto-created at runtime (git-ignored)
├── models.py               # Shared data contract: Employee, OrderType
├── main.py                 # Entry point — wires modules, drives menu loop
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Logs

Runtime logs are written to `logs/hr_doc_flow.log` (plain text, UTF-8) and
printed to the terminal via Rich at `INFO` level. Set `LOG_LEVEL=DEBUG` in `.env`
for verbose output.

---

## Team

| Developer | Module | Role |
|-----------|--------|------|
| Andrii | `api/` | Google Workspace integration |
| Misha | `data/` | Data management & local FS |
| Roma | `core/`, `main.py` | UI, logging, orchestration |

---

> Python 3.11 · Google Workspace APIs · [questionary](https://github.com/tmbo/questionary) · [rich](https://github.com/Textualize/rich) · python-dotenv

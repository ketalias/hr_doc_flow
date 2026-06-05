import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError  # Додано для перехоплення помилок API
from models import Employee, get_employee_mock

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

SERVICE_ACCOUNT_FILE = 'credentials.json'

# --- 1. АВТОРИЗАЦІЯ ---
def authenticate_google_services():
    """Авторизує користувача через браузер та зберігає сесію."""
    creds = None
    
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                SERVICE_ACCOUNT_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    try:
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        print("Успішна авторизація в Google API!")
        return drive_service, docs_service
    except Exception as e:
        print(f"Помилка при створенні клієнтів API: {e}")
        return None, None


def copy_template(drive_service, template_id, destination_folder_id, new_file_name):
    """Створює копію шаблону у вказаній папці з обробкою помилок."""
    body = {
        'name': new_file_name,
        'parents': [destination_folder_id]
    }
    
    try:
        # Виконуємо запит до API Диску на копіювання
        new_file = drive_service.files().copy(
            fileId=template_id,
            body=body,
            fields='id'
        ).execute()
        return new_file.get('id')
        
    except HttpError as error:
        print(f"Помилка API при копіюванні шаблону: {error}")
        return None
    except Exception as e:
        print(f"Неочікувана помилка при роботі з Google Drive: {e}")
        return None


def fill_document(docs_service, document_id, employee):
    """Замінює маркери в документі на реальні дані працівника з обробкою помилок."""
    template_data = employee.to_template_dict()
    requests = [
        {
            'replaceAllText': {
                'containsText': {'text': marker, 'matchCase': True},
                'replaceText': value,
            }
        }
        for marker, value in template_data.items()
    ]

    try:
        # Відправляємо одним пакетом (batch) всі зміни в документ
        docs_service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()
        return True
        
    except HttpError as error:
        print(f"Помилка API при заповненні документа: {error}")
        return False
    except Exception as e:
        print(f"Неочікувана помилка при роботі з Google Docs: {e}")
        return False


def generate_order(drive_service, docs_service, employee, template_id, dest_folder_id):
    """Головна функція: копіює шаблон і заповнює його даними."""
    
    doc_name = f"Наказ_{employee.last_name}_{employee.first_name}"
    print(f"\nПочинаємо генерацію документа для: {employee.full_name}...")
    
    # Крок 1: Копіюємо файл
    new_doc_id = copy_template(drive_service, template_id, dest_folder_id, doc_name)
    
    # Якщо копіювання не вдалося, зупиняємо процес
    if not new_doc_id:
        print("Генерацію скасовано: не вдалося створити файл.")
        return None
        
    # Крок 2: Заповнюємо даними
    success = fill_document(docs_service, new_doc_id, employee)
    
    # Якщо заповнення не вдалося, повідомляємо, але повертаємо ID створеного (порожнього) файлу
    if not success:
        print(f"Увага! Документ (ID: {new_doc_id}) створено, але виникли помилки при заповненні тексту.")
        return new_doc_id
    
    print(f"Документ успішно створено та заповнено! ID: {new_doc_id}")
    return new_doc_id
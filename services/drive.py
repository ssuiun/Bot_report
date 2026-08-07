"""
Загрузка файлов (фото чеков) в Google Drive через тот же сервисный аккаунт,
что используется для Google Sheets (services/sheets.py).

Файл заливается в папку GOOGLE_DRIVE_FOLDER_ID (если задана в .env), становится
доступным по ссылке на просмотр (без права редактирования), и возвращается
постоянная ссылка — она и сохраняется в столбце "Ссылка на чек/фото" в Google Sheets.

Как и в services/sheets.py, все обращения к Google API — синхронные (googleapiclient),
поэтому выполняются в отдельном потоке через asyncio.to_thread.
"""
import asyncio
import io

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_DRIVE_FOLDER_ID

_SCOPES = ["https://www.googleapis.com/auth/drive"]

_service = None


def _get_service():
    global _service
    if _service is None:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=_SCOPES)
        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _service


def _upload_sync(file_bytes: bytes, filename: str, mime_type: str) -> str:
    service = _get_service()

    metadata = {"name": filename}
    if GOOGLE_DRIVE_FOLDER_ID:
        metadata["parents"] = [GOOGLE_DRIVE_FOLDER_ID]

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    uploaded = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )
    file_id = uploaded["id"]

    # Открываем доступ на просмотр по ссылке любому, у кого есть ссылка
    # (без этого сотрудники/админ не смогут открыть файл — по умолчанию доступ
    # есть только у самого сервисного аккаунта).
    try:
        service.permissions().create(
            fileId=file_id, body={"role": "reader", "type": "anyone"}
        ).execute()
    except Exception:
        pass

    # Прямая CDN-ссылка на файл — именно её идеально распознает формула =IMAGE() в Google Sheets
    return f"https://lh3.googleusercontent.com/d/{file_id}"


async def upload_photo(file_bytes: bytes, filename: str, mime_type: str = "image/jpeg") -> str:
    """Возвращает прямую ссылку на файл, пригодную для формулы =IMAGE(...)."""
    return await asyncio.to_thread(_upload_sync, file_bytes, filename, mime_type)

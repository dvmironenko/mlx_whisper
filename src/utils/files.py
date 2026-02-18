"""Утилиты для работы с файлами."""
import os
import uuid
from typing import Optional

from src.config import MAX_FILE_SIZE, CHUNK_SIZE


def generate_unique_filename(original_filename: str) -> str:
    """Сгенерировать уникальное имя файла."""
    ext = os.path.splitext(original_filename)[1]
    return f"{uuid.uuid4()}{ext}"


def validate_file_size(file_path: str) -> bool:
    """Проверить размер файла."""
    return os.path.getsize(file_path) <= MAX_FILE_SIZE


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Проверить расширение файла."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed_extensions


def chunked_read(file_path: str, chunk_size: int = CHUNK_SIZE):
    """Читать файл порциями."""
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


def delete_file(file_path: str) -> bool:
    """Удалить файл. Вернуть True если успешно."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception:
        pass
    return False


def cleanup_old_files(directory: str, days: int = 30) -> int:
    """Удалить файлы старше N дней. Вернуть количество удаленных."""
    import time
    from datetime import datetime, timedelta

    now = time.time()
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()

    count = 0
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path) and os.stat(file_path).st_mtime < cutoff:
            delete_file(file_path)
            count += 1
    return count

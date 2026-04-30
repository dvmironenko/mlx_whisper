"""Утилиты для скачивания видео/аудио по URL."""
import os
import re
import subprocess
from urllib.parse import urlparse
from typing import Optional

from src.config import logger, MAX_FILE_SIZE, CONVERSION_TIMEOUT_SECONDS

# Белый список доменов (без www - проверяется отдельно)
ALLOWED_URL_DOMAINS = [
    "youtube.com",
    "youtu.be",
    "vimeo.com",
]


def _get_base_domain(hostname: str) -> str:
    """Извлечь базовый домен из hostname (убирает www)."""
    hostname = hostname.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname

# Разрешённые протоколы
ALLOWED_PROTOCOLS = ["http", "https"]


def validate_url(url: str) -> bool:
    """
    Валидация URL для безопасности.

    Проверяет:
    - Протокол (только http/https)
    - Домен (только из белого списка)
    - Отсутствие опасных паттернов

    Parameters
    ----------
    url : str
        URL для валидации

    Returns
    -------
    bool
        True если URL валиден, False иначе
    """
    try:
        parsed = urlparse(url)

        # Проверка протокола
        if parsed.scheme not in ALLOWED_PROTOCOLS:
            logger.warning(f"Blocked URL with protocol '{parsed.scheme}': {url}")
            return False

        # Проверка домена
        hostname = parsed.hostname
        if hostname:
            hostname_lower = hostname.lower()
            base_domain = _get_base_domain(hostname_lower)

            # Разрешаем прямые ссылки (без домена из списка)
            # или домены из белого списка
            if base_domain not in ALLOWED_URL_DOMAINS:
                # Проверяем, не прямая ли это ссылка на файл
                path = parsed.path.lower()
                allowed_extensions = ['.mp4', '.webm', '.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.oga', '.weba']
                if not any(path.endswith(ext) for ext in allowed_extensions):
                    logger.warning(f"Blocked URL with non-whitelisted domain: {url}")
                    return False

        # Блокировка опасных паттернов
        if re.search(r'[<>"\x00-\x1F]', url):
            logger.warning(f"Blocked URL with dangerous characters: {url}")
            return False

        return True
    except Exception as e:
        logger.error(f"URL validation error for {url}: {e}")
        return False


def get_url_format(url: str) -> str:
    """
    Определить тип контента по URL.

    Parameters
    ----------
    url : str
        URL для анализа

    Returns
    -------
    str
        Тип контента: 'youtube', 'vimeo', 'direct', 'unknown'
    """
    parsed = urlparse(url)
    hostname = parsed.hostname.lower() if parsed.hostname else ""

    if 'youtube' in hostname or 'youtu.be' in hostname:
        return 'youtube'
    elif 'vimeo' in hostname:
        return 'vimeo'
    elif parsed.path:
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext in ['.mp4', '.webm', '.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.oga', '.weba']:
            return 'direct'

    return 'unknown'


def download_from_url(url: str, output_path: str, max_size: Optional[int] = None) -> str:
    """
    Скачать видео/аудио по URL через yt-dlp.

    Parameters
    ----------
    url : str
        URL видео/аудио
    output_path : str
        Путь для сохранения скачанного файла
    max_size : int
        Максимальный размер файла в байтах (по умолчанию из config)

    Returns
    -------
    str
        Путь к скачанному файлу

    Raises
    ------
    HTTPException
        При ошибках скачивания
    """
    if max_size is None:
        max_size = MAX_FILE_SIZE

    if not validate_url(url):
        raise ValueError("Invalid URL")

    logger.info(f"Downloading from URL: {url}")

    # yt-dlp команды
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=mp3]/best[ext=mp4]/best",
        "-o", output_path,
        "--no-warnings",
        "--no-progress",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        url,
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=CONVERSION_TIMEOUT_SECONDS,
        )

        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Downloaded file not found: {output_path}")

        # Проверка размера
        size = os.path.getsize(output_path)
        if size > max_size:  # type: ignore
            os.remove(output_path)
            raise ValueError(f"File too large: {size} bytes (max: {max_size})")

        logger.info(f"Downloaded file: {output_path}, size: {size} bytes")
        return output_path

    except subprocess.TimeoutExpired as e:
        logger.error(f"Download timed out for {url}: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"Download timed out after {CONVERSION_TIMEOUT_SECONDS} seconds")

    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp error for {url}: {e.stderr.decode() if e.stderr else str(e)}")
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"Download failed: {e.stderr.decode() if e.stderr else str(e)}")

    except FileNotFoundError as e:
        logger.error(f"yt-dlp not found: {e}")
        raise RuntimeError("yt-dlp not found. Please install: pip install yt-dlp")


def get_yt_dlp_version() -> Optional[str]:
    """Получить версию yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.decode().strip()
    except Exception:
        pass
    return None

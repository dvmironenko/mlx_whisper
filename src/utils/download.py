"""Утилиты для скачивания видео/аудио по URL."""
import os
import re
import shutil
import subprocess
from urllib.parse import urlparse
from typing import Optional

from src.config import logger, MAX_FILE_SIZE, CONVERSION_TIMEOUT_SECONDS, ALLOWED_URL_DOMAINS


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


def download_from_url(
    url: str,
    output_path: str,
    max_size: Optional[int] = None,
    extract_title: bool = True,
) -> tuple:
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
    extract_title : bool
        Извлечь название видео из метаданных (по умолчанию True)

    Returns
    -------
    tuple[str, Optional[str]]
        (путь к скачанному файлу, название видео)
        название видео — None, если извлечение не удалось или отключено.

    Raises
    ------
    ValueError
        При ошибках скачивания
    """
    if max_size is None:
        max_size = MAX_FILE_SIZE

    if not validate_url(url):
        raise ValueError("Invalid URL")

    logger.info(f"Downloading from URL: {url}")

    # Resolve yt-dlp to absolute path to avoid PATH issues in spawned processes
    yt_dlp_path = shutil.which("yt-dlp")
    if not yt_dlp_path:
        raise RuntimeError("yt-dlp not found. Please install: pip install yt-dlp")

    # yt-dlp appends its own extension to the -o path, so we pass the directory
    # and a template, then find the actual file afterward.
    output_dir = os.path.dirname(output_path) or "."
    yt_output_template = os.path.join(output_dir, "downloaded.%(ext)s")

    # yt-dlp команды — скачиваем оригинальный аудиоформат,
    # конвертацию в WAV и удаление тишины делает convert_to_wav()
    cmd = [
        yt_dlp_path,
        "--no-simulate",
    ]
    if extract_title:
        cmd.extend(["--print", "title"])
    cmd.extend([
        "-f", "bestaudio",
        "-o", yt_output_template,
        "--no-warnings",
        "--no-progress",
        "--extract-audio",
        url,
    ])

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=CONVERSION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as e:
        logger.error(f"Download timed out for {url}: {e}")
        _cleanup_yt_dlp_output(output_dir)
        raise RuntimeError(f"Download timed out after {CONVERSION_TIMEOUT_SECONDS} seconds")

    except subprocess.CalledProcessError as e:
        stderr_text = e.stderr.decode() if e.stderr else "(no stderr)"
        logger.error(f"yt-dlp error for {url}: {stderr_text[:1000]}")
        _cleanup_yt_dlp_output(output_dir)
        raise RuntimeError(f"yt-dlp failed: {stderr_text[:500]}")

    # Extract title from first line of stdout
    video_title = None
    if extract_title and result.stdout:
        try:
            stdout_text = result.stdout.decode("utf-8", errors="replace").strip()
            first_line = stdout_text.split("\n")[0].strip()
            if first_line:
                video_title = first_line
        except Exception as e:
            logger.warning(f"Title extraction failed: {e}")

    # Find the actual downloaded file (yt-dlp appends its own extension)
    downloaded_file = _find_yt_dlp_output(output_dir)
    if not downloaded_file:
        logger.error(f"No audio file found in {output_dir} after download")
        raise RuntimeError(f"yt-dlp did not produce any audio file in {output_dir}")

    # Проверка размера
    size = os.path.getsize(downloaded_file)
    if size > max_size:  # type: ignore
        os.remove(downloaded_file)
        raise ValueError(f"File too large: {size} bytes (max: {max_size})")

    logger.info(f"Downloaded file: {downloaded_file}, size: {size} bytes")
    return (downloaded_file, video_title)


def _cleanup_yt_dlp_output(output_dir: str) -> None:
    """Удалить все файлы, созданные yt-dlp в директории."""
    if os.path.isdir(output_dir):
        for f in os.listdir(output_dir):
            filepath = os.path.join(output_dir, f)
            if os.path.isfile(filepath):
                os.remove(filepath)


def _find_yt_dlp_output(output_dir: str) -> Optional[str]:
    """Найти файл, созданный yt-dlp, в директории."""
    audio_extensions = {".opus", ".webm", ".m4a", ".mp4", ".weba", ".flac", ".aac", ".ogg", ".wav", ".mp3"}
    if os.path.isdir(output_dir):
        for f in os.listdir(output_dir):
            ext = os.path.splitext(f)[1].lower()
            if ext in audio_extensions:
                return os.path.join(output_dir, f)
    return None


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

"""Конфигурация приложения через environment variables."""

from dotenv import load_dotenv
import os

# Загружаем переменные из .env файла (ищем в родительской директории)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

import logging
from typing import Optional
from logging.handlers import RotatingFileHandler

# Server settings
HOST: str = os.getenv("MLX_WHISPER_HOST", "0.0.0.0")
PORT: int = int(os.getenv("MLX_WHISPER_PORT", "8801"))
DEBUG: bool = os.getenv("MLX_WHISPER_DEBUG", "false").lower() == "true"

# Audio processing
MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE_MB", "500")) * 1024 * 1024
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE_KB", "8")) * 1024

# FFmpeg timeouts
CONVERSION_TIMEOUT_SECONDS: int = int(os.getenv("CONVERSION_TIMEOUT", "600"))
TRANSCRIPTION_TIMEOUT_SECONDS: int = int(os.getenv("TRANSCRIPTION_TIMEOUT", "3600"))

# Models path
MODELS_DIR: str = os.getenv("MODELS_DIR", "models")

# Results storage
RESULTS_DIR: str = os.getenv("RESULTS_DIR", "results")
RESULTS_RETENTION_DAYS: int = int(os.getenv("RESULTS_RETENTION_DAYS", "30"))

# User uploads storage
DATA_UPLOADS_DIR: str = "data"
os.makedirs(DATA_UPLOADS_DIR, exist_ok=True)

# Auth
API_KEY: Optional[str] = os.getenv("MLX_WHISPER_API_KEY")

# Logging
LOGS_DIR: str = os.getenv("LOGS_DIR", "logs")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Initial prompt for context-aware transcription (optional)
INITIAL_PROMPT: Optional[str] = os.getenv("INITIAL_PROMPT", None)

# Silence removal settings
REMOVE_SILENCE: bool = os.getenv("REMOVE_SILENCE", "true").lower() == "true"
SILENCE_THRESHOLD: float = float(os.getenv("SILENCE_THRESHOLD", "-45.0"))
SILENCE_DURATION: float = float(os.getenv("SILENCE_DURATION", "1.0"))

# Default language for transcription (empty string for auto-detect)
DEFAULT_LANGUAGE: Optional[str] = os.getenv("DEFAULT_LANGUAGE", None)

# Default model for transcription
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "turbo")

# Transcription thresholds
NO_SPEECH_THRESHOLD: float = float(os.getenv("NO_SPEECH_THRESHOLD", "0.4"))
HALLUCINATION_SILENCE_THRESHOLD: float = float(os.getenv("HALLUCINATION_SILENCE_THRESHOLD", "0.8"))

# OpenAI API settings for report generation
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL", None)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_REPORT_PROMPT: Optional[str] = os.getenv(
    "OPENAI_REPORT_PROMPT",
    "Создать отчет о сессии. Отчет должен содержать все фразы спикеров в формате: [Спикер:] [Высказывание]"
)

# Report generation chunk size (for large texts)
MAX_REPORT_CHUNK_SIZE: int = int(os.getenv("MAX_REPORT_CHUNK_SIZE", "10000"))

# OMLX / VibeVoice Configuration
OMLX_BASE_URL: str = os.getenv("OMLX_BASE_URL", "")
OMLX_MODEL: str = os.getenv("OMLX_MODEL", "VibeVoice-ASR-4bit")
OMLX_API_KEY: Optional[str] = os.getenv("OMLX_API_KEY") or None
OMLX_ENABLED: bool = os.getenv("OMLX_ENABLED", "true").lower() == "true"


def omlx_available() -> bool:
    """Check if oMLX is configured and enabled."""
    if not OMLX_ENABLED:
        return False
    return bool(OMLX_BASE_URL)

# URL download settings
ALLOWED_URL_DOMAINS_STR: str = os.getenv("ALLOWED_URL_DOMAINS", "youtube.com,youtu.be,vimeo.com")
ALLOWED_URL_DOMAINS: list = [d.strip() for d in ALLOWED_URL_DOMAINS_STR.split(",") if d.strip()]
MAX_DOWNLOAD_SIZE: int = int(os.getenv("MAX_DOWNLOAD_SIZE_MB", "2048")) * 1024 * 1024
DOWNLOAD_TIMEOUT: int = int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "600"))

# Transcription queue settings
TRANSCRIBER_WORKERS: int = int(os.getenv("TRANSCRIBER_WORKERS", "3"))
QUEUE_MAX_SIZE: int = int(os.getenv("QUEUE_MAX_SIZE", "20"))

# Audio extensions
AUDIO_EXTENSIONS: set = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".aac",
    ".ogg",
    ".wma",
    ".webm",
    ".mp4",
    ".mkv",
}

# Supported models
SUPPORTED_MODELS: dict = {
    "tiny": "models/whisper-tiny",
    "base": "models/whisper-base",
    "small": "models/whisper-small",
    "medium": "models/whisper-medium",
    "turbo": "models/whisper-turbo",
    "large": "models/whisper-large",
}

# Create logs directory if not exists
os.makedirs(LOGS_DIR, exist_ok=True)

# Create uploads directory if not exists
UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Create formatter
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

# Create logger
logger = logging.getLogger("mlx_whisper")
logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# File handler (rotating 10MB, keep 5 files)
file_handler = RotatingFileHandler(
    os.path.join(LOGS_DIR, "app.log"),
    maxBytes=10 * 1024 * 1024,
    backupCount=5
)
file_handler.setLevel(getattr(logging, LOG_LEVEL.upper()))
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Error handler
error_handler = RotatingFileHandler(
    os.path.join(LOGS_DIR, "error.log"),
    maxBytes=10 * 1024 * 1024,
    backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)


def log_transcription_result(
    filename: str,
    model: str,
    language: Optional[str],
    task: str,
    audio_duration: Optional[float],
    convert_duration: Optional[float],
    transcribe_duration: float,
    total_duration: float,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """
    Логировать результат транскрипции.

    Parameters
    ----------
    filename: str
        Имя загруженного файла
    model: str
        Использованная модель
    language: Optional[str]
        Язык транскрипции (или None для auto-detect)
    task: str
        Тип задачи (transcribe/translate)
    audio_duration: Optional[float]
        Длительность аудио в секундах
    convert_duration: Optional[float]
        Время конвертации в секундах
    transcribe_duration: float
        Время транскрипции в секундах
    total_duration: float
        Общее время обработки в секундах
    success: bool
        Успешность завершения
    error: Optional[str]
        Описание ошибки (если есть)
    """
    if success:
        logger.info(
            f"Transcription completed: file={filename}, model={model}, "
            f"task={task}, language={language or 'auto'}, audio_duration={audio_duration:.2f}s, "
            f"convert_time={convert_duration:.2f}s, transcribe_time={transcribe_duration:.2f}s, "
            f"total_time={total_duration:.2f}s"
        )
    else:
        logger.error(
            f"Transcription failed: file={filename}, model={model}, "
            f"task={task}, language={language or 'auto'}, error={error}"
        )

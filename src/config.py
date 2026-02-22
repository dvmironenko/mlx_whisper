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

# Auth
API_KEY: Optional[str] = os.getenv("MLX_WHISPER_API_KEY")

# Logging
LOGS_DIR: str = os.getenv("LOGS_DIR", "logs")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Initial prompt for context-aware transcription (optional)
INITIAL_PROMPT: Optional[str] = os.getenv("INITIAL_PROMPT", None)

# Silence removal settings
REMOVE_SILENCE: bool = os.getenv("REMOVE_SILENCE", "true").lower() == "true"
SILENCE_THRESHOLD: float = float(os.getenv("SILENCE_THRESHOLD", "-60.0"))
SILENCE_DURATION: float = float(os.getenv("SILENCE_DURATION", "0.5"))

# Default language for transcription (empty string for auto-detect)
DEFAULT_LANGUAGE: Optional[str] = os.getenv("DEFAULT_LANGUAGE", None)

# Transcription thresholds
NO_SPEECH_THRESHOLD: float = float(os.getenv("NO_SPEECH_THRESHOLD", "0.4"))
HALLUCINATION_SILENCE_THRESHOLD: float = float(os.getenv("HALLUCINATION_SILENCE_THRESHOLD", "0.8"))

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
file_handler.setLevel(logging.INFO)
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

"""Утилиты для работы с аудио."""
import os
import subprocess
import logging
from typing import Optional

from src.config import CONVERSION_TIMEOUT_SECONDS, CHUNK_SIZE

logger = logging.getLogger("mlx_whisper")


def convert_to_wav(input_path: str, output_path: str, remove_silence: bool = True, silence_threshold: float = -45.0, silence_duration: float = 1.0) -> bool:
    """Конвертировать аудио в WAV формат (16kHz, mono)."""
    # Если нужно удалять тишину, используем фильтры FFmpeg
    if remove_silence:
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-acodec", "pcm_s16le",
            "-ar", "32000",
            "-ac", "1",
            "-af", f"silenceremove=stop_periods=-1:stop_duration={silence_duration}:stop_threshold={silence_threshold}dB",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-acodec", "pcm_s16le",
            "-ar", "32000",
            "-ac", "1",
            output_path,
        ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=CONVERSION_TIMEOUT_SECONDS,
        )
        return result.returncode == 0 and os.path.exists(output_path)
    except subprocess.TimeoutExpired as e:
        logger.error(f"Audio conversion timed out for {input_path}: {e}")
        raise RuntimeError(f"Conversion timed out after {CONVERSION_TIMEOUT_SECONDS} seconds")
    except FileNotFoundError as e:
        logger.error(f"FFmpeg not found for conversion of {input_path}: {e}")
        raise RuntimeError("FFmpeg not found. Please install ffmpeg.")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion failed for {input_path}: {e.stderr.decode()}")
        raise RuntimeError(f"FFmpeg conversion failed: {e.stderr.decode()}")


def validate_audio_file(file_path: str) -> bool:
    """Проверить, является ли файл валидным аудиофайлом."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        return result.returncode == 0 and float(result.stdout) > 0
    except Exception:
        return False


def get_audio_duration(file_path: str) -> Optional[float]:
    """Получить длительность аудиофайла в секундах."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if result.returncode == 0:
            return float(result.stdout)
    except Exception:
        pass
    return None

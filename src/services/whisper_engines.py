"""Абстракция механизмов транскрибации: TranscriptionEngine ABC + WhisperEngine."""

import gc
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict

import mlx.core as mx

from src.config import logger
from src.models.model_cache import ModelCache
from src.utils.audio import get_audio_duration

# Import mlx_whisper.transcribe
try:
    from mlx_whisper.transcribe import transcribe as _mlx_transcribe
except ImportError:
    raise ImportError("mlx-whisper package is required. Install it with: pip install mlx-whisper")


class TranscriptionEngine(ABC):
    """Абстрактный базовый класс для механизмов транскрибации."""

    @abstractmethod
    def transcribe(self, file_path: str, **params) -> Dict[str, Any]:
        """
        Транскрибировать аудиофайл.

        Parameters
        ----------
        file_path : str
            Путь к аудиофайлу
        **params
            Параметры транскрипции (language, model, task и др.)

        Returns
        -------
        dict
            Нормализованный результат:
            {
                "segments": [...],
                "text": str,
                "speaker_detected": bool,
                "transcription_duration": float,
                "raw_response": str | None,  # optional: сырой ответ API
            }
        """


class WhisperEngine(TranscriptionEngine):
    """Механизм транскрибации на основе MLX Whisper."""

    MODEL_MAPPING = {
        "tiny": "models/whisper-tiny",
        "base": "models/whisper-base",
        "small": "models/whisper-small",
        "medium": "models/whisper-medium",
        "turbo": "models/whisper-turbo",
        "large": "models/whisper-large",
    }

    def transcribe(self, file_path: str, **params) -> Dict[str, Any]:
        """Выполнить транскрипцию через MLX Whisper."""
        model = params.get("model", "large")
        language = params.get("language")
        task = params.get("task", "transcribe")
        word_timestamps = params.get("word_timestamps", False)
        condition_on_previous_text = params.get("condition_on_previous_text", True)
        no_speech_threshold = params.get("no_speech_threshold")
        hallucination_silence_threshold = params.get("hallucination_silence_threshold")
        initial_prompt = params.get("initial_prompt")
        include_timestamps = params.get("include_timestamps", True)

        # Resolve model path
        models_dir = os.getenv("MODELS_DIR", "models")
        model_path = self.MODEL_MAPPING.get(model, os.path.join(models_dir, f"whisper-{model}"))

        if not os.path.exists(model_path):
            model_path = f"mlx-community/whisper-{model}"

        # Load from cache
        cache = ModelCache.get_instance()
        cached_model = cache.get_model(model)
        if cached_model is None:
            cache.load_model(model, model_path)

        # Get audio duration
        try:
            audio_duration = get_audio_duration(file_path)
        except Exception as e:
            logger.error(f"Failed to get audio duration for {file_path}: {e}")
            audio_duration = None

        # Prepare options
        transcribe_options: Dict[str, Any] = {
            "language": language,
            "task": task,
            "word_timestamps": word_timestamps,
            "condition_on_previous_text": condition_on_previous_text,
        }
        if no_speech_threshold is not None:
            transcribe_options["no_speech_threshold"] = no_speech_threshold
        if hallucination_silence_threshold is not None:
            transcribe_options["hallucination_silence_threshold"] = hallucination_silence_threshold
        if initial_prompt is not None:
            transcribe_options["initial_prompt"] = initial_prompt

        # Execute transcription
        start_time = time.time()
        try:
            result = _mlx_transcribe(
                audio=file_path,
                path_or_hf_repo=model_path,
                **transcribe_options,
            )
        except Exception as e:
            logger.error(f"Transcription failed for {file_path}: {e}")
            raise

        transcribe_duration = time.time() - start_time
        result["transcribe_duration"] = transcribe_duration  # type: ignore[assignment]
        if audio_duration is not None:
            result["audio_duration"] = audio_duration  # type: ignore[assignment]

        # Save raw response before normalization
        raw_json = None
        try:
            raw_json = json.dumps(result, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            logger.warning("Failed to serialize Whisper raw response")

        # Форматируем текст из сегментов: [MM:SS]: Текст
        segments = result.get("segments")
        if not isinstance(segments, list):
            segments = []
        formatted_text = _build_formatted_text_from_segments(
            segments, include_timestamps=include_timestamps
        )

        # Normalize to unified format
        return {
            "segments": result.get("segments", []),
            "text": formatted_text,
            "speaker_detected": False,
            "transcription_duration": round(transcribe_duration, 2),
            "raw_response": raw_json,
        }


def _build_formatted_text_from_segments(
    segments: list[dict],
    *,
    include_speaker: bool = False,
    include_timestamps: bool = True,
) -> str:
    """Собрать текст из сегментов.

    При include_timestamps=True — формат [MM:SS]: Текст.
    При include_timestamps=False — только текст, без префикса.
    """
    lines: list[str] = []
    for seg in segments:
        start = seg.get("start", 0)
        speaker = seg.get("speaker", 0)
        text = seg.get("text", "").strip()
        if not text:
            continue
        if include_timestamps:
            minutes = int(start) // 60
            seconds = int(start) % 60
            if include_speaker:
                lines.append(f"[{minutes:02d}:{seconds:02d}] Спикер {speaker} : {text}")
            else:
                lines.append(f"[{minutes:02d}:{seconds:02d}]: {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def get_engine(mechanism: str = "vibevoice") -> TranscriptionEngine:
    """Получить механизм транскрибации по имени."""
    if mechanism == "vibevoice":
        from src.services.vibevoice_engine import VibeVoiceEngine

        return VibeVoiceEngine()
    return WhisperEngine()


# Backward-compatibility wrapper
def transcribe_audio(file_path: str, **params) -> Dict[str, Any]:
    """Обратная совместимость: обёртка над WhisperEngine."""
    engine = WhisperEngine()
    return engine.transcribe(file_path, **params)


def _clear_memory() -> None:
    """Очистить кэш MLX и запустить сборку мусора Python."""
    mx.clear_cache()
    gc.collect()
    logger.debug("Memory cleared")


# Referenced by transcription_queue.py via: _transcription_module._clear_memory()

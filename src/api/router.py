"""FastAPI роуты для API."""
import math
import os
import time
import uuid
from fastapi import APIRouter, UploadFile, Form, HTTPException
from typing import Optional


def sanitize_floats(value):
    """Заменить NaN и Infinity на None для JSON-совместимости."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def sanitize_result(result: dict) -> dict:
    """Рекурсивно заменить NaN и Infinity в словаре."""
    sanitized = {}
    for key, value in result.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_result(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_result(item) if isinstance(item, dict) else sanitize_floats(item)
                for item in value
            ]
        else:
            sanitized[key] = sanitize_floats(value)
    return sanitized
from typing import Optional

from src.config import AUDIO_EXTENSIONS, SUPPORTED_MODELS, CHUNK_SIZE, LANGUAGE, NO_SPEECH_THRESHOLD, HALLUCINATION_SILENCE_THRESHOLD, REMOVE_SILENCE, SILENCE_THRESHOLD, SILENCE_DURATION, logger, log_transcription_result
from src.models.transcription import transcribe_audio
from src.utils.audio import convert_to_wav, get_audio_duration
from src.utils.files import generate_unique_filename, delete_file, validate_file_extension

router = APIRouter(prefix="/api/v1", tags=["transcription"])


@router.post("/transcribe")
async def transcribe_audio_endpoint(
    file: UploadFile,
    language: Optional[str] = Form(None),
    task: str = Form("transcribe"),
    model: str = Form("large"),
    word_timestamps: str = Form("false"),
    condition_on_previous_text: str = Form("true"),
    no_speech_threshold: Optional[str] = Form(None),
    hallucination_silence_threshold: Optional[str] = Form(None),
    initial_prompt: Optional[str] = Form(None),
    remove_silence: str = Form(None),  # Используем None для определения, что параметр не задан
    silence_threshold: str = Form(None),
    silence_duration: str = Form(None),
):
    """Транскрибировать аудиофайл."""

    # Валидация расширения
    if file.filename is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )

    if not validate_file_extension(file.filename, AUDIO_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format. Supported: {', '.join(AUDIO_EXTENSIONS)}"
        )

    # Валидация модели
    if model not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model. Supported: {', '.join(SUPPORTED_MODELS.keys())}"
        )

    # Обработка параметров, если они не были переданы (значения из .env)
    # Если передано дефолтное значение, используем значение из .env (если задано)
    task_value = task
    if task == "transcribe":
        task_value = os.getenv("TASK", "transcribe")

    model_value = model
    if model == "large":
        model_value = os.getenv("MODEL", "large")

    word_timestamps_value = word_timestamps.lower() == "true"
    if word_timestamps == "false":
        word_timestamps_value = os.getenv("WORD_TIMESTAMPS", "false").lower() == "true"

    condition_on_previous_text_value = condition_on_previous_text.lower() == "true"
    if condition_on_previous_text == "true":
        condition_on_previous_text_value = os.getenv("CONDITION_ON_PREVIOUS", "true").lower() == "true"

    remove_silence_value = REMOVE_SILENCE if remove_silence is None else remove_silence.lower() == "true"
    silence_threshold_value = SILENCE_THRESHOLD if silence_threshold is None else float(silence_threshold)
    silence_duration_value = SILENCE_DURATION if silence_duration is None else float(silence_duration)
    no_speech_threshold_value = NO_SPEECH_THRESHOLD if no_speech_threshold is None else float(no_speech_threshold)
    hallucination_silence_threshold_value = HALLUCINATION_SILENCE_THRESHOLD if hallucination_silence_threshold is None else float(hallucination_silence_threshold)

    # Конвертация
    tmp_path = f"uploads/tmp_{file.filename}"
    converted_wav_path = None
    total_start_time = time.time()

    try:
        # Save file
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                f.write(chunk)

        # Измеряем длительность аудио до конвертации
        audio_duration = get_audio_duration(tmp_path)

        # Convert to WAV и измеряем время
        converted_wav_path = f"uploads/{os.path.splitext(file.filename)[0]}_converted.wav"
        convert_start_time = time.time()
        convert_to_wav(
            tmp_path,
            converted_wav_path,
            remove_silence=remove_silence_value,
            silence_threshold=silence_threshold_value,
            silence_duration=silence_duration_value
        )
        convert_duration = time.time() - convert_start_time

        # Transcribe и измеряем время
        transcribe_start_time = time.time()
        result = transcribe_audio(
            file_path=converted_wav_path,
            language=language,
            task=task_value,
            model=model_value,
            word_timestamps=word_timestamps_value,
            condition_on_previous_text=condition_on_previous_text_value,
            no_speech_threshold=no_speech_threshold_value,
            hallucination_silence_threshold=hallucination_silence_threshold_value,
            initial_prompt=initial_prompt,
        )
        transcribe_duration = time.time() - transcribe_start_time

        # Добавляем информацию о времени в результат
        total_duration = time.time() - total_start_time
        result["uploaded_file"] = os.path.basename(tmp_path)
        result["result_file"] = os.path.splitext(os.path.basename(converted_wav_path))[0] + ".txt"
        result["job_id"] = str(uuid.uuid4())
        result["model"] = model_value
        result["no_speech_threshold"] = no_speech_threshold_value
        result["hallucination_silence_threshold"] = hallucination_silence_threshold_value
        result["convert_duration"] = round(convert_duration, 2)
        result["transcribe_duration"] = round(transcribe_duration, 2)
        result["total_duration"] = round(total_duration, 2)
        if audio_duration is not None:
            result["audio_duration"] = round(audio_duration, 2)

        # Логируем результат
        log_transcription_result(
            filename=os.path.basename(tmp_path),
            model=model_value,
            language=language,
            task=task_value,
            audio_duration=audio_duration,
            convert_duration=convert_duration,
            transcribe_duration=transcribe_duration,
            total_duration=total_duration,
            success=True,
        )

        # Очистить NaN и Infinity для JSON-совместимости
        result = sanitize_result(result)

        return result
    except Exception as e:
        # Логируем ошибку
        total_duration = time.time() - total_start_time
        logger.error(f"Transcription API error for {os.path.basename(tmp_path)}: {e}")
        log_transcription_result(
            filename=os.path.basename(tmp_path),
            model=model_value,
            language=language,
            task=task_value,
            audio_duration=audio_duration if 'audio_duration' in locals() else None,
            convert_duration=convert_duration if 'convert_duration' in locals() else None,
            transcribe_duration=0.0,
            total_duration=total_duration,
            success=False,
            error=str(e),
        )
        raise
    finally:
        # Cleanup temp files
        delete_file(tmp_path)
        if converted_wav_path and os.path.exists(converted_wav_path):
            delete_file(converted_wav_path)


@router.get("/health")
async def health_check():
    """Проверка состояния сервиса."""
    return {"status": "healthy", "version": "1.0.0"}


@router.get("/config")
async def get_config():
    """Получить конфигурацию из .env файла."""
    from src.config import (
        INITIAL_PROMPT,
        REMOVE_SILENCE,
        SILENCE_THRESHOLD,
        SILENCE_DURATION,
        LANGUAGE,
        NO_SPEECH_THRESHOLD,
        HALLUCINATION_SILENCE_THRESHOLD
    )
    return {
        "initial_prompt": INITIAL_PROMPT,
        "remove_silence": REMOVE_SILENCE,
        "silence_threshold": SILENCE_THRESHOLD,
        "silence_duration": SILENCE_DURATION,
        "language": LANGUAGE,
        "no_speech_threshold": NO_SPEECH_THRESHOLD,
        "hallucination_silence_threshold": HALLUCINATION_SILENCE_THRESHOLD,
    }


@router.get("/models")
async def get_models():
    """Список поддерживаемых моделей."""
    return {"supported_models": list(SUPPORTED_MODELS.keys())}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Статус задачи."""
    # TODO: Реализовать сохранение/получение из файла
    return {"job_id": job_id, "status": "pending"}

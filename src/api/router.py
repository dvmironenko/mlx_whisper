"""FastAPI роуты для API."""
import os
from fastapi import APIRouter, UploadFile, Form, HTTPException
from typing import Optional

from src.config import AUDIO_EXTENSIONS, SUPPORTED_MODELS, CHUNK_SIZE, DEFAULT_LANGUAGE, NO_SPEECH_THRESHOLD, HALLUCINATION_SILENCE_THRESHOLD, REMOVE_SILENCE, SILENCE_THRESHOLD, SILENCE_DURATION
from src.models.transcription import transcribe_audio
from src.utils.audio import convert_to_wav
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
        task_value = os.getenv("DEFAULT_TASK", "transcribe")

    model_value = model
    if model == "large":
        model_value = os.getenv("DEFAULT_MODEL", "large")

    word_timestamps_value = word_timestamps.lower() == "true"
    if word_timestamps == "false":
        word_timestamps_value = os.getenv("DEFAULT_WORD_TIMESTAMPS", "false").lower() == "true"

    condition_on_previous_text_value = condition_on_previous_text.lower() == "true"
    if condition_on_previous_text == "true":
        condition_on_previous_text_value = os.getenv("DEFAULT_CONDITION_ON_PREVIOUS", "true").lower() == "true"

    remove_silence_value = REMOVE_SILENCE if remove_silence is None else remove_silence.lower() == "true"
    silence_threshold_value = SILENCE_THRESHOLD if silence_threshold is None else float(silence_threshold)
    silence_duration_value = SILENCE_DURATION if silence_duration is None else float(silence_duration)
    no_speech_threshold_value = NO_SPEECH_THRESHOLD if no_speech_threshold is None else float(no_speech_threshold)
    hallucination_silence_threshold_value = HALLUCINATION_SILENCE_THRESHOLD if hallucination_silence_threshold is None else float(hallucination_silence_threshold)

    # Конвертация
    tmp_path = f"uploads/tmp_{file.filename}"
    converted_wav_path = None

    try:
        # Save file
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                f.write(chunk)

        # Convert to WAV
        converted_wav_path = f"uploads/{os.path.splitext(file.filename)[0]}_converted.wav"
        convert_to_wav(
            tmp_path,
            converted_wav_path,
            remove_silence=remove_silence_value,
            silence_threshold=silence_threshold_value,
            silence_duration=silence_duration_value
        )

        # Transcribe
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

        # Add file references to result
        result["uploaded_file"] = os.path.basename(tmp_path)
        result["result_file"] = os.path.splitext(os.path.basename(converted_wav_path))[0] + ".txt"
        result["job_id"] = generate_unique_filename(file.filename)

        # Add duration to the result for frontend display
        if "duration" not in result:
            result["duration"] = None

        return result
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
        DEFAULT_LANGUAGE,
        NO_SPEECH_THRESHOLD,
        HALLUCINATION_SILENCE_THRESHOLD
    )
    return {
        "initial_prompt": INITIAL_PROMPT,
        "remove_silence": REMOVE_SILENCE,
        "silence_threshold": SILENCE_THRESHOLD,
        "silence_duration": SILENCE_DURATION,
        "default_language": DEFAULT_LANGUAGE,
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

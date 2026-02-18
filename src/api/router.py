"""FastAPI роуты для API."""
import os
from fastapi import APIRouter, UploadFile, Form, HTTPException
from typing import Optional

from src.config import AUDIO_EXTENSIONS, SUPPORTED_MODELS, CHUNK_SIZE
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
    no_speech_threshold: Optional[str] = Form("0.4"),
    hallucination_silence_threshold: Optional[str] = Form("0.8"),
):
    """Транскрибировать аудиофайл."""
    from src.config import logger

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
        convert_to_wav(tmp_path, converted_wav_path)

        # Transcribe
        result = transcribe_audio(
            file_path=converted_wav_path,
            language=language,
            task=task,
            model=model,
            word_timestamps=word_timestamps.lower() == "true",
            condition_on_previous_text=condition_on_previous_text.lower() == "true",
            no_speech_threshold=float(no_speech_threshold) if no_speech_threshold else 0.4,
            hallucination_silence_threshold=float(hallucination_silence_threshold) if hallucination_silence_threshold else 0.8,
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


@router.get("/models")
async def get_models():
    """Список поддерживаемых моделей."""
    return {"supported_models": list(SUPPORTED_MODELS.keys())}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Статус задачи."""
    # TODO: Реализовать сохранение/получение из файла
    return {"job_id": job_id, "status": "pending"}

"""FastAPI роуты для API."""
import json
import math
import os
import shutil
import time
import uuid
from fastapi import APIRouter, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from typing import Optional


def format_timestamp(seconds: float) -> str:
    """Форматировать секунды в HH:MM:SS.mmm формат."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    ms = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

from src.config import AUDIO_EXTENSIONS, SUPPORTED_MODELS, CHUNK_SIZE, DEFAULT_LANGUAGE, NO_SPEECH_THRESHOLD, HALLUCINATION_SILENCE_THRESHOLD, REMOVE_SILENCE, SILENCE_THRESHOLD, SILENCE_DURATION, UPLOADS_DIR, DATA_UPLOADS_DIR, MAX_FILE_SIZE, logger, log_transcription_result
from src.models.transcription import transcribe_audio
from src.utils.audio import convert_to_wav, get_audio_duration
from src.utils.files import generate_unique_filename, delete_file, validate_file_extension, validate_file_size, build_job_path

router = APIRouter(prefix="/api/v1", tags=["transcription"])


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
    tmp_path = f"{UPLOADS_DIR}/tmp_{file.filename}"
    converted_wav_path = None
    txt_path = None
    total_start_time = time.time()

    try:
        # Save file
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                f.write(chunk)

        # Валидация размера файла
        if not validate_file_size(tmp_path):
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed ({MAX_FILE_SIZE // (1024 * 1024)} MB)"
            )

        # Генерируем job_id и создаём директорию для хранения файлов
        job_id = str(uuid.uuid4())
        job_path = build_job_path(job_id)

        # Сохраняем оригинал в data/uploads/{job_id}/
        original_path = os.path.join(job_path, file.filename)
        shutil.copy2(tmp_path, original_path)

        # Измеряем длительность аудио до конвертации
        audio_duration = get_audio_duration(tmp_path)

        # Convert to WAV и измеряем время
        wav_name = f"{os.path.splitext(file.filename)[0]}_converted.wav"
        converted_wav_path = os.path.join(job_path, wav_name)
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
        result["uploaded_file"] = file.filename
        result["result_file"] = f"{os.path.splitext(file.filename)[0]}.txt"
        result["job_id"] = job_id
        result["storage_dir"] = job_path

        # Сохраняем основной TXT файл (простой текст)
        txt_name = f"{os.path.splitext(file.filename)[0]}.txt"
        txt_path = os.path.join(job_path, txt_name)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(result.get("text", ""))

        # Сохраняем файлы с сегментами если word_timestamps=True
        if word_timestamps_value and result.get("segments"):
            # TXT с разметкой времени
            segments_txt_name = f"{os.path.splitext(file.filename)[0]}_segments.txt"
            segments_txt_path = os.path.join(job_path, segments_txt_name)
            with open(segments_txt_path, "w", encoding="utf-8") as f:
                for segment in result["segments"]:
                    start = segment.get("start", 0)
                    end = segment.get("end", 0)
                    text = segment.get("text", "")
                    f.write(f"[{format_timestamp(start)}] {text}\n")

            # JSON с полной структурой
            segments_json_name = f"{os.path.splitext(file.filename)[0]}_segments.json"
            segments_json_path = os.path.join(job_path, segments_json_name)
            with open(segments_json_path, "w", encoding="utf-8") as f:
                json.dump({"segments": result["segments"]}, f, ensure_ascii=False, indent=2)

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

        # Добавляем параметр word_timestamps для фронтенда
        result["word_timestamps"] = word_timestamps_value

        # Очистить NaN и Infinity для JSON-совместимости
        result = sanitize_result(result)

        # Очистка памяти после транскрипции
        from src.models.transcription import _clear_memory
        _clear_memory()

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
        # Удаляем только временный файл из uploads/
        delete_file(tmp_path)
        # Converted WAV и TXT сохраняются в data/uploads/{job_id}/


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


@router.get("/jobs")
async def list_jobs():
    """Список всех сохранённых задач."""
    jobs = []
    if not os.path.exists(DATA_UPLOADS_DIR):
        return jobs

    for job_id in sorted(os.listdir(DATA_UPLOADS_DIR)):
        job_dir = os.path.join(DATA_UPLOADS_DIR, job_id)
        if os.path.isdir(job_dir):
            files = []
            for f in os.listdir(job_dir):
                fp = os.path.join(job_dir, f)
                if os.path.isfile(fp):
                    files.append({"name": f, "size": os.path.getsize(fp)})
            # Дата создания папки задания
            created_at = os.path.getctime(job_dir)
            jobs.append({
                "job_id": job_id,
                "files": files,
                "created_at": created_at
            })
    return jobs




@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Удалить задание и все связанные файлы."""
    job_dir = os.path.join(DATA_UPLOADS_DIR, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Job not found")
    shutil.rmtree(job_dir)
    return {"status": "deleted", "job_id": job_id}


@router.delete("/jobs/{job_id}/files/{filename}")
async def delete_file_from_job(job_id: str, filename: str):
    """Удалить отдельный файл из задания."""
    job_dir = os.path.join(DATA_UPLOADS_DIR, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = os.path.join(job_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    os.remove(file_path)
    return {"status": "deleted", "job_id": job_id, "filename": filename}


@router.get("/files/{filename}/download")
async def download_file(filename: str):
    """Скачивание файла из data/uploads/."""
    import os

    # Защита от path traversal
    # Сначала ищем в директориях job_id, затем в корневой data/uploads
    print(f"DEBUG: Download request for filename: {filename}")
    print(f"DEBUG: DATA_UPLOADS_DIR: {DATA_UPLOADS_DIR}")
    if os.path.exists(os.path.join(DATA_UPLOADS_DIR, filename)):
        # Файл в корневой директории (редкий случай)
        resolved = os.path.realpath(os.path.join(DATA_UPLOADS_DIR, filename))
        base = os.path.realpath(DATA_UPLOADS_DIR)
    else:
        # Ищем в поддиректориях job_id
        found = False
        for job_id in os.listdir(DATA_UPLOADS_DIR):
            job_dir = os.path.join(DATA_UPLOADS_DIR, job_id)
            if os.path.isdir(job_dir):
                potential_path = os.path.join(job_dir, filename)
                if os.path.exists(potential_path):
                    resolved = os.path.realpath(potential_path)
                    base = os.path.realpath(DATA_UPLOADS_DIR)
                    found = True
                    break
        if not found:
            raise HTTPException(status_code=404, detail="File not found")

    if not resolved.startswith(base):
        raise HTTPException(status_code=400, detail="Invalid path")

    return FileResponse(resolved)

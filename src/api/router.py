"""FastAPI роуты для API."""
import json
import math
import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, UploadFile, Form, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from typing import Optional


def format_timestamp(seconds: float) -> str:
    """Форматировать секунды в HH:MM:SS.mmm формат."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    ms = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

from src.config import AUDIO_EXTENSIONS, SUPPORTED_MODELS, CHUNK_SIZE, DEFAULT_LANGUAGE, NO_SPEECH_THRESHOLD, HALLUCINATION_SILENCE_THRESHOLD, REMOVE_SILENCE, SILENCE_THRESHOLD, SILENCE_DURATION, UPLOADS_DIR, DATA_UPLOADS_DIR, MAX_FILE_SIZE, ALLOWED_URL_DOMAINS, MAX_DOWNLOAD_SIZE, DOWNLOAD_TIMEOUT, logger, log_transcription_result
from src.models.transcription import transcribe_audio
from src.models.report import load_segments_file, generate_report_via_openai, save_report, generate_report_via_openai_sync
from src.models.model_cache import ModelCache
from src.utils.download import download_from_url, validate_url

# ThreadPoolExecutor для фоновой генерации отчётов
_report_executor = ThreadPoolExecutor(max_workers=3)

from src.utils.audio import convert_to_wav, get_audio_duration
from src.utils.files import generate_unique_filename, delete_file, validate_file_extension, validate_file_size, build_job_path

router = APIRouter(prefix="/api/v1", tags=["transcription"])


def _start_report_generation(job_id: str):
    """Запустить генерацию отчёта в фоновом потоке."""
    import os

    job_path = os.path.join(DATA_UPLOADS_DIR, job_id)

    def run():
        try:
            logger.info(f"Report generation started for job: {job_id}")

            if not os.path.exists(job_path):
                logger.warning(f"Job directory not found: {job_id}")
                return

            segments_content = load_segments_file(job_path)

            if segments_content is None:
                logger.error(f"No segments.txt found for job: {job_id}")
                return

            try:
                logger.info(f"Calling OpenAI API for report generation (job: {job_id})")
                report_content = generate_report_via_openai_sync(segments_content)
            except ValueError as e:
                logger.error(f"OpenAI configuration error for job {job_id}: {e}")
                return
            except Exception as e:
                logger.error(f"Report generation failed for job {job_id}: {e}")
                return

            try:
                report_path = save_report(job_path, job_id, report_content)
                logger.info(f"Report generation completed for job: {job_id}")
            except Exception as e:
                logger.error(f"Failed to save report for job {job_id}: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in report generation for job {job_id}: {e}")

    _report_executor.submit(run)


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
    request: Request,
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
    """Залогировать файл в очередь транскрипции."""

    if file.filename is None:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not validate_file_extension(file.filename, AUDIO_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format. Supported: {', '.join(AUDIO_EXTENSIONS)}"
        )

    if model not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model. Supported: {', '.join(SUPPORTED_MODELS.keys())}"
        )

    # Resolve defaults
    task_value = os.getenv("DEFAULT_TASK", "transcribe")
    model_value = os.getenv("DEFAULT_MODEL", "large") if model == "large" else model
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

    # Validate size via Content-Length
    content_length = request.headers.get("content-length")
    if content_length:
        size = int(content_length)
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed ({MAX_FILE_SIZE // (1024 * 1024)} MB)"
            )

    tmp_path = f"{UPLOADS_DIR}/tmp_{file.filename}"
    total_start_time = time.time()

    try:
        # Save uploaded file
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                f.write(chunk)

        job_id = str(uuid.uuid4())
        job_path = build_job_path(job_id)

        # Save original
        original_path = os.path.join(job_path, file.filename)
        shutil.copy2(tmp_path, original_path)

        # Get audio duration before conversion
        audio_duration = get_audio_duration(tmp_path)

        # Convert to WAV
        wav_name = f"{os.path.splitext(file.filename)[0]}_converted.wav"
        converted_wav_path = os.path.join(job_path, wav_name)
        convert_to_wav(
            tmp_path,
            converted_wav_path,
            remove_silence=remove_silence_value,
            silence_threshold=silence_threshold_value,
            silence_duration=silence_duration_value,
        )

        # Submit to queue
        from src.services.transcription_queue import get_transcription_manager
        mgr = get_transcription_manager()
        success = mgr.submit({
            "job_id": job_id,
            "source": "upload",
            "original_filename": file.filename,
            "wav_path": converted_wav_path,
            "duration": round(audio_duration, 2) if audio_duration is not None else None,
            "params": {
                "model": model_value,
                "language": language,
                "task": task_value,
                "word_timestamps": word_timestamps_value,
                "condition_on_previous_text": condition_on_previous_text_value,
                "no_speech_threshold": no_speech_threshold_value,
                "hallucination_silence_threshold": hallucination_silence_threshold_value,
                "initial_prompt": initial_prompt,
            },
        })

        if not success:
            raise HTTPException(status_code=429, detail="Queue is full, try again later")

        return {"job_id": job_id, "status": "queued"}

    except HTTPException:
        raise
    except Exception as e:
        total_duration = time.time() - total_start_time
        logger.error(f"Transcription API error for {os.path.basename(tmp_path)}: {e}")
        raise
    finally:
        delete_file(tmp_path)


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
        "allowed_url_domains": ALLOWED_URL_DOMAINS,
        "max_download_size_mb": MAX_DOWNLOAD_SIZE // (1024 * 1024),
        "download_timeout": DOWNLOAD_TIMEOUT,
    }


@router.post("/transcribe-url")
async def transcribe_url_endpoint(
    url: str = Form(...),
    language: Optional[str] = Form(None),
    task: str = Form("transcribe"),
    model: str = Form("large"),
    word_timestamps: str = Form("false"),
    condition_on_previous_text: str = Form("true"),
    no_speech_threshold: Optional[str] = Form(None),
    hallucination_silence_threshold: Optional[str] = Form(None),
    initial_prompt: Optional[str] = Form(None),
    remove_silence: str = Form(None),
    silence_threshold: str = Form(None),
    silence_duration: str = Form(None),
):
    """Транскрибировать аудио по URL (YouTube, Vimeo, прямые ссылки)."""

    import tempfile
    import shutil

    from src.utils.files import build_job_path
    from src.config import (
        DEFAULT_LANGUAGE, DEFAULT_MODEL, REMOVE_SILENCE, SILENCE_THRESHOLD,
        SILENCE_DURATION, NO_SPEECH_THRESHOLD, HALLUCINATION_SILENCE_THRESHOLD
    )

    # Валидация URL
    if not validate_url(url):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Only YouTube, Vimeo, and direct HTTP/HTTPS links are allowed."
        )

    # Обработка параметров
    model_value = model
    if model == "large":
        model_value = DEFAULT_MODEL

    word_timestamps_value = word_timestamps.lower() == "true"
    if word_timestamps == "false":
        word_timestamps_value = False

    condition_on_previous_text_value = condition_on_previous_text.lower() == "true"
    if condition_on_previous_text == "true":
        condition_on_previous_text_value = True

    remove_silence_value = REMOVE_SILENCE if remove_silence is None else remove_silence.lower() == "true"
    silence_threshold_value = SILENCE_THRESHOLD if silence_threshold is None else float(silence_threshold)
    silence_duration_value = SILENCE_DURATION if silence_duration is None else float(silence_duration)
    no_speech_threshold_value = NO_SPEECH_THRESHOLD if no_speech_threshold is None else float(no_speech_threshold)
    hallucination_silence_threshold_value = HALLUCINATION_SILENCE_THRESHOLD if hallucination_silence_threshold is None else float(hallucination_silence_threshold)

    # Создаём job_id и папку
    job_id = str(uuid.uuid4())
    job_path = build_job_path(job_id)

    # Временный файл для скачивания
    tmp_download = None
    converted_wav_path = None
    txt_path = None
    total_start_time = time.time()

    try:
        # Скачивание файла
        tmp_download = os.path.join(job_path, "downloaded.wav")
        download_from_url(url, tmp_download, MAX_DOWNLOAD_SIZE)

        # Конвертация (если скачалось не WAV)
        if not tmp_download.endswith(".wav"):
            converted_wav_path = os.path.join(job_path, "converted.wav")
            convert_to_wav(
                tmp_download,
                converted_wav_path,
                remove_silence=remove_silence_value,
                silence_threshold=silence_threshold_value,
                silence_duration=silence_duration_value
            )
        else:
            converted_wav_path = tmp_download

        # Транскрипция
        transcribe_start_time = time.time()
        result = transcribe_audio(
            file_path=converted_wav_path,
            language=language,
            task=task,
            model=model_value,
            word_timestamps=word_timestamps_value,
            condition_on_previous_text=condition_on_previous_text_value,
            no_speech_threshold=no_speech_threshold_value,
            hallucination_silence_threshold=hallucination_silence_threshold_value,
            initial_prompt=initial_prompt,
        )
        transcribe_duration = time.time() - transcribe_start_time

        # Добавляем информацию о времени
        total_duration = time.time() - total_start_time
        audio_duration = get_audio_duration(converted_wav_path)

        result["uploaded_url"] = url
        result["job_id"] = job_id
        result["storage_dir"] = job_path
        result["model"] = model_value
        result["convert_duration"] = round(transcribe_duration, 2)  # Для URL просто используем время транскрипции
        result["transcribe_duration"] = round(transcribe_duration, 2)
        result["total_duration"] = round(total_duration, 2)
        if audio_duration is not None:
            result["audio_duration"] = round(audio_duration, 2)

        # Сохраняем основной TXT файл
        txt_name = "transcription.txt"
        txt_path = os.path.join(job_path, txt_name)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(result.get("text", ""))

        # Сохраняем файлы с сегментами если word_timestamps=True
        if word_timestamps_value and result.get("segments"):
            segments_txt_name = "segments.txt"
            segments_txt_path = os.path.join(job_path, segments_txt_name)
            with open(segments_txt_path, "w", encoding="utf-8") as f:
                for segment in result["segments"]:
                    start = segment.get("start", 0)
                    end = segment.get("end", 0)
                    text = segment.get("text", "")
                    f.write(f"[{format_timestamp(start)}] {text}\n")

        # Очистка временного скачанного файла
        if tmp_download and os.path.exists(tmp_download):
            os.remove(tmp_download)

        # Очистка памяти
        from src.models.transcription import _clear_memory
        _clear_memory()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription URL API error for {url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Удаляем временный скачанный файл
        if tmp_download and os.path.exists(tmp_download):
            delete_file(tmp_download)
        if converted_wav_path and os.path.exists(converted_wav_path) and converted_wav_path != tmp_download:
            delete_file(converted_wav_path)
        if txt_path and os.path.exists(txt_path):
            delete_file(txt_path)


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


@router.get("/files/{filename}/content")
async def get_file_content(filename: str):
    """Получить содержимое текстового файла для просмотра."""
    import os

    # Защита от path traversal
    # Сначала ищем в директориях job_id, затем в корневой data/uploads
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

    # Определяем тип контента в зависимости от расширения
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".json":
        media_type = "application/json"
    else:
        media_type = "text/plain; charset=utf-8"

    with open(resolved, "r", encoding="utf-8") as f:
        content = f.read()

    return PlainTextResponse(content=content, media_type=media_type)


@router.post("/report/{job_id}")
async def generate_report(job_id: str):
    """
    Запустить генерацию Markdown отчёта по расшифровке в фоновом потоке.

    Возвращает сразу после запуска генерации. Проверьте директорию задания
    для скачивания report.md после завершения генерации.
    """
    _start_report_generation(job_id)
    return {
        "status": "started",
        "job_id": job_id,
        "message": "Генерация отчёта запущена. Проверьте директорию задания для скачивания report.md после завершения."
    }


@router.get("/cache/models")
async def get_cached_models():
    """Получить список загруженных моделей из кэша."""
    cache = ModelCache.get_instance()
    return cache.get_stats()


@router.post("/cache/clear")
async def clear_cache():
    """Очистить все модели из кэша."""
    cache = ModelCache.get_instance()
    cache.clear()
    return {
        "status": "success",
        "message": "Model cache cleared"
    }


@router.post("/cache/preload")
async def preload_model(model: str = "large"):
    """Предзагрузить модель в кэш."""
    try:
        cache = ModelCache.get_instance()
        models_dir = os.getenv("MODELS_DIR", "models")
        model_mapping = {
            "tiny": os.path.join(models_dir, "whisper-tiny"),
            "base": os.path.join(models_dir, "whisper-base"),
            "small": os.path.join(models_dir, "whisper-small"),
            "medium": os.path.join(models_dir, "whisper-medium"),
            "turbo": os.path.join(models_dir, "whisper-turbo"),
            "large": os.path.join(models_dir, "whisper-large"),
        }
        model_path = model_mapping.get(model, os.path.join(models_dir, "whisper-large"))

        if not os.path.exists(model_path):
            model_path = f"mlx-community/whisper-{model}"

        cache.load_model(model, model_path)
        return {
            "status": "success",
            "model": model,
            "model_path": model_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preload model: {str(e)}")

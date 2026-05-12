# Queue Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подключить TranscriptionQueueManager к API, превратив синхронный `/transcribe` в асинхронный через очередь.

**Architecture:** Новый сервисный слой `TranscriptionService` (обёртка над queue + job manager) становится посредником между router и queue. Router становится thin layer: валидирует входные данные, делегирует сервису, форматирует ответ. main.py инициализирует и шатдаунит очередь через lifespan.

**Tech Stack:** Python 3.12, FastAPI, ThreadPoolExecutor, JSON filesystem metadata.

---

## Файлы, которые будут изменены

| Файл | Действие | Ответственность |
|------|----------|-----------------|
| `src/services/transcription_service.py` | Создать | Сервисный слой: обёртка над TranscriptionQueueManager + JobManager |
| `src/api/router.py` | Изменить | 5 endpoint'ов: transcribe, transcribe-url, get job, list jobs, delete job |
| `src/main.py` | Изменить | Инициализация/shutdown TranscriptionQueueManager в lifespan |
| `tests/test_transcription_service.py` | Создать | Интеграционные тесты нового сервиса |

## Существующие файлы (read-only, reference)

- `src/services/transcription_queue.py` — TranscriptionQueueManager, `get_transcription_manager()`, JobPayload, `_worker_process`, `_sanitize_result`
- `src/services/job_manager.py` — JobManager (create, load, update_status, list_all), JobStatus enum
- `src/config.py` — TRANSCRIBER_WORKERS=3, QUEUE_MAX_SIZE=20, JOB_METADATA_DIR
- `src/utils/files.py` — `build_job_path()`, `validate_file_extension()`, `validate_file_size()`, `delete_file()`
- `src/utils/audio.py` — `convert_to_wav()`, `get_audio_duration()`

---

### Task 1: Создать TranscriptionService

**Files:**
- Create: `src/services/transcription_service.py`
- Test: `tests/test_transcription_service.py`

**Контекст:** TranscriptionService — обёртка над TranscriptionQueueManager и JobManager. Инкапсулирует логику submission и retrieval. TranscriptionQueueManager — singleton с `get_transcription_manager()`. JobManager — singleton.

- [ ] **Step 1: Написать тест на submit — передача payload в queue manager**

```python
"""Тесты для TranscriptionService."""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_test_dir: str | None = None


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch, tmp_path):
    global _test_dir
    _test_dir = str(tmp_path)
    monkeypatch.setattr("src.services.job_manager.JOB_METADATA_DIR", os.path.join(_test_dir, "jobs"))
    os.makedirs(os.path.join(_test_dir, "jobs"), exist_ok=True)
    yield
    try:
        import shutil
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_managers():
    from src.services.transcription_queue import TranscriptionQueueManager
    TranscriptionQueueManager.reset()
    yield
    TranscriptionQueueManager.reset()


def test_submit_passes_payload_to_queue_manager():
    """submit() формирует payload из параметров и делегирует queue_manager.submit()."""
    from src.services.transcription_service import TranscriptionService
    from src.services.transcription_queue import TranscriptionQueueManager

    mock_qm = MagicMock()
    mock_qm.submit.return_value = True
    service = TranscriptionService(queue_manager=mock_qm, job_manager=MagicMock())

    job_id, success = service.submit(
        wav_path="/tmp/test.wav",
        job_id="test-1",
        original_filename="audio.mp3",
        model="turbo",
        language="ru",
        task="transcribe",
        word_timestamps=True,
        condition_on_previous_text=True,
        no_speech_threshold=0.4,
        hallucination_silence_threshold=0.8,
        initial_prompt="context",
        duration=120.5,
    )

    assert success is True
    assert job_id == "test-1"
    mock_qm.submit.assert_called_once()
    called_payload = mock_qm.submit.call_args[0][0]
    assert called_payload["job_id"] == "test-1"
    assert called_payload["wav_path"] == "/tmp/test.wav"
    assert called_payload["original_filename"] == "audio.mp3"
    assert called_payload["model"] == "turbo"
    assert called_payload["params"]["language"] == "ru"
    assert called_payload["params"]["task"] == "transcribe"
    assert called_payload["params"]["word_timestamps"] is True
    assert called_payload["duration"] == 120.5
```

- [ ] **Step 2: Запустить тест — должен упасть с ImportError**

```bash
cd /Users/dvmironenko/dev/mlx_whisper
source .venv/bin/activate
python -m pytest tests/test_transcription_service.py::test_submit_passes_payload_to_queue_manager -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'src.services.transcription_service'"

- [ ] **Step 3: Написать минимальную реализацию TranscriptionService**

```python
"""Сервисный слой для очереди транскрипции."""

from typing import Any, Dict, List, Optional, Tuple

from src.services.job_manager import JobManager, JobStatus
from src.services.transcription_queue import TranscriptionQueueManager


class TranscriptionService:
    """Обёртка над TranscriptionQueueManager + JobManager."""

    def __init__(
        self,
        queue_manager: TranscriptionQueueManager,
        job_manager: JobManager,
    ) -> None:
        self._qm = queue_manager
        self._jm = job_manager

    def submit(
        self,
        wav_path: str,
        job_id: str,
        original_filename: str,
        model: str,
        language: Optional[str],
        task: str,
        word_timestamps: bool,
        condition_on_previous_text: bool,
        no_speech_threshold: Optional[float],
        hallucination_silence_threshold: Optional[float],
        initial_prompt: Optional[str],
        duration: Optional[float],
    ) -> Tuple[str, bool]:
        """Submit a job to the queue. Returns (job_id, success)."""
        payload: Dict[str, Any] = {
            "job_id": job_id,
            "source": "upload",
            "original_filename": original_filename,
            "wav_path": wav_path,
            "duration": duration,
            "params": {
                "model": model,
                "language": language,
                "task": task,
                "word_timestamps": word_timestamps,
                "condition_on_previous_text": condition_on_previous_text,
                "no_speech_threshold": no_speech_threshold,
                "hallucination_silence_threshold": hallucination_silence_threshold,
                "initial_prompt": initial_prompt,
            },
        }
        success = self._qm.submit(payload)
        return job_id, success

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job metadata + result if completed."""
        metadata = self._jm.load(job_id)
        if metadata is None:
            return None

        result: Dict[str, Any] = dict(metadata)
        status = JobStatus(metadata["status"])

        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            import os
            job_dir = os.path.join("data", job_id)

            if os.path.isdir(job_dir):
                # Read text file
                txt_files = [f for f in os.listdir(job_dir) if f.endswith(".txt") and "segments" not in f]
                if txt_files:
                    with open(os.path.join(job_dir, txt_files[0]), "r", encoding="utf-8") as f:
                        result["text"] = f.read()

                # Read segments JSON
                json_files = [f for f in os.listdir(job_dir) if f.endswith(".json")]
                if json_files:
                    with open(os.path.join(job_dir, json_files[0]), "r", encoding="utf-8") as f:
                        import json
                        data = json.load(f)
                        result["segments"] = data.get("segments", [])

                # List all files
                result["files"] = [f for f in os.listdir(job_dir) if os.path.isfile(os.path.join(job_dir, f))]

        return result

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs via JobManager."""
        return self._jm.list_all()

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or processing job via queue manager."""
        return self._qm.cancel_job(job_id)
```

- [ ] **Step 4: Запустить тест — должен пройти**

```bash
python -m pytest tests/test_transcription_service.py::test_submit_passes_payload_to_queue_manager -v
```
Expected: PASS

- [ ] **Step 5: Добавить тест get_job — loading result for completed job**

```python
def test_get_job_returns_metadata_and_result_when_completed(tmp_path):
    """get_job() возвращает metadata + text/segments для completed job."""
    import os
    from src.services.transcription_service import TranscriptionService
    from src.services.job_manager import JobManager, JobStatus

    jm = JobManager()
    jm.create(
        job_id="get-job-1",
        source="upload",
        original_filename="test.mp3",
        model="turbo",
    )
    jm.update_status("get-job-1", JobStatus.COMPLETED, transcription_duration=5.2)

    # Создаём job directory и файлы результатов
    job_dir = os.path.join(str(tmp_path), "data", "get-job-1")
    os.makedirs(job_dir, exist_ok=True)
    with open(os.path.join(job_dir, "transcription.txt"), "w", encoding="utf-8") as f:
        f.write("Hello world")
    with open(os.path.join(job_dir, "segments.json"), "w", encoding="utf-8") as f:
        import json
        json.dump({"segments": [{"start": 0.0, "end": 1.0, "text": "Hello world"}]}, f)

    service = TranscriptionService(
        queue_manager=MagicMock(),
        job_manager=jm,
    )

    result = service.get_job("get-job-1")
    assert result is not None
    assert result["job_id"] == "get-job-1"
    assert result["status"] == "completed"
    assert result["text"] == "Hello world"
    assert result["segments"] == [{"start": 0.0, "end": 1.0, "text": "Hello world"}]
    assert "transcription.txt" in result["files"]
    assert "segments.json" in result["files"]
```

- [ ] **Step 6: Запустить тест — должен упасть (тест на get_job)**

```bash
python -m pytest tests/test_transcription_service.py::test_get_job_returns_metadata_and_result_when_completed -v
```
Expected: FAIL — text/segments не заполнены

- [ ] **Step 7: Запустить тест — должен пройти**

```bash
python -m pytest tests/test_transcription_service.py::test_get_job_returns_metadata_and_result_when_completed -v
```
Expected: PASS

- [ ] **Step 8: Добавить тест для get_job — job not found**

```python
def test_get_job_returns_none_for_nonexistent():
    """get_job() возвращает None для несуществующего job_id."""
    service = TranscriptionService(
        queue_manager=MagicMock(),
        job_manager=MagicMock(),
    )
    assert service.get_job("does-not-exist") is None
```

- [ ] **Step 9: Запустить все тесты — все должны пройти**

```bash
python -m pytest tests/test_transcription_service.py -v
```

- [ ] **Step 10: Запустить существующие тесты — ничего не сломалось**

```bash
python -m pytest tests/test_transcription_queue.py tests/test_job_manager.py tests/test_job_status.py -v
```

- [ ] **Step 11: Коммит**

```bash
git add src/services/transcription_service.py tests/test_transcription_service.py
git commit -m "feat: add TranscriptionService — service layer for queue integration"
```

---

### Task 2: Обновить POST /api/v1/transcribe — async через очередь

**Files:**
- Modify: `src/api/router.py:103-309`
- Test: `tests/test_transcription_service.py` (или новый `tests/test_router_integration.py`)

**Контекст:** Строки 103-309 — текущий синхронный endpoint. Ключевые шаги которые сохраняются: валидация расширения/модели/размера, сохранение файла, генерация job_id, сохранение оригинала, получение duration, конвертация в WAV. Что убираем: вызов `transcribe_audio()`, сохранение txt/segments, логирование результата, `_clear_memory()`, возврат полного результата.

- [ ] **Step 1: Написать интеграционный тест на async submit**

```python
def test_transcribe_endpoint_submits_to_queue(client, isolated_dirs):
    """POST /transcribe возвращает job_id и status queued, вместо полного результата."""
    import os
    from unittest.mock import patch

    # Создаём тестовый аудиофайл
    test_file = os.path.join(os.path.dirname(__file__), "test.wav")
    if not os.path.exists(test_file):
        pytest.skip("test.wav not available")

    with patch("src.api.router.get_transcription_manager") as mock_mgr:
        mock_qm = mock_mgr.return_value
        mock_qm.submit.return_value = True

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/v1/transcribe",
                files={"file": ("test.wav", f, "audio/wav")},
                data={
                    "model": "turbo",
                    "task": "transcribe",
                    "word_timestamps": "false",
                    "condition_on_previous_text": "true",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    mock_qm.submit.assert_called_once()
```

- [ ] **Step 2: Запустить тест — упадёт, т.к. endpoint ещё синхронный (вернёт полный result)**

Expected: FAIL — expected `status: queued`, got full transcription result

- [ ] **Step 3: Заменить тело endpoint на async submit**

Заменить функцию `transcribe_audio_endpoint` (строки 103-309) на:

```python
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
    remove_silence: str = Form(None),
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
```

Также нужно добавить импорты в начало файла (строка 30+):
```python
from src.services.transcription_queue import get_transcription_manager
```

- [ ] **Step 4: Удалить старые импорты, которые больше не нужны в router.py**

Удалить или закомментировать:
```python
# Больше не нужен — транскрипция уходит в очередь
from src.models.transcription import transcribe_audio
```
(Оставить, т.к. он может использоваться другими частями кода — лучше проверить, что transcribe_audio больше не импортируется напрямую в router.)

Проверить: `transcribe_audio` больше не используется в router.py после замены — можно удалить импорт.

- [ ] **Step 5: Запустить тест — должен пройти**

```bash
python -m pytest tests/test_transcription_service.py::test_transcribe_endpoint_submits_to_queue -v
```

- [ ] **Step 6: Убедиться что существующие тесты не сломались**

```bash
python -m pytest tests/test_job_manager.py tests/test_job_status.py tests/test_transcription_queue.py -v
```

- [ ] **Step 7: Коммит**

```bash
git add src/api/router.py src/services/transcription_queue.py tests/test_transcription_service.py
git commit -m "feat: make POST /transcribe async — submits to queue, returns job_id"
```

---

### Task 3: Обновить POST /api/v1/transcribe-url — async через очередь

**Files:**
- Modify: `src/api/router.py:345-494`

**Контекст:** Аналогично — сохраняем валидацию URL, скачивание файла, конвертацию в WAV. Убираем вызов `transcribe_audio()` и сохранение txt/segments. Вместо этого submit в очередь.

- [ ] **Step 1: Заменить тело transcribe_url_endpoint (строки 345-494)**

```python
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
    """Залогировать аудио по URL в очередь транскрипции."""

    from src.utils.files import build_job_path

    if not validate_url(url):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Only YouTube, Vimeo, and direct HTTP/HTTPS links are allowed."
        )

    model_value = os.getenv("DEFAULT_MODEL", "large") if model == "large" else model
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

    job_id = str(uuid.uuid4())
    job_path = build_job_path(job_id)

    tmp_download = None
    converted_wav_path = None
    total_start_time = time.time()

    try:
        # Download file
        tmp_download = os.path.join(job_path, "downloaded.wav")
        download_from_url(url, tmp_download, MAX_DOWNLOAD_SIZE)

        # Convert to WAV if needed
        if not tmp_download.endswith(".wav"):
            converted_wav_path = os.path.join(job_path, "converted.wav")
            convert_to_wav(
                tmp_download,
                converted_wav_path,
                remove_silence=remove_silence_value,
                silence_threshold=silence_threshold_value,
                silence_duration=silence_duration_value,
            )
        else:
            converted_wav_path = tmp_download

        # Get duration
        audio_duration = get_audio_duration(converted_wav_path)

        # Submit to queue
        mgr = get_transcription_manager()
        success = mgr.submit({
            "job_id": job_id,
            "source": "url",
            "original_filename": None,
            "wav_path": converted_wav_path,
            "duration": round(audio_duration, 2) if audio_duration is not None else None,
            "params": {
                "model": model_value,
                "language": language,
                "task": task,
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
        logger.error(f"Transcription URL API error for {url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if tmp_download and os.path.exists(tmp_download):
            delete_file(tmp_download)
        if converted_wav_path and os.path.exists(converted_wav_path) and converted_wav_path != tmp_download:
            delete_file(converted_wav_path)
```

- [ ] **Step 2: Запустить существующие тесты**

```bash
python -m pytest tests/test_transcription_queue.py tests/test_job_manager.py tests/test_job_status.py -v
```

- [ ] **Step 3: Коммит**

```bash
git add src/api/router.py
git commit -m "feat: make POST /transcribe-url async — submits to queue, returns job_id"
```

---

### Task 4: Обновить GET /api/v1/jobs/{job_id} — через сервисный слой

**Files:**
- Modify: `src/api/router.py:503-507`

**Контекст:** Заменить TODO stub на вызов `get_transcription_manager()._meta.load()` напрямую или (better) добавить helper в TranscriptionService. Поскольку get_job() требует чтения файлов с диска, а GET /jobs должен возвращать metadata + результат — используем get_transcription_manager().

- [ ] **Step 1: Заменить get_job_status endpoint**

```python
@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Статус задачи с результатом, если завершена."""
    mgr = get_transcription_manager()
    metadata = mgr._meta.load(job_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Job not found")

    result = dict(metadata)
    status = JobStatus(metadata["status"])

    if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        import os
        job_dir = os.path.join("data", job_id)
        if os.path.isdir(job_dir):
            txt_files = [f for f in os.listdir(job_dir) if f.endswith(".txt") and "segments" not in f]
            if txt_files:
                with open(os.path.join(job_dir, txt_files[0]), "r", encoding="utf-8") as f:
                    result["text"] = f.read()

            json_files = [f for f in os.listdir(job_dir) if f.endswith(".json")]
            if json_files:
                with open(os.path.join(job_dir, json_files[0]), "r", encoding="utf-8") as f:
                    import json
                    data = json.load(f)
                    result["segments"] = data.get("segments", [])

            result["files"] = [f for f in os.listdir(job_dir) if os.path.isfile(os.path.join(job_dir, f))]

    return result
```

- [ ] **Step 2: Убедиться что JobStatus импортирован**

Добавить в imports router.py:
```python
from src.services.job_manager import JobStatus
```

- [ ] **Step 3: Коммит**

```bash
git add src/api/router.py
git commit -m "feat: GET /jobs/{job_id} returns status + result from queue"
```

---

### Task 5: Обновить GET /api/v1/jobs — через JobManager

**Files:**
- Modify: `src/api/router.py:510-532`

**Контекст:** Заменить FS scan на вызов JobManager.list_all().

- [ ] **Step 1: Заменить list_jobs endpoint**

```python
@router.get("/jobs")
async def list_jobs():
    """Список всех задач через JobManager."""
    mgr = get_transcription_manager()
    return mgr._jm.list_all()
```

- [ ] **Step 2: Коммит**

```bash
git add src/api/router.py
git commit -m "feat: GET /jobs uses JobManager instead of FS scan"
```

---

### Task 6: Обновить DELETE /api/v1/jobs/{job_id} — через очередь

**Files:**
- Modify: `src/api/router.py:537-544`

**Контекст:** Сначала cancel через queue manager, затем удалить файлы директории.

- [ ] **Step 1: Заменить delete_job endpoint**

```python
@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Удалить задание: отменить если active, удалить файлы."""
    import shutil

    mgr = get_transcription_manager()

    # Try to cancel via queue manager
    cancelled = mgr.cancel_job(job_id)

    # Remove job directory
    job_dir = os.path.join(DATA_UPLOADS_DIR, job_id)
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
    else:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"status": "deleted", "job_id": job_id, "cancelled": cancelled}
```

- [ ] **Step 2: Коммит**

```bash
git add src/api/router.py
git commit -m "feat: DELETE /jobs/{job_id} cancels via queue manager before deletion"
```

---

### Task 7: Обновить main.py — инициализация/shutdown очереди

**Files:**
- Modify: `src/main.py:22-48`

**Контекст:** lifespan — место для инициализации. Нужно добавить get_transcription_manager() после preloading model и shutdown перед exit.

- [ ] **Step 1: Добавить инициализацию и shutdown очереди в lifespan**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Предзагрузка моделей и инициализация очереди при запуске сервера."""
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
        model_path = model_mapping.get(DEFAULT_MODEL, os.path.join(models_dir, "whisper-large"))

        if not os.path.exists(model_path):
            model_path = f"mlx-community/whisper-{DEFAULT_MODEL}"

        logger.info(f"Preloading model '{DEFAULT_MODEL}' from {model_path}")
        cache.load_model(DEFAULT_MODEL, model_path)
        logger.info(f"Model '{DEFAULT_MODEL}' preloaded successfully")
    except Exception as e:
        logger.warning(f"Failed to preload model: {e}")

    # Initialize transcription queue
    from src.services.transcription_queue import get_transcription_manager
    mgr = get_transcription_manager()
    logger.info("Transcription queue manager initialized")

    yield

    # Shutdown queue on exit
    mgr.shutdown()
    logger.info("Transcription queue manager shut down")
```

- [ ] **Step 2: Добавить import для JobStatus (если ещё не добавлен)**

- [ ] **Step 3: Коммит**

```bash
git add src/main.py
git commit -m "feat: initialize TranscriptionQueueManager on startup, shutdown on exit"
```

---

### Task 8: Интеграционные тесты

**Files:**
- Create: `tests/test_router_integration.py`
- Modify: `tests/test_transcription_service.py` (добавить тест cancel и list)

- [ ] **Step 1: Написать тесты для cancel и list в service**

```python
def test_list_jobs_delegates_to_job_manager():
    """list_jobs() делегирует JobManager.list_all()."""
    from src.services.transcription_service import TranscriptionService
    from src.services.job_manager import JobManager, JobStatus

    jm = JobManager()
    jm.create(job_id="list-job-1", source="upload", original_filename="a.mp3", model="turbo")
    jm.create(job_id="list-job-2", source="upload", original_filename="b.mp3", model="large")

    service = TranscriptionService(
        queue_manager=MagicMock(),
        job_manager=jm,
    )

    jobs = service.list_jobs()
    assert len(jobs) >= 2
    job_ids = [j["job_id"] for j in jobs]
    assert "list-job-1" in job_ids
    assert "list-job-2" in job_ids
```

```python
def test_cancel_job_delegates_to_queue_manager():
    """cancel_job() делегирует queue_manager.cancel_job()."""
    from src.services.transcription_service import TranscriptionService

    mock_qm = MagicMock()
    mock_qm.cancel_job.return_value = True
    service = TranscriptionService(
        queue_manager=mock_qm,
        job_manager=MagicMock(),
    )

    result = service.cancel_job("cancel-1")
    assert result is True
    mock_qm.cancel_job.assert_called_once_with("cancel-1")
```

- [ ] **Step 2: Написать интеграционный тест на 404 для GET /jobs/{id}**

```python
def test_get_job_returns_404_for_nonexistent(client):
    """GET /jobs/{id} возвращает 404 для несуществующего job."""
    response = client.get("/api/v1/jobs/nonexistent-job-id")
    assert response.status_code == 404
```

- [ ] **Step 3: Запустить все тесты**

```bash
python -m pytest tests/test_transcription_service.py tests/test_router_integration.py tests/test_transcription_queue.py tests/test_job_manager.py tests/test_job_status.py -v
```

- [ ] **Step 4: Коммит**

```bash
git add tests/
git commit -m "test: add integration tests for queue integration"
```

---

### Task 9: Финальная верификация

- [ ] **Step 1: Запустить все тесты проекта**

```bash
python -m pytest tests/test_transcription_queue.py tests/test_job_manager.py tests/test_job_status.py tests/test_transcription_service.py -v
```

Ожидаемый результат: все тесты проходят.

- [ ] **Step 2: Проверить что импорт не сломан**

```bash
source .venv/bin/activate
python -c "from src.api import router; print('OK')"
```

- [ ] **Step 3: Проверить что приложение стартует**

```bash
python src/main.py
```

Ожидаемый результат: лог `TranscriptionQueueManager started` + `Model preloaded`.

- [ ] **Step 4: Проверить health endpoint**

```bash
curl http://localhost:8801/api/v1/health
```

Expected: `{"status":"healthy","version":"1.0.0"}`

- [ ] **Step 5: Проверить что POST /transcribe возвращает job_id**

```bash
curl -X POST http://localhost:8801/api/v1/transcribe \
  -F "file=@tests/test.wav" \
  -F "model=turbo" \
  -F "task=transcribe"
```

Expected: `{"job_id":"uuid","status":"queued"}`

- [ ] **Step 6: Проверить GET /jobs**

```bash
curl http://localhost:8801/api/v1/jobs
```

Expected: массив jobs из JobManager.

- [ ] **Step 7: Коммит всех изменений**

```bash
git add -A
git commit -m "feat: integrate queue into API — async transcription via queue manager"
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-05-queue-integration.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

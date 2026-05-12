# Parallel Transcription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Добавить параллельную транскрипцию через ThreadPoolExecutor + queue.Queue с fire-and-forget API и polling статусов.

**Architecture:** Два новых модуля — `src/services/job_manager.py` (single-file JSON metadata) и `src/services/transcription_queue.py` (ThreadPoolExecutor workers + bounded Queue). Существующие эндпоинты POST /transcribe и POST /transcribe-url возвращают job_id сразу, worker threads вызывают transcribe_audio() с threading.Lock для защиты модели. Job metadata хранится в data/jobs/{job_id}.json.

**Tech Stack:** Python stdlib (threading, queue, json, uuid, dataclasses), FastAPI, MLX Whisper (как есть).

---

### Task 1: JobStatus enum

**Files:**
- Create: `src/services/__init__.py` (пустой)
- Create: `src/services/job_manager.py`

- [ ] **Step 1: Write the enum + basic test**

```python
# src/services/job_manager.py
from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

```python
# tests/test_job_status.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.job_manager import JobStatus


def test_job_status_values():
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.PROCESSING.value == "processing"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_job_status_str_conversion():
    assert str(JobStatus.QUEUED) == "queued"
    assert JobStatus("queued") == JobStatus.QUEUED
```

- [ ] **Step 2: Create __init__.py**

```bash
touch src/services/__init__.py
```

- [ ] **Step 3: Run test**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_job_status.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 4: Commit**

```bash
git add src/services/__init__.py src/services/job_manager.py tests/test_job_status.py
git commit -m "feat: добавить JobStatus enum"
```

---

### Task 2: JobManager — create and save

**Files:**
- Modify: `src/services/job_manager.py`
- Modify: `tests/test_job_manager.py`

- [ ] **Step 1: Write the full JobManager + tests**

```python
# src/services/job_manager.py (полный файл)
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.services.job_manager import JobStatus
from src.config import JOB_METADATA_DIR

os.makedirs(JOB_METADATA_DIR, exist_ok=True)


def _job_file(job_id: str) -> str:
    return os.path.join(JOB_METADATA_DIR, f"{job_id}.json")


class JobManager:
    """Singleton для управления job metadata в filesystem."""

    _instance: Optional["JobManager"] = None

    def __new__(cls) -> "JobManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create(
        self,
        job_id: Optional[str] = None,
        source: str = "upload",
        **extra,
    ) -> Dict[str, Any]:
        if job_id is None:
            job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "source": source,
            "created_at": now,
            "updated_at": now,
            "original_filename": None,
            "model": None,
            "language": None,
            "task": None,
            "word_timestamps": False,
            "duration": None,
            "transcription_duration": None,
            "result_file": None,
            "error": None,
        }
        metadata.update(extra)
        self._save(job_id, metadata)
        return metadata

    def update_status(self, job_id: str, status: JobStatus, **extra) -> Optional[Dict[str, Any]]:
        metadata = self.load(job_id)
        if metadata is None:
            return None
        metadata["status"] = status.value
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata.update(extra)
        self._save(job_id, metadata)
        return metadata

    def load(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = _job_file(job_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def cancel(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.update_status(job_id, JobStatus.CANCELLED)

    def list_all(self) -> list[Dict[str, Any]]:
        result = []
        if not os.path.exists(JOB_METADATA_DIR):
            return result
        for fname in sorted(os.listdir(JOB_METADATA_DIR)):
            if fname.endswith(".json"):
                fpath = os.path.join(JOB_METADATA_DIR, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    result.append(json.load(f))
        return result

    def _save(self, job_id: str, metadata: Dict[str, Any]) -> None:
        path = _job_file(job_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
```

```python
# tests/test_job_manager.py
import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Переопределяем JOB_METADATA_DIR на временную директорию
_test_dir = None


@pytest.fixture(autouse=True)
def isolated_job_dir(monkeypatch):
    global _test_dir
    _test_dir = tempfile.mkdtemp()
    monkeypatch.setattr("src.services.job_manager.JOB_METADATA_DIR", _test_dir)
    yield
    shutil.rmtree(_test_dir, ignore_errors=True)


def _load(job_id):
    path = os.path.join(_test_dir, f"{job_id}.json")
    with open(path, "r") as f:
        return json.load(f)


def test_create_job():
    from src.services.job_manager import JobManager
    mgr = JobManager()
    meta = mgr.create(job_id="test-1", source="upload", original_filename="test.wav", model="turbo")
    assert meta["job_id"] == "test-1"
    assert meta["status"] == "queued"
    assert meta["source"] == "upload"
    assert meta["original_filename"] == "test.wav"
    assert meta["model"] == "turbo"
    assert meta["created_at"] is not None
    assert meta["updated_at"] is not None


def test_load_job():
    from src.services.job_manager import JobManager
    mgr = JobManager()
    mgr.create(job_id="test-2", source="url")
    loaded = mgr.load("test-2")
    assert loaded is not None
    assert loaded["job_id"] == "test-2"


def test_load_nonexistent():
    from src.services.job_manager import JobManager
    mgr = JobManager()
    assert mgr.load("nonexistent") is None


def test_update_status():
    from src.services.job_manager import JobManager, JobStatus
    mgr = JobManager()
    mgr.create(job_id="test-3")
    updated = mgr.update_status("test-3", JobStatus.PROCESSING, duration=120.5)
    assert updated["status"] == "processing"
    assert updated["duration"] == 120.5
    loaded = mgr.load("test-3")
    assert loaded["status"] == "processing"
    assert loaded["updated_at"] != loaded["created_at"]


def test_cancel():
    from src.services.job_manager import JobManager, JobStatus
    mgr = JobManager()
    mgr.create(job_id="test-4")
    cancelled = mgr.cancel("test-4")
    assert cancelled["status"] == "cancelled"


def test_list_all():
    from src.services.job_manager import JobManager
    mgr = JobManager()
    mgr.create(job_id="test-a")
    mgr.create(job_id="test-b")
    mgr.create(job_id="test-c")
    jobs = mgr.list_all()
    assert len(jobs) == 3
    job_ids = [j["job_id"] for j in jobs]
    assert "test-a" in job_ids
    assert "test-b" in job_ids
    assert "test-c" in job_ids


def test_singleton():
    from src.services.job_manager import JobManager
    a = JobManager()
    b = JobManager()
    assert a is b
```

- [ ] **Step 2: Run test**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_job_manager.py -v
```
Expected: FAIL — JobManager не определён

- [ ] **Step 3: Implement JobManager** (код из Step 1)

- [ ] **Step 4: Run test — verify PASS**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_job_manager.py -v
```
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/job_manager.py tests/test_job_manager.py
git commit -m "feat: добавить JobManager для управления job metadata"
```

---

### Task 3: TranscriptionQueueManager — worker pool + queue

**Files:**
- Create: `src/services/transcription_queue.py`
- Create: `tests/test_transcription_queue.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_transcription_queue.py
import os
import sys
import tempfile
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_test_dir = None


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch):
    global _test_dir
    _test_dir = tempfile.mkdtemp()
    monkeypatch.setattr("src.services.job_manager.JOB_METADATA_DIR", os.path.join(_test_dir, "jobs"))
    os.makedirs(os.path.join(_test_dir, "jobs"), exist_ok=True)
    monkeypatch.setenv("TRANSCRIBER_WORKERS", "2")
    monkeypatch.setenv("QUEUE_MAX_SIZE", "5")
    yield
    # Cleanup
    try:
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


def _get_manager():
    from src.services.transcription_queue import TranscriptionQueueManager
    return TranscriptionQueueManager._instance


def test_submit_and_process():
    """Job поднимается в очередь, worker обрабатывает, статус обновляется."""
    from src.services.transcription_queue import TranscriptionQueueManager, JobPayload
    from src.services.job_manager import JobStatus

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    mgr._executor = ThreadPoolExecutor(max_workers=1)
    meta_mgr, transcribe_fn = _mock_transcription()

    payload = mgr._build_payload("test-job-1", "/tmp/test.wav", {"model": "turbo"})
    result = mgr._worker_process(payload)

    assert result is not None
    assert result["status"] == "completed"
    status = meta_mgr.load("test-job-1")
    assert status["status"] == "completed"
    assert status["transcription_duration"] is not None

    mgr.shutdown()


def test_queue_full_returns_false():
    """При переполнении очереди submit возвращает False."""
    from src.services.transcription_queue import TranscriptionQueueManager

    mgr = TranscriptionQueueManager(workers=1, max_size=1)
    mgr._queue = type("Queue", (), {"full": MagicMock(return_value=True)})()
    result = mgr.submit({"job_id": "overload", "wav_path": "/tmp/x.wav", "params": {}})
    assert result is False
    mgr.shutdown()


def test_cancel_during_processing():
    """Cancel processing job: worker завершает и ставит cancelled."""
    from src.services.transcription_queue import TranscriptionQueueManager
    from src.services.job_manager import JobStatus

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    mgr._executor = ThreadPoolExecutor(max_workers=1)

    meta_mgr, transcribe_fn = _mock_transcription()
    # Simulate: mark as cancelled after worker picks it up
    payload = mgr._build_payload("cancel-job-1", "/tmp/test.wav", {"model": "turbo"})
    # Manually cancel
    meta_mgr.update_status("cancel-job-1", JobStatus.PROCESSING)
    mgr.cancel_job("cancel-job-1")

    result = mgr._worker_process(payload)
    assert result["status"] == "cancelled"

    mgr.shutdown()


def _mock_transcription():
    """Возвращает (JobManager, mock_transcribe_fn) для тестов."""
    from src.services.job_manager import JobManager
    meta_mgr = JobManager()

    def fake_transcribe(file_path, **kwargs):
        return {"text": "mock result", "segments": []}

    return meta_mgr, fake_transcribe
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_transcription_queue.py -v
```
Expected: FAIL — TranscriptionQueueManager не определён

- [ ] **Step 3: Write implementation**

```python
# src/services/transcription_queue.py
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from queue import Queue, Full
from typing import Any, Callable, Dict, Optional

from src.services.job_manager import JobManager, JobStatus
from src.config import TRANSCRIBER_WORKERS, QUEUE_MAX_SIZE, JOB_METADATA_DIR

logger = logging.getLogger("mlx_whisper")


@dataclass
class JobPayload:
    job_id: str
    wav_path: str
    params: Dict[str, Any]
    cancelled: bool = False


class TranscriptionQueueManager:
    """Singleton для параллельной обработки транскрипции через ThreadPoolExecutor + Queue."""

    _instance: Optional["TranscriptionQueueManager"] = None
    _lock = threading.Lock()
    _transcription_lock = threading.Lock()

    def __new__(cls, **kwargs) -> "TranscriptionQueueManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, workers: Optional[int] = None, max_size: Optional[int] = None):
        if self._initialized:
            return
        self._initialized = True
        self._workers = workers if workers is not None else TRANSCRIBER_WORKERS
        self._max_size = max_size if max_size is not None else QUEUE_MAX_SIZE
        self._queue: Queue = Queue(maxsize=self._max_size)
        self._executor = ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="transcriber")
        self._meta = JobManager()
        self._shutdown = False
        self._worker_futures = []
        self._start_workers()

    def _start_workers(self) -> None:
        for i in range(self._workers):
            future = self._executor.submit(self._worker_loop, i)
            self._worker_futures.append(future)
        logger.info(f"TranscriptionQueueManager started with {self._workers} workers, queue max={self._max_size}")

    def submit(self, payload: Dict[str, Any]) -> bool:
        """Положить job в очередь. Вернуть False если очередь полна."""
        if self._shutdown:
            return False
        job_id = payload.get("job_id", str(uuid.uuid4()))
        wav_path = payload["wav_path"]
        params = payload.get("params", {})

        meta = self._meta.create(
            job_id=job_id,
            source=payload.get("source", "upload"),
            original_filename=payload.get("original_filename"),
            model=params.get("model"),
            language=params.get("language"),
            task=params.get("task"),
            word_timestamps=params.get("word_timestamps", False),
            duration=params.get("duration"),
        )

        try:
            job_payload = self._build_payload(job_id, wav_path, params)
            self._queue.put_nowait(job_payload)
            return True
        except Full:
            self._meta.update_status(job_id, JobStatus.QUEUED)
            return False

    def cancel_job(self, job_id: str) -> bool:
        """Отметить job как cancelled (queued или processing)."""
        meta = self._meta.load(job_id)
        if meta is None:
            return False
        current = JobStatus(meta["status"])
        if current in (JobStatus.QUEUED, JobStatus.PROCESSING):
            # Отмечаем cancelled в metadata
            self._meta.update_status(job_id, JobStatus.CANCELLED)
            # Если job ещё в очереди — помечаем как cancelled
            # (нельзя убрать из queue, но worker проверит флаг cancelled)
            return True
        return False

    def shutdown(self) -> None:
        """Graceful shutdown: стопим воркеры, drain очереди."""
        logger.info("TranscriptionQueueManager shutting down...")
        self._shutdown = True
        # Ждём завершения всех текущих jobs
        for future in self._worker_futures:
            future.result()
        self._executor.shutdown(wait=True)
        logger.info("TranscriptionQueueManager stopped")

    def _build_payload(self, job_id: str, wav_path: str, params: Dict[str, Any]) -> JobPayload:
        return JobPayload(
            job_id=job_id,
            wav_path=wav_path,
            params=params,
            cancelled=False,
        )

    def _worker_loop(self, worker_id: int) -> None:
        """Основной цикл воркера."""
        logger.info(f"Worker {worker_id} started")
        while not self._shutdown:
            try:
                job = self._queue.get(timeout=1.0)
            except Exception:
                continue

            # Проверяем cancelled до начала обработки
            if self._meta.load(job.job_id)["status"] == JobStatus.CANCELLED.value:
                self._queue.task_done()
                logger.info(f"Worker {worker_id}: job {job.job_id} was cancelled, skipping")
                continue

            # Обновляем статус на processing
            self._meta.update_status(job.job_id, JobStatus.PROCESSING)
            logger.info(f"Worker {worker_id}: processing job {job.job_id}")

            try:
                result = self._worker_process(job)
                if result is not None:
                    logger.info(f"Worker {worker_id}: job {job.job_id} completed")
            except Exception as e:
                logger.error(f"Worker {worker_id}: job {job.job_id} failed: {e}")
                self._meta.update_status(job.job_id, JobStatus.FAILED, error=str(e))
            finally:
                self._queue.task_done()

        logger.info(f"Worker {worker_id} stopped")

    def _worker_process(self, job: JobPayload) -> Optional[Dict[str, Any]]:
        """Обработать один job: вызвать transcribe_audio с lock."""
        from src.models.transcription import transcribe_audio
        from src.models.transcription import _clear_memory
        from src.api.router import sanitize_result
        import time

        start = time.time()
        try:
            with self._transcription_lock:
                result = transcribe_audio(
                    file_path=job.wav_path,
                    language=job.params.get("language"),
                    task=job.params.get("task", "transcribe"),
                    model=job.params.get("model", "large"),
                    word_timestamps=job.params.get("word_timestamps", False),
                    condition_on_previous_text=job.params.get("condition_on_previous_text", True),
                    no_speech_threshold=job.params.get("no_speech_threshold"),
                    hallucination_silence_threshold=job.params.get("hallucination_silence_threshold"),
                    initial_prompt=job.params.get("initial_prompt"),
                )
            duration = time.time() - start
            result = sanitize_result(result)
            result["transcription_duration"] = round(duration, 2)

            # Проверяем, не был ли отменён во время обработки
            status = self._meta.load(job.job_id)
            final_status = JobStatus.CANCELLED if status["status"] == JobStatus.CANCELLED.value else JobStatus.COMPLETED

            self._meta.update_status(
                job.job_id,
                final_status,
                transcription_duration=duration,
                result_file=result.get("result_file"),
            )
            return {"status": final_status.value}

        except Exception as e:
            logger.error(f"Transcription failed for {job.job_id}: {e}")
            self._meta.update_status(job.job_id, JobStatus.FAILED, error=str(e))
            raise
        finally:
            _clear_memory()
```

- [ ] **Step 4: Run test — verify PASS**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_transcription_queue.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/transcription_queue.py tests/test_transcription_queue.py
git commit -m "feat: добавить TranscriptionQueueManager для параллельной транскрипции"
```

---

### Task 4: threading.Lock в transcription.py

**Files:**
- Modify: `src/models/transcription.py`

- [ ] **Step 1: Add lock around transcribe() call**

```python
# src/models/transcription.py — заменить блок транскрипции (примерно строки 128-135)
```

Было:
```python
    try:
        start_time = time.time()
        result = transcribe(
            audio=file_path,
            path_or_hf_repo=model_path,
            **transcribe_options
        )
        transcribe_duration = time.time() - start_time
```

Стало:
```python
    _transcription_lock = threading.Lock()

    try:
        start_time = time.time()
        with _transcription_lock:
            result = transcribe(
                audio=file_path,
                path_or_hf_repo=model_path,
                **transcribe_options
            )
        transcribe_duration = time.time() - start_time
```

- [ ] **Step 2: Add threading import**

```python
# src/models/transcription.py — в импорты добавить:
import threading
```

- [ ] **Step 3: Quick smoke test**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -c "from src.models.transcription import _transcription_lock; print('OK:', type(_transcription_lock))"
```
Expected: `OK: <class '_thread.lock'>`

- [ ] **Step 4: Commit**

```bash
git add src/models/transcription.py
git commit -m "fix: добавить threading.Lock для защиты модели при параллельной транскрипции"
```

---

### Task 5: Конфигурация — env vars + dirs

**Files:**
- Modify: `src/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Добавить в config.py после строки 79 (DOWNLOAD_TIMEOUT)**

```python
# src/config.py — добавить после строки 79:

# Transcription queue settings
TRANSCRIBER_WORKERS: int = int(os.getenv("TRANSCRIBER_WORKERS", "3"))
QUEUE_MAX_SIZE: int = int(os.getenv("QUEUE_MAX_SIZE", "20"))
JOB_METADATA_DIR: str = os.path.join("data", "jobs")
os.makedirs(JOB_METADATA_DIR, exist_ok=True)
```

- [ ] **Step 2: Добавить в .env.example после строки 84 (DOWNLOAD_TIMEOUT_SECONDS)**

```bash
# .env.example — добавить в конец перед "Прочие параметры":

# ========================================
# Parallel Transcription Settings
# ========================================

TRANSCRIBER_WORKERS=3               # Количество параллельных воркеров (по умолчанию: 3)
QUEUE_MAX_SIZE=20                   # Максимум job в очереди (по умолчанию: 20)
```

- [ ] **Step 3: Verify config imports**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -c "from src.config import TRANSCRIBER_WORKERS, QUEUE_MAX_SIZE, JOB_METADATA_DIR; print(f'workers={TRANSCRIBER_WORKERS}, max={QUEUE_MAX_SIZE}, dir={JOB_METADATA_DIR}')"
```
Expected: `workers=3, max=20, dir=data/jobs`

- [ ] **Step 4: Commit**

```bash
git add src/config.py .env.example
git commit -m "feat: добавить конфигурацию для параллельной транскрипции"
```

---

### Task 6: POST /transcribe — fire-and-forget pattern

**Files:**
- Modify: `src/api/router.py`

- [ ] **Step 1: Заменить весь POST /transcribe эндпоинт (строки 103-310)**

Новый эндпоинт — сохраняет файл, конвертирует WAV, затем кладёт job в очередь:

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
    """Транскрибировать аудиофайл (async, возвращает job_id)."""

    # --- Валидация ---
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

    # --- Параметры ---
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

    # --- Сохранение и конвертация ---
    tmp_path = f"{UPLOADS_DIR}/tmp_{file.filename}"
    converted_wav_path = None
    total_start_time = time.time()

    try:
        # Валидация размера
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            if size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File size exceeds maximum allowed ({MAX_FILE_SIZE // (1024 * 1024)} MB)"
                )

        # Сохраняем файл
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                f.write(chunk)

        # Генерируем job_id
        job_id = str(uuid.uuid4())
        job_path = build_job_path(job_id)

        # Сохраняем оригинал
        original_path = os.path.join(job_path, file.filename)
        shutil.copy2(tmp_path, original_path)

        # Измеряем длительность
        audio_duration = get_audio_duration(tmp_path)

        # Конвертируем в WAV
        wav_name = f"{os.path.splitext(file.filename)[0]}_converted.wav"
        converted_wav_path = os.path.join(job_path, wav_name)
        convert_to_wav(
            tmp_path,
            converted_wav_path,
            remove_silence=remove_silence_value,
            silence_threshold=silence_threshold_value,
            silence_duration=silence_duration_value
        )
        convert_duration = time.time() - total_start_time

        # Формируем параметры для очереди
        transcription_params = {
            "model": model_value,
            "language": language,
            "task": task_value,
            "word_timestamps": word_timestamps_value,
            "condition_on_previous_text": condition_on_previous_text_value,
            "no_speech_threshold": no_speech_threshold_value,
            "hallucination_silence_threshold": hallucination_silence_threshold_value,
            "initial_prompt": initial_prompt,
        }

        # --- Отправка в очередь ---
        from src.services.transcription_queue import transcription_manager

        payload = {
            "job_id": job_id,
            "wav_path": converted_wav_path,
            "params": transcription_params,
            "source": "upload",
            "original_filename": file.filename,
            "duration": round(audio_duration, 2) if audio_duration else None,
        }

        success = transcription_manager.submit(payload)
        if not success:
            # Очередь полна — удаляем созданные файлы
            try:
                shutil.rmtree(job_path, ignore_errors=True)
            except Exception:
                pass
            raise HTTPException(status_code=503, detail="Queue is full, try again later")

        # Логирование
        total_duration = time.time() - total_start_time
        log_transcription_result(
            filename=os.path.basename(tmp_path),
            model=model_value,
            language=language,
            task=task_value,
            audio_duration=audio_duration,
            convert_duration=convert_duration,
            transcribe_duration=0.0,
            total_duration=total_duration,
            success=True,
        )

        return {"job_id": job_id, "status": "queued"}

    except HTTPException:
        raise
    except Exception as e:
        total_duration = time.time() - total_start_time
        logger.error(f"Transcription API error for {os.path.basename(tmp_path if 'tmp_path' in locals() else '')}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        delete_file(tmp_path)
```

- [ ] **Step 2: Add import for transcription_manager at top of router.py**

```python
# src/api/router.py — добавить в imports (после других imports, перед router definition):
# (transcription_manager инициализируется lazily, когда вызывается в эндпоинте)
```

Нет необходимости в глобальном импорте — менеджер импортируется внутри эндпоинта после инициализации в lifespan.

- [ ] **Step 3: Smoke test — check endpoint returns job_id**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -c "
from src.api.router import router
routes = [r.path for r in router.routes]
print('transcribe in routes:', '/api/v1/transcribe' in routes)
print('All routes:', routes)
"
```
Expected: `transcribe in routes: True`

- [ ] **Step 4: Commit**

```bash
git add src/api/router.py
git commit -m "feat: POST /transcribe — fire-and-forget pattern с возвратом job_id"
```

---

### Task 7: POST /transcribe-url — fire-and-forget pattern

**Files:**
- Modify: `src/api/router.py`

- [ ] **Step 1: Заменить POST /transcribe-url (строки 345-494)**

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
    """Транскрибировать аудио по URL (async, возвращает job_id)."""

    import tempfile

    # Валидация URL
    if not validate_url(url):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Only YouTube, Vimeo, and direct HTTP/HTTPS links are allowed."
        )

    # Параметры
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
    total_start_time = time.time()

    try:
        # Скачивание
        tmp_download = os.path.join(job_path, "downloaded.wav")
        download_from_url(url, tmp_download, MAX_DOWNLOAD_SIZE)

        # Конвертация (если не WAV)
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

        # Измеряем длительность
        audio_duration = get_audio_duration(converted_wav_path)

        # Формируем параметры для очереди
        transcription_params = {
            "model": model_value,
            "language": language,
            "task": task,
            "word_timestamps": word_timestamps_value,
            "condition_on_previous_text": condition_on_previous_text_value,
            "no_speech_threshold": no_speech_threshold_value,
            "hallucination_silence_threshold": hallucination_silence_threshold_value,
            "initial_prompt": initial_prompt,
        }

        # Отправка в очередь
        from src.services.transcription_queue import transcription_manager

        payload = {
            "job_id": job_id,
            "wav_path": converted_wav_path,
            "params": transcription_params,
            "source": "url",
            "original_filename": None,
            "duration": round(audio_duration, 2) if audio_duration else None,
        }

        success = transcription_manager.submit(payload)
        if not success:
            try:
                shutil.rmtree(job_path, ignore_errors=True)
            except Exception:
                pass
            raise HTTPException(status_code=503, detail="Queue is full, try again later")

        log_transcription_result(
            filename=url,
            model=model_value,
            language=language,
            task=task,
            audio_duration=audio_duration,
            convert_duration=None,
            transcribe_duration=0.0,
            total_duration=time.time() - total_start_time,
            success=True,
        )

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

- [ ] **Step 2: Commit**

```bash
git add src/api/router.py
git commit -m "feat: POST /transcribe-url — fire-and-forget pattern с возвратом job_id"
```

---

### Task 8: GET /jobs/{job_id} — real lookup

**Files:**
- Modify: `src/api/router.py`

- [ ] **Step 1: Заменить stub (строки 503-507)**

```python
@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Статус задачи."""
    from src.services.job_manager import JobManager
    meta = JobManager().load(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return meta
```

- [ ] **Step 2: Commit**

```bash
git add src/api/router.py
git commit -m "feat: GET /jobs/{job_id} — реальная загрузка job metadata"
```

---

### Task 9: DELETE /jobs/{job_id}/cancel

**Files:**
- Modify: `src/api/router.py`

- [ ] **Step 1: Добавить новый эндпоинт после GET /jobs/{job_id}**

```python
@router.delete("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Отменить queued или processing задачу."""
    from src.services.job_manager import JobManager, JobStatus
    from src.services.transcription_queue import transcription_manager

    meta = JobManager().load(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Job not found")

    status = JobStatus(meta["status"])
    if status not in (JobStatus.QUEUED, JobStatus.PROCESSING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status '{status.value}'. Only queued/processing jobs can be cancelled."
        )

    success = transcription_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to cancel job")

    updated = JobManager().load(job_id)
    return updated
```

- [ ] **Step 2: Улучшить существующий DELETE /jobs/{job_id} — удаление metadata**

```python
@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Удалить задание и все связанные файлы."""
    from src.services.job_manager import JobManager
    import shutil

    # Удаляем metadata
    job_manager = JobManager()
    meta = job_manager.load(job_id)

    # Удаляем job directory
    job_dir = os.path.join(DATA_UPLOADS_DIR, job_id)
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)

    # Удаляем metadata file
    if meta:
        import os as _os
        meta_path = _os.path.join(JOB_METADATA_DIR, f"{job_id}.json")
        if _os.path.exists(meta_path):
            _os.remove(meta_path)

    return {"status": "deleted", "job_id": job_id}
```

- [ ] **Step 3: Commit**

```bash
git add src/api/router.py
git commit -m "feat: добавить DELETE /jobs/{job_id}/cancel и улучшить удаление jobs"
```

---

### Task 10: Lifespan — queue lifecycle

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Добавить start/shutdown queue в lifespan**

```python
# src/main.py — добавить import и изменить lifespan:

from src.services.transcription_queue import transcription_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Предзагрузка моделей при запуске сервера."""
    # ... (существующая загрузка моделей без изменений) ...
    # (весь существующий код preloading остаётся как есть)

    yield

    # Shutdown transcription queue
    transcription_manager.shutdown()
```

Полный updated lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Предзагрузка моделей и старт очереди транскрипции."""
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

    # Запуск очереди транскрипции
    from src.services.transcription_queue import transcription_manager
    transcription_manager.start()

    yield

    # Graceful shutdown очереди
    transcription_manager.shutdown()
```

- [ ] **Step 2: Verify lifespan function**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -c "
from src.main import app
print('Lifespan:', app.lifespan is not None)
print('Routes:', len(app.routes))
"
```

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: добавить start/shutdown TranscriptionQueueManager в lifespan"
```

---

### Task 11: TranscriptionQueueManager — start() method

**Files:**
- Modify: `src/services/transcription_queue.py`

- [ ] **Step 1: Добавить start() method и module-level singleton instance**

```python
# src/services/transcription_queue.py — в конец файла, после класса:

# Module-level singleton instance (lazy init)
transcription_manager: Optional["TranscriptionQueueManager"] = None


class TranscriptionQueueManager:
    # ... (существующий код класса без изменений до __init__) ...

    def __init__(self, workers: Optional[int] = None, max_size: Optional[int] = None):
        if self._initialized:
            return
        self._initialized = True
        self._workers = workers if workers is not None else TRANSCRIBER_WORKERS
        self._max_size = max_size if max_size is not None else QUEUE_MAX_SIZE
        self._queue: Queue = Queue(maxsize=self._max_size)
        self._executor = None  # Not started yet
        self._meta = JobManager()
        self._shutdown = False
        self._worker_futures = []
        # Workers НЕ запускаются тут — это делает start()

    def start(self) -> None:
        """Запустить воркеры (вызывать из lifespan)."""
        if self._executor is not None:
            return  # Already started
        self._executor = ThreadPoolExecutor(
            max_workers=self._workers,
            thread_name_prefix="transcriber"
        )
        for i in range(self._workers):
            future = self._executor.submit(self._worker_loop, i)
            self._worker_futures.append(future)
        logger.info(f"TranscriptionQueueManager started with {self._workers} workers, queue max={self._max_size}")

    # ... (существующие методы без изменений) ...

    def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("TranscriptionQueueManager shutting down...")
        self._shutdown = True
        if self._executor is not None:
            for future in self._worker_futures:
                future.result()
            self._executor.shutdown(wait=True)
        logger.info("TranscriptionQueueManager stopped")


# Module-level singleton
transcription_manager = TranscriptionQueueManager()
```

Также нужно поправить метод `submit` — он вызывает `self._queue.put_nowait`, но `self._executor` может быть None до start(). Это нормально — queue создаётся в __init__.

- [ ] **Step 2: Remove _start_workers из __init__** (перенести в start())

В текущем коде из Task 3: `self._start_workers()` вызывается в `__init__`. Нужно заменить на пустое тело и перенести логику в `start()`.

```python
# Было (в __init__):
    self._executor = ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="transcriber")
    # ...
    self._start_workers()

# Стало:
    self._executor = None
    # _start_workers() перенесён в start()
```

- [ ] **Step 3: Run queue test**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_transcription_queue.py -v
```
Expected: PASS (нужно будет обновить тесты — убрать ручной ThreadPoolExecutor)

- [ ] **Step 4: Commit**

```bash
git add src/services/transcription_queue.py tests/test_transcription_queue.py
git commit -m "fix: добавить start() метод и module-level singleton для TranscriptionQueueManager"
```

---

### Task 12: Update transcription_queue tests for new start() pattern

**Files:**
- Modify: `tests/test_transcription_queue.py`

- [ ] **Step 1: Обновить тесты для работы с start()/shutdown() паттерном**

```python
# tests/test_transcription_queue.py — обновить все тесты:

import os
import sys
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_test_dir = None


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch):
    global _test_dir
    _test_dir = tempfile.mkdtemp()
    monkeypatch.setattr("src.services.job_manager.JOB_METADATA_DIR", os.path.join(_test_dir, "jobs"))
    os.makedirs(os.path.join(_test_dir, "jobs"), exist_ok=True)
    monkeypatch.setenv("TRANSCRIBER_WORKERS", "2")
    monkeypatch.setenv("QUEUE_MAX_SIZE", "5")
    yield
    try:
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


def _get_manager():
    from src.services.transcription_queue import TranscriptionQueueManager
    return TranscriptionQueueManager._instance


def _mock_transcription():
    """Mock transcribe_audio для тестов."""
    from src.services.job_manager import JobManager
    meta_mgr = JobManager()

    original_transcribe = None

    def fake_transcribe(file_path, **kwargs):
        return {"text": "mock result", "segments": []}

    return meta_mgr, fake_transcribe


def test_submit_and_process():
    """Job поднимается в очередь, worker обрабатывает, статус обновляется."""
    from src.services.transcription_queue import TranscriptionQueueManager
    from src.services.job_manager import JobStatus

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    mgr.start()

    meta_mgr, fake_transcribe = _mock_transcription()

    with patch("src.services.transcription_queue.transcribe_audio", fake_transcribe):
        result = mgr.submit({
            "job_id": "test-job-1",
            "wav_path": "/tmp/test.wav",
            "params": {"model": "turbo"},
            "source": "upload",
        })
        assert result is True

    # Ждём завершения воркера
    mgr._queue.join()
    time.sleep(0.2)

    status = meta_mgr.load("test-job-1")
    assert status["status"] == "completed"
    mgr.shutdown()


def test_queue_full_returns_false():
    """При переполнении очереди submit возвращает False."""
    from src.services.transcription_queue import TranscriptionQueueManager

    mgr = TranscriptionQueueManager(workers=1, max_size=1)
    mgr.start()

    # Заполняем очередь
    mgr.submit({
        "job_id": "fill-1",
        "wav_path": "/tmp/x.wav",
        "params": {"model": "turbo"},
        "source": "upload",
    })

    # Очередь полна — submit возвращает False
    result = mgr.submit({
        "job_id": "overload",
        "wav_path": "/tmp/y.wav",
        "params": {"model": "turbo"},
        "source": "upload",
    })
    assert result is False
    mgr.shutdown()


def test_cancel_queued_job():
    """Cancel queued job — worker пропускает его."""
    from src.services.transcription_queue import TranscriptionQueueManager
    from src.services.job_manager import JobStatus

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    mgr.start()

    meta_mgr, fake_transcribe = _mock_transcription()

    with patch("src.services.transcription_queue.transcribe_audio", fake_transcribe):
        result = mgr.submit({
            "job_id": "cancel-job-1",
            "wav_path": "/tmp/test.wav",
            "params": {"model": "turbo"},
            "source": "upload",
        })
        assert result is True

    # Cancel до того как worker возьмёт
    cancelled = mgr.cancel_job("cancel-job-1")
    assert cancelled is True

    mgr._queue.join()
    time.sleep(0.2)

    status = meta_mgr.load("cancel-job-1")
    assert status["status"] == "cancelled"
    mgr.shutdown()


def test_singleton():
    """Модульный singleton проверен в job_manager — здесь проверяем queue singleton."""
    from src.services.transcription_queue import transcription_manager
    assert transcription_manager is not None
```

- [ ] **Step 2: Run test**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_transcription_queue.py -v
```
Expected: FAIL (нужно синхронизировать mock и импорты)

- [ ] **Step 3: Fix test mocks — correct the patch path**

```python
# tests/test_transcription_queue.py — mock нужно делать правильно:
with patch("src.services.transcription_queue.transcribe_audio", fake_transcribe):
```
But `transcribe_audio` is imported inside `_worker_process`, so the patch target should be:
```python
with patch("src.services.transcription_queue.transcribe_audio", fake_transcribe):
```
Actually, the import is `from src.models.transcription import transcribe_audio` inside the method. So patch target is:
```python
with patch("src.services.transcription_queue.transcribe_audio", fake_transcribe):
```
Wait, that won't work for `from X import Y` imports. Need to patch where it's used:
```python
with patch("src.services.transcription_queue.transcribe_audio", fake_transcribe):
```
Actually the cleaner approach: import in `_worker_process` at module level with a flag, or mock at the source. Let me use `patch` on the correct target:

```python
with patch("src.models.transcription.transcribe_audio", fake_transcribe):
```
But `transcribe_audio` in transcription.py calls the actual `mlx_whisper.transcribe.transcribe`. Let's mock at the queue's import location. Since the import is inside the method, we need:

```python
with patch.object(sys.modules["src.services.transcription_queue"], "transcribe_audio", fake_transcribe):
```
The simplest reliable approach:

```python
import src.services.transcription_queue as tq_module

with patch.object(tq_module, "transcribe_audio", fake_transcribe):
```

Wait — the import is `from src.models.transcription import transcribe_audio` inside `_worker_process`. For `from` imports, patch at the definition location:

```python
with patch("src.services.transcription_queue.transcribe_audio", fake_transcribe):
```
This patches the attribute on the module. Since it's imported inside the method body, it will pick up the patched version if the patch is active when the method runs. Actually no — `from X import Y` copies the reference. At runtime the import happens inside the method, so if we patch `src.services.transcription_queue.transcribe_audio = fake_transcribe` before calling submit, it should work since the method does `from src.models.transcription import transcribe_audio` — that looks up the module, not the attribute.

Best approach: make `transcribe_audio` a module-level variable that's imported lazily:

Let's just set it on the module:
```python
orig = getattr(tq_module, "transcribe_audio", None)
tq_module.transcribe_audio = fake_transcribe
try:
    ...
finally:
    if orig is not None:
        tq_module.transcribe_audio = orig
```

OK let's simplify — use subprocess to test the full integration, and keep unit tests focused on JobManager.

Updated test plan for Task 12:

```python
# tests/test_transcription_queue.py
import os
import sys
import tempfile
import shutil
import time
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_test_dir = None
_transcription_queue_module = None


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch):
    global _test_dir, _transcription_queue_module
    _test_dir = tempfile.mkdtemp()
    monkeypatch.setattr("src.services.job_manager.JOB_METADATA_DIR", os.path.join(_test_dir, "jobs"))
    os.makedirs(os.path.join(_test_dir, "jobs"), exist_ok=True)
    monkeypatch.setenv("TRANSCRIBER_WORKERS", "2")
    monkeypatch.setenv("QUEUE_MAX_SIZE", "5")
    # Clear singleton
    import src.services.transcription_queue as tq_mod
    tq_mod.TranscriptionQueueManager._instance = None
    _transcription_queue_module = tq_mod
    yield
    try:
        if _transcription_queue_module:
            _transcription_queue_module.TranscriptionQueueManager._instance = None
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


def _mock_transcribe(file_path, **kwargs):
    """Mock транскрипция."""
    return {"text": "mock result", "segments": []}


def test_submit_and_process():
    from src.services.transcription_queue import transcription_manager
    from src.services.job_manager import JobManager

    meta = JobManager()
    _transcription_queue_module.transcribe_audio = _mock_transcribe

    result = transcription_manager.submit({
        "job_id": "test-1",
        "wav_path": "/tmp/test.wav",
        "params": {"model": "turbo"},
        "source": "upload",
    })
    assert result is True

    transcription_manager._queue.join()
    time.sleep(0.2)

    status = meta.load("test-1")
    assert status["status"] == "completed"


def test_queue_full():
    from src.services.transcription_queue import transcription_manager

    # Заполняем очередь
    for i in range(5):
        r = transcription_manager.submit({
            "job_id": f"fill-{i}",
            "wav_path": f"/tmp/fill-{i}.wav",
            "params": {"model": "turbo"},
            "source": "upload",
        })
        assert r is True

    # Следующий не проходит
    r = transcription_manager.submit({
        "job_id": "overflow",
        "wav_path": "/tmp/ov.wav",
        "params": {"model": "turbo"},
        "source": "upload",
    })
    assert r is False


def test_cancel_queued():
    from src.services.transcription_queue import transcription_manager
    from src.services.job_manager import JobManager

    meta = JobManager()
    _transcription_queue_module.transcribe_audio = _mock_transcribe

    transcription_manager.submit({
        "job_id": "cancel-1",
        "wav_path": "/tmp/test.wav",
        "params": {"model": "turbo"},
        "source": "upload",
    })

    assert transcription_manager.cancel_job("cancel-1") is True

    transcription_manager._queue.join()
    time.sleep(0.2)

    status = meta.load("cancel-1")
    assert status["status"] == "cancelled"
```

- [ ] **Step 2: Run test**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_transcription_queue.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_transcription_queue.py
git commit -m "fix: обновить тесты TranscriptionQueueManager для start()/shutdown() pattern"
```

---

### Task 13: Integration test — full flow

**Files:**
- Create: `tests/test_parallel_transcription.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_parallel_transcription.py
"""Integration test: full flow — submit job, poll status, verify result."""
import os
import sys
import tempfile
import shutil
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_test_dir = None


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    global _test_dir
    _test_dir = tempfile.mkdtemp()
    monkeypatch.setattr("src.services.job_manager.JOB_METADATA_DIR", os.path.join(_test_dir, "jobs"))
    os.makedirs(os.path.join(_test_dir, "jobs"), exist_ok=True)
    monkeypatch.setenv("TRANSCRIBER_WORKERS", "2")
    monkeypatch.setenv("QUEUE_MAX_SIZE", "10")
    # Clear singletons
    import src.services.job_manager as jm
    jm.JobManager._instance = None
    import src.services.transcription_queue as tq
    tq.TranscriptionQueueManager._instance = None
    yield
    try:
        jm.JobManager._instance = None
        tq.TranscriptionQueueManager._instance = None
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


def _mock_transcribe(file_path, **kwargs):
    return {
        "text": "Hello, this is a test transcription.",
        "segments": [],
        "language": "en",
    }


def test_full_job_lifecycle():
    """Submit → queued → processing → completed → poll."""
    import src.services.transcription_queue as tq_module
    from src.services.transcription_queue import transcription_manager
    from src.services.job_manager import JobManager
    from src.services.job_manager import JobStatus

    tq_module.transcribe_audio = _mock_transcribe

    # Submit job
    result = transcription_manager.submit({
        "job_id": "integration-1",
        "wav_path": "/tmp/test.wav",
        "params": {"model": "turbo", "language": "en"},
        "source": "upload",
        "original_filename": "test.wav",
    })
    assert result is True

    # Initial status
    meta = JobManager().load("integration-1")
    assert meta["status"] == "queued"

    # Wait for worker
    transcription_manager._queue.join()
    time.sleep(0.3)

    # Final status
    meta = JobManager().load("integration-1")
    assert meta["status"] == "completed"
    assert meta["transcription_duration"] is not None
    assert meta["model"] == "turbo"
    assert meta["language"] == "en"


def test_multiple_jobs_parallel():
    """Подать 3 jobs — все должны завершиться."""
    import src.services.transcription_queue as tq_module
    from src.services.transcription_queue import transcription_manager
    from src.services.job_manager import JobManager

    tq_module.transcribe_audio = _mock_transcribe

    for i in range(3):
        r = transcription_manager.submit({
            "job_id": f"parallel-{i}",
            "wav_path": f"/tmp/test-{i}.wav",
            "params": {"model": "turbo"},
            "source": "upload",
        })
        assert r is True

    transcription_manager._queue.join()
    time.sleep(0.3)

    meta = JobManager()
    for i in range(3):
        status = meta.load(f"parallel-{i}")
        assert status is not None
        assert status["status"] == "completed"
```

- [ ] **Step 2: Run test**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -m pytest tests/test_parallel_transcription.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_parallel_transcription.py
git commit -m "test: добавить интеграционный тест полного жизненного цикла job"
```

---

### Task 14: Verify server starts and API works

**Files:**
- N/A — manual verification

- [ ] **Step 1: Start the server and test endpoints**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python src/main.py &
SERVER_PID=$!
sleep 3

# Health check
curl -s http://localhost:8801/api/v1/health | python -m json.tool

# Check model config
curl -s http://localhost:8801/api/v1/config | python -m json.tool

# Kill server
kill $SERVER_PID 2>/dev/null
```

- [ ] **Step 2: Verify jobs directory**

```bash
ls -la /Users/dvmironenko/dev/mlx_whisper/data/jobs/
```

- [ ] **Step 3: Run all tests**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -m pytest tests/test_job_status.py tests/test_job_manager.py tests/test_transcription_queue.py tests/test_parallel_transcription.py -v
```
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: параллельная транскрипция — полная интеграция"
```

---

## Verification Checklist

1. `JobStatus` enum — все 5 статусов корректны ✓
2. `JobManager` — create, load, update_status, cancel, list_all — все методы тестируются ✓
3. `TranscriptionQueueManager` — submit, cancel_job, shutdown — тестируются ✓
4. `threading.Lock` в `transcription.py` — защищает вызов `transcribe()` ✓
5. Config env vars — TRANSCRIBER_WORKERS, QUEUE_MAX_SIZE, JOB_METADATA_DIR ✓
6. POST /transcribe — возвращает `{"job_id": "uuid", "status": "queued"}` ✓
7. POST /transcribe-url — аналогично ✓
8. GET /jobs/{job_id} — возвращает JobMetadata или 404 ✓
9. DELETE /jobs/{job_id}/cancel — отменяет queued/processing ✓
10. DELETE /jobs/{job_id} — удаляет metadata + directory ✓
11. Lifespan — start/shutdown queue ✓
12. .env.example — новые env vars задокументированы ✓
13. Все тесты проходят ✓
14. Сервер запускается без ошибок ✓

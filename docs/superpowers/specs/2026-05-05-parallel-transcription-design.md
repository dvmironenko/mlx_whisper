# Параллельная транскрипция через ThreadPoolExecutor + Queue

## Context

Проект mlx_whisper v1.3.0 — сервис транскрипции аудио/видео через MLX Whisper. Текущие эндпоинты `POST /transcribe` и `POST /transcribe-url` вызывают `transcribe_audio()` синхронно — при транскрипции большого файла эндпоинт блокируется на десятки секунд или минуты, другие запросы не обрабатываются.

**Цель:** добавить параллельную обработку нескольких файлов через `ThreadPoolExecutor` + `queue.Queue`, fire-and-forget API с poll-статусом, tracking job-статусов через JSON-файлы.

## Constraints

- **2-3 параллельных воркера** (конфигурируется через `TRANSCRIBER_WORKERS`)
- **Очередь с лимитом** (конфигурируется через `QUEUE_MAX_SIZE`, default 20; при переполнении — 503)
- **Один экземпляр модели на все потоки**, protected by `threading.Lock`
- **Job metadata в filesystem** — `data/jobs/{job_id}.json`
- **Статусы:** `queued`, `processing`, `completed`, `failed`, `cancelled`
- **Graceful shutdown** — завершение текущих jobs, drain очереди, выход
- Существующий `ThreadPoolExecutor` для report generation **не трогать** — он отдельный

## Architecture

```
                        +---------------------------+
                        |      FastAPI App          |
                        +-------------+-------------+
                                      |
              +---------------------------------------------------+
              |        TranscriptionQueueManager (singleton)       |
              |                                                    |
              |  + ThreadPoolExecutor (N workers)                  |
              |  |                                                  |
              |  |  +---+  +---+  +---+                           |
              |  |  | W1|  | W2|  | W3|     (worker threads)      |
              |  |  +---+  +---+  +---+                           |
              |  +------------------------------------------------+
              |           ^        |                              |
              |           |        v                              |
              |  +---------------------+                          |
              |  |  queue.Queue (bounded) |  <-- threading.Lock   |
              |  +---------------------+      (модель общая)      |
              +---------------------------------------------------+
```

## New Files

### `src/services/__init__.py`
Пустой файл для package.

### `src/services/job_manager.py`
`JobManager` — singleton для управления job metadata:
- `create(job_id, source, params)` — создать JSON, статус `queued`
- `update_status(job_id, status, extra)` — обновить статус и доп. поля
- `load(job_id)` — загрузить metadata
- `cancel(job_id)` — отметить `cancelled`
- `list_all()` — список всех jobs

### `src/services/transcription_queue.py`
`TranscriptionQueueManager` — singleton для очереди транскрипции:
- `start()` — запустить N worker threads (из lifespan)
- `submit(job_payload)` — положить job в очередь, return False если full
- `cancel_job(job_id)` — отметить cancelled
- `shutdown()` — graceful shutdown: drain + exit
- `_worker_loop(worker_id)` — main loop: get(job, timeout=1.0) → check cancelled → transcribe → update status → task_done()

## Modified Files

### `src/config.py` (+7 строк)
Добавить после line 79:
```python
TRANSCRIBER_WORKERS: int = int(os.getenv("TRANSCRIBER_WORKERS", "3"))
QUEUE_MAX_SIZE: int = int(os.getenv("QUEUE_MAX_SIZE", "20"))
JOB_METADATA_DIR: str = os.path.join("data", "jobs")
os.makedirs(JOB_METADATA_DIR, exist_ok=True)
```

### `src/main.py` (+4 строки)
В `lifespan()`:
```python
from src.services.transcription_queue import transcription_manager
transcription_manager.start()
yield
transcription_manager.shutdown()
```

### `src/api/router.py` (significant changes)
- `POST /transcribe` (line ~103-310) — после валидации и сохранения WAV → создать job metadata → положить в очередь → вернуть `{"job_id", "status": "queued"}`
- `POST /transcribe-url` (line ~345-494) — аналогично
- `GET /jobs/{job_id}` (line ~503-507) — заменить stub на `job_manager.load()`
- `DELETE /jobs/{job_id}` (line ~537-544) — расширить: если terminal status → delete metadata + directory
- Новый `DELETE /jobs/{job_id}/cancel` — отмена queued/processing jobs

### `src/models/transcription.py` (+3 строки)
Добавить `_transcription_lock = threading.Lock()` и обернуть вызов `transcribe()`:
```python
with _transcription_lock:
    result = transcribe(audio=file_path, path_or_hf_repo=model_path, **transcribe_options)
```

## Data Structures

### JobStatus (enum)
```python
class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### JobMetadata (dataclass → JSON)
```json
{
    "job_id": "550e8400-...",
    "status": "queued",
    "source": "upload|url",
    "created_at": "2026-05-05T14:30:00Z",
    "updated_at": "2026-05-05T14:30:00Z",
    "original_filename": "meeting.webm",
    "model": "turbo",
    "language": "ru",
    "task": "transcribe",
    "word_timestamps": false,
    "duration": 180.5,
    "transcription_duration": 45.2,
    "result_file": "meeting.txt",
    "error": null
}
```

### JobPayload (внутри очереди)
```python
@dataclass
class JobPayload:
    job_id: str
    wav_path: str
    params: dict                    # все параметры транскрипции
    cancelled: bool = False
```

## API Changes

| Endpoint | Response |
|----------|----------|
| `POST /transcribe` | `{"job_id": "uuid", "status": "queued"}` |
| `POST /transcribe-url` | `{"job_id": "uuid", "status": "queued"}` |
| `GET /jobs/{job_id}` | Полный JobMetadata JSON |
| `DELETE /jobs/{job_id}/cancel` | `{"job_id": "uuid", "status": "cancelled"}` |
| Queue full | 503 `{"detail": "Queue is full"}` |

## Error Handling

- **Очередь полна** → 503
- **Job не найден** → 404
- **Cancel processing job** → MLX не умеет abort, статус станет `cancelled` после завершения текущей транскрипции
- **Ошибка транскрипции** → статус `failed`, `error` поле заполнено
- **Процесс упал (OOM)** → orphaned files, future cleanup script

## Config (env vars)

| Var | Default | Description |
|-----|---------|-------------|
| `TRANSCRIBER_WORKERS` | 3 | Количество воркеров |
| `QUEUE_MAX_SIZE` | 20 | Максимум job в очереди |

## Reuse (не менять)

- `ModelCache` — синглтон, уже thread-safe для read-after-write
- `build_job_path()` — создание `data/{job_id}/`
- `convert_to_wav()` — FFmpeg конвертация
- `_report_executor` — отдельный от транскрипции
- `/files/{filename}/download`, `/files/{filename}/content` — unchanged
- `sanitize_result()` — переиспользовать в worker

## Potential Pitfalls

1. **GIL:** MLX Ops releases GIL, GPU-вычисления параллельны. Lock только для model loading/ModelHolder state.
2. **Model state corruption:** Lock на `transcribe()` предотвращает race condition в `ModelHolder`.
3. **Race cancel vs processing:** Accept in-progress cannot be aborted; override status to `cancelled` after completion.
4. **JSON file races:** Each job has unique ID, one worker per job, atomic write. No contention.

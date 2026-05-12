# Queue Integration Design

> **Goal:** Подключить сервисный слой очереди транскрипции (`TranscriptionQueueManager` + `JobManager`) к API и инициализации сервера, превратив синхронный `/transcribe` в асинхронный через очередь.

**Architecture:** Service layer wraps `TranscriptionQueueManager`. Router becomes a thin layer: validates input, delegates to service, formats responses.

**Tech Stack:** Python 3.12, FastAPI, ThreadPoolExecutor, JSON filesystem metadata.

---

## Сервисный слой

### Новый файл: `src/services/transcription_service.py`

Обёртка над `TranscriptionQueueManager`. Инкапсулирует логику submission и retrieval.

```python
class TranscriptionService:
    def __init__(self, queue_manager: TranscriptionQueueManager, job_manager: JobManager): ...

    def submit(
        self,
        wav_path: str,
        job_id: str,
        original_filename: str,
        model: str,
        language: str | None,
        task: str,
        word_timestamps: bool,
        condition_on_previous_text: bool,
        no_speech_threshold: float | None,
        hallucination_silence_threshold: float | None,
        initial_prompt: str | None,
        duration: float | None,
    ) -> tuple[str, bool]:  # (job_id, success)

    def get_job(self, job_id: str) -> dict | None: ...

    def list_jobs(self) -> list[dict]: ...

    def cancel_job(self, job_id: str) -> bool: ...
```

`submit()` формирует payload из параметров и делегирует `queue_manager.submit()`. `get_job()` делегирует `job_manager.load()` и объединяет metadata с файлами результата (текст, segments).

### Данные для ответа `GET /jobs/{job_id}`

Когда статус `completed`, ответ включает:
- Все поля metadata (`job_id`, `status`, `created_at`, `updated_at`, `original_filename`, `model`, `language`, `task`, `word_timestamps`, `duration`, `transcription_duration`)
- `text` — содержимое основного .txt файла (если completed/failed)
- `segments` — массив segments из .json (если word_timestamps=true и completed)
- `error` — сообщение ошибки (если failed/cancelled)
- `files` — список файлов в директории задания (для скачивания)

Когда статус `queued`/`processing` — только metadata, без text/segments.

---

## Изменения в API Router

### `POST /api/v1/transcribe`

**Было:** Синхронная транскрипция, файл сохраняется, WAV конвертируется, результат возвращается сразу.

**Станет:**
1. Валидация файла и параметров (без изменений)
2. Сохранение оригинала в `data/uploads/{job_id}/{filename}`
3. Конвертация в WAV
4. Получение длительности аудио
5. Вызов `transcription_service.submit()`
6. Возврат `{"job_id": "...", "status": "queued"}`

Важно: WAV и txt-файлы сохраняются воркером в `_worker_process()`. Endpoint не сохраняет результат.

### `POST /api/v1/transcribe-url`

Аналогично — replace синхронный call на `transcription_service.submit()`. Скачанный файл конвертируется в WAV, затем submit в очередь.

### `GET /api/v1/jobs/{job_id}`

**Было:** Хардкод `{"job_id": job_id, "status": "pending"}`.

**Станет:** Вызов `transcription_service.get_job(job_id)`. Возврат metadata + результат (если completed).

### `GET /api/v1/jobs`

**Было:** Сканирование `data/uploads/` на файловой системе.

**Станет:** Вызов `transcription_service.list_jobs()` → `JobManager.list_all()`. Возврат списка всех jobs с metadata.

### `DELETE /api/v1/jobs/{job_id}`

**Было:** `shutil.rmtree()` директории.

**Станет:** Сначала `transcription_service.cancel_job(job_id)`. Если job в queued/processing — отменяет. Затем удаляет файлы директории. Возвращает статус отмены.

### `DELETE /api/v1/jobs/{job_id}/files/{filename}`

Без изменений — работает с файловой системой напрямую.

### `GET /files/{filename}/download` и `GET /files/{filename}/content`

Без изменений.

---

## Изменения в main.py

**Лейфспан:**
- On startup: после preloading model — инициализировать `get_transcription_manager()` (ленивый синглтон)
- On shutdown: `get_transcription_manager().shutdown()`

---

## Flow данных

```
Клиент → POST /api/v1/transcribe (файл)
  ├─ Router валидирует file, params
  ├─ Сохраняет оригинал + конвертирует WAV
  ├─ TranscriptionService.submit()
  │   └─ TranscriptionQueueManager.submit()
  │       └─ JobManager.create() → data/jobs/{job_id}.json
  │       └─ Queue.put(JobPayload)
  └─ Возврат: {"job_id": "uuid", "status": "queued"}

Клиент → GET /api/v1/jobs/{job_id}
  └─ TranscriptionService.get_job()
      └─ JobManager.load() → metadata
      └─ При completed: чтение txt, json из data/uploads/{job_id}/
  └─ Возврат: metadata + {text, segments, files, ...}

Worker (фоновый)
  └─ Queue.get() → JobPayload
  └─ JobManager.update_status(PROCESSING)
  └─ transcribe_audio() → result
  └─ _sanitize_result()
  └─ JobManager.update_status(COMPLETED/FAILED/CANCELLED)
  └─ _clear_memory()
```

---

## Обработка ошибок

- **Queue full:** `submit()` возвращает `False` → router 429 Too Many Requests
- **Job not found:** `GET /jobs/{id}` → 404
- **Invalid job_id:** `GET /jobs/{id}` → 404 (JobManager.load возвращает None)
- **Worker exception:** JobManager.update_status(FAILED, error=...) → клиент видит ошибку в GET

## Тестирование

- Существующие 5 тестов `test_transcription_queue.py` — без изменений
- Существующие 5 тестов `test_job_manager.py` — без изменений
- 2 теста `test_job_status.py` — без изменений
- Новые интеграционные тесты (по возможности):
  - `test_transcribe_endpoint_submits_to_queue` — POST возвращает job_id
  - `test_get_job_returns_metadata` — GET возвращает статус из JobManager
  - `test_list_jobs_uses_job_manager` — GET /jobs через JobManager.list_all()
  - `test_cancel_job_uses_queue_manager` — DELETE вызывает cancel_job()

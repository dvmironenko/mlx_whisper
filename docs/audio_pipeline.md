# Аудио пайплайн MLX-Whisper

Документ описывает полный цикл обработки аудиофайла — от загрузки через веб-интерфейс до генерации результатов транскрибации.

## Обзор

```
Загрузка файла  →  Конвертация в WAV  →  Очередь задач  →  Транскрипция  →  Результаты
     │                  │                    │                │              │
 POST              FFmpeg             ThreadPool        Whisper /     txt,
 /api/v1          16kHz mono          Executor          VibeVoice     segments
 /transcribe       16-bit PCM         + JobMgr                              .json
```

---

## 1. Загрузка файла

### HTTP POST `/api/v1/transcribe`

**Файл:** [`src/api/router.py`](../src/api/router.py)

Клиент отправляет `multipart/form-data` с файлом и параметрами транскрипции.

#### Валидация

| Параметр | Что проверяется | Код ошибки |
|----------|-----------------|------------|
| `filename` | Не `None` | 400 |
| Расширение | `AUDIO_EXTENSIONS` (.wav, .mp3, .m4a, .flac, .aac, .ogg, .wma, .webm, .mp4, .mkv) | 400 |
| Модель | `SUPPORTED_MODELS` (tiny, base, small, medium, turbo, large) | 400 |
| Размер | `Content-Length` заголовок ≤ `MAX_FILE_SIZE` (500 MB) | 413 |

#### Маршрутизация параметров формы

Параметры формы делятся на три категории: параметры для Whisper-движка, параметры для FFmpeg-конвертации и общие параметры.

| Параметр | Категория | Куда передаётся | Описание |
|----------|-----------|-----------------|----------|
| `model` | Whisper | `TranscriptionEngine.transcribe()` | Модель MLX-Whisper (tiny, base, small, medium, turbo, large) |
| `task` | Whisper | `TranscriptionEngine.transcribe()` | Задача: `transcribe` или `translate` |
| `word_timestamps` | Whisper | `TranscriptionEngine.transcribe()` | Возвращать таймстампы для каждого слова |
| `condition_on_previous` | Whisper | `TranscriptionEngine.transcribe()` | Учитывать предыдущий текст при генерации |
| `initial_prompt` | Whisper | `TranscriptionEngine.transcribe()` | Начальный промпт для улучшения качества |
| `language` | Оба механизма | `TranscriptionEngine.transcribe()` / `VibeVoiceEngine._transcribe_segment()` | Язык аудио (None = auto-detect) |
| `no_speech_threshold` | Whisper | `TranscriptionEngine.transcribe()` | Порог для пропуска сегментов без речи |
| `hallucination_silence_threshold` | Whisper | `TranscriptionEngine.transcribe()` | Порог для отсеивания галлюцинаций |
| `remove_silence` | FFmpeg | `convert_to_wav()` | Удалять тишину при конвертации |
| `silence_threshold` | FFmpeg | `convert_to_wav()` | Порог тишины в dB для фильтра `silenceremove` |
| `silence_duration` | FFmpeg | `convert_to_wav()` | Минимальная длительность тишины для удаления (сек) |
| `file` | — | сохранение оригинала | Аудиофайл для загрузки |

**Важно:** Параметр `model` игнорируется при `mechanism=vibevoice` — VibeVoice использует модель `OMLX_MODEL` из конфигурации.

**Файлы реализации:**
- Маршрутизация: [`src/api/router.py`](../src/api/router.py) — `POST /api/v1/transcribe` (строки 219-229)
- FFmpeg конвертация: [`src/utils/audio.py`](../src/utils/audio.py) — `convert_to_wav()`
- Whisper-движок: [`src/services/transcription_engines.py`](../src/services/transcription_engines.py) — `WhisperEngine.transcribe()`

#### Сохранение оригинала

1. Файл читается порциями по `CHUNK_SIZE` (8 КБ) и записывается во временный файл `uploads/tmp_{filename}`.
2. Генерируется `job_id` (UUID4).
3. Создаётся директория задания: `data/{job_id}/` — [`build_job_path()`](../src/utils/files.py).
4. Оригинальный файл копируется в `data/{job_id}/{filename}`.
5. Через `ffprobe` определяется длительность аудио.

#### Конвертация в WAV

Файл конвертируется в стандартизированный формат с помощью FFmpeg:

```bash
ffmpeg -i input.mp3 \
    -acodec pcm_s16le \
    -ar 16000 \
    -ac 1 \
    output.wav
```

- **Формат:** PCM 16-bit little-endian
- **Частота дискретизации:** 16000 Гц
- **Каналы:** 1 (mono)

Опционально применяется удаление тишины (фильтр `silenceremove`).

Конвертированный WAV сохраняется как `{filename}_converted.wav` в директории задания.

#### Параметры по умолчанию

| Параметр | Значение по умолчанию | Источник |
|----------|----------------------|----------|
| Модель | `turbo` | `DEFAULT_MODEL` env |
| Задача | `transcribe` | `DEFAULT_TASK` env |
| Word timestamps | `false` | `DEFAULT_WORD_TIMESTAMPS` env |
| Condition on previous | `true` | `DEFAULT_CONDITION_ON_PREVIOUS` env |
| Remove silence | `true` | `REMOVE_SILENCE` env |
| Silence threshold | -45.0 dB | `SILENCE_THRESHOLD` env |
| Silence duration | 1.0 сек | `SILENCE_DURATION` env |
| No speech threshold | 0.4 | `NO_SPEECH_THRESHOLD` env |
| Hallucination silence | 0.8 | `HALLUCINATION_SILENCE_THRESHOLD` env |

#### Ответ

```json
{ "job_id": "uuid", "status": "queued" }
```

Временный файл удаляется в `finally` блоке.

---

## 2. Конвертация аудио

**Файл:** [`src/utils/audio.py`](../src/utils/audio.py)

### `convert_to_wav()`

Конвертирует любой поддерживаемый аудиоформат в WAV (16kHz, mono, 16-bit PCM).

#### Без удаления тишины

```bash
ffmpeg -i input -acodec pcm_s16le -ar 16000 -ac 1 output.wav
```

#### С удалением тишины

```bash
ffmpeg -i input \
    -acodec pcm_s16le -ar 16000 -ac 1 \
    -af "silenceremove=stop_periods=-1:stop_duration={silence_duration}:stop_threshold={silence_threshold}dB" \
    output.wav
```

- `stop_periods=-1` — удалять все сегменты тишины
- `stop_duration` — минимальная длительность тишины для удаления (по умолчанию 1.0 сек)
- `stop_threshold` — порог тишины в dB (по умолчанию -45.0)

#### Обработка ошибок

| Сценарий | Исключение |
|----------|-----------|
| Таймаут (по умолчанию 600 сек) | `RuntimeError("Conversion timed out...")` |
| FFmpeg не установлен | `RuntimeError("FFmpeg not found...")` |
| Ошибка конвертации | `RuntimeError("FFmpeg conversion failed: ...")` |

### `validate_audio_file()` / `get_audio_duration()`

Используют `ffprobe` для проверки валидности и получения длительности аудиофайла.

```bash
ffprobe -v error -show_entries format=duration \
    -of default=noprint_wrappers=1:nokey=1 input.wav
```

---

## 3. Очередь задач

**Файл:** [`src/services/transcription_queue.py`](../src/services/transcription_queue.py)

### TranscriptionQueueManager

Singleton, управляющий параллельной обработкой задач транскрипции.

#### Конфигурация

| Параметр | Значение | Описание |
|----------|----------|----------|
| `TRANSCRIBER_WORKERS` | 3 | Количество рабочих потоков |
| `QUEUE_MAX_SIZE` | 20 | Максимальный размер очереди |

#### Job states

```
QUEUED → PROCESSING → COMPLETED
                      → FAILED
                      → CANCELLED
```

#### Структура

```
TranscriptionQueueManager
├── ThreadPoolExecutor (3 workers)
├── Queue (maxsize=20)
├── JobManager (метаданные заданий)
└── _transcription_lock (однопоточная транскрипция)
```

**Важно:** Несмотря на 3 рабочих потока, транскрипция выполняется последовательно благодаря `_transcription_lock` — одновременно обрабатывается только одна задача.

#### Методы

| Метод | Описание |
|-------|----------|
| `submit(payload)` | Добавить задачу в очередь |
| `cancel_job(job_id)` | Отменить задачу (QUEUED/PROCESSING) |
| `shutdown()` | Грациозная остановка |

---

## 4. Транскрипция

### 4.1. Whisper MLX (локальная модель)

**Файл:** [`src/services/transcription_engines.py`](../src/services/transcription_engines.py)

`WhisperEngine` использует `mlx_whisper.transcribe.transcribe` через `ModelCache` singleton.

#### Кэширование моделей

`ModelCache` загружает MLX модель один раз и переиспользует для всех запросов. Это значительно ускоряет повторные транскрипции.

#### Память

После завершения транскрипции вызывается `_clear_memory()`:

```python
import mlx.core as mx
import gc
mx.clear_cache()
gc.collect()
```

Это освобождает GPU память для следующих задач.

### 4.2. VibeVoice (oMLX API)

**Файл:** [`src/services/vibevoice_engine.py`](../src/services/vibevoice_engine.py)

`VibeVoiceEngine` транскрибирует аудио через облачный oMLX API.

#### Разбиение аудио

Длинное аудио разбивается на сегменты:

1. **librosa** загружает аудио (16kHz, mono)
2. **`librosa.effects.split()`** находит сегменты речи (порог тишины 40 dB)
3. Интервалы с паузами < 2 сек объединяются
4. Сегменты > 50 минут разбиваются на части

#### API запрос

```
POST {OMLX_BASE_URL}/audio/transcriptions
Authorization: Bearer {OMLX_API_KEY}
Content-Type: multipart/form-data
```

Параметры: `model`, `language`

#### Парсинг ответа

Многоуровневый парсер обрабатывает несколько форматов ответа от oMLX API:

1. Прямой JSON-массив сегментов
2. Конкатенированные JSON-объекты
3. JSON в markdown code block (```json)
4. Regex-извлечение из обрезанного текста
5. Fallback: текстовый формат `[MM:SS] Speaker N: text`

#### Идентификаторы спикеров

ID спикеров возвращаются oMLX API (0, 1, 2+) и доступны в полях `speaker` сегментов.

#### Константы

| Константа | Значение | Описание |
|-----------|----------|----------|
| `MAX_AUDIO_DURATION_SEC` | 3000 (50 мин) | Макс. длительность сегмента |
| `SILENCE_THRESHOLD_DB` | 40 | Порог тишины для split |
| `MAX_UPLOAD_BYTES` | 100 MB | Макс. размер файла для API |

---

## 5. Сохранение результатов

**Файл:** [`src/services/transcription_queue.py`](../src/services/transcription_queue.py) → `_worker_process()`

После завершения транскрипции результаты сохраняются в директорию задания `data/{job_id}/`:

### Генерируемые файлы

| Файл | Описание |
|------|----------|
| `{original_name}.txt` | Полный текст транскрипции |
| `{original_name}_segments.json` | Сегменты с временными метками |
| `{original_name}_raw.json` | Сырой ответ API (если есть) |

### Структура segments.json

```json
{
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.5,
      "text": "Текст сегмента",
      "words": [...]
    },
    ...
  ]
}
```

### Обновление статуса

JobManager обновляет статус задачи:

```python
self._meta.update_status(
    job_id,
    JobStatus.COMPLETED,  # или FAILED/CANCELLED
    transcription_duration=duration,
    result_file=result.get("result_file"),
)
```

---

## Полная схема данных

```
┌──────────────────────────────────────────────────────────────────┐
│                         КЛИЕНТ                                    │
│  POST /api/v1/transcribe (multipart/form-data)                   │
│  file=audio.mp3, mechanism=whisper, model=turbo, language=ru     │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  router.py: POST /api/v1/transcribe                               │
│                                                                    │
│  1. Валидация (extension, model, size)                             │
│  2. Сохранение: uploads/tmp_{filename}                             │
│  3. job_id = uuid4()                                              │
│  4. Копирование: data/{job_id}/{filename}                          │
│  5. ffprobe → audio_duration                                       │
│  6. convert_to_wav() → data/{job_id}/{filename}_converted.wav     │
│  7. mgr.submit(...)                                               │
│  8. delete_file(tmp_path)                                         │
│                                                                    │
│  ← { "job_id": "...", "status": "queued" }                        │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  TranscriptionQueueManager                                        │
│                                                                    │
│  JobManager.create(job_id, ...)                                   │
│  Queue.put(JobPayload(job_id, wav_path, params))                  │
│                                                                    │
│  Worker loop:                                                     │
│    1. Check cancelled                                             │
│    2. update_status(PROCESSING)                                   │
│    3. with _transcription_lock:                                   │
│         engine = get_engine(mechanism)                            │
│         result = engine.transcribe(...)                           │
│    4. sanitize_result(result)                                     │
│    5. Сохранение:                                                 │
│       data/{job_id}/{name}.txt                                    │
│       data/{job_id}/{name}_segments.json                          │
│       data/{job_id}/{name}_raw.json                               │
│    6. update_status(COMPLETED)                                    │
│    7. if whisper: _clear_memory()                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Расположение файлов

```
data/                                    # DATA_UPLOADS_DIR
└── {job_id}/                            # build_job_path(job_id)
    ├── {original_filename}              # Оригинальный файл
    ├── {original_name}_converted.wav    # Конвертированный WAV
    ├── {original_name}.txt              # Текстовый результат
    ├── {original_name}_segments.json    # Сегменты
    └── {original_name}_raw.json         # Сырой ответ API (опционально)

uploads/                                 # UPLOADS_DIR
└── tmp_{filename}                       # Временный файл (удаляется)

models/                                  # MODELS_DIR
├── whisper-tiny/
├── whisper-base/
├── whisper-small/
├── whisper-medium/
├── whisper-turbo/
└── whisper-large/
```

---

## Ключевые конфигурационные переменные

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `MAX_FILE_SIZE_MB` | 500 | Макс. размер загружаемого файла |
| `CHUNK_SIZE_KB` | 8 | Размер чанка при чтении файла |
| `CONVERSION_TIMEOUT` | 600 | Таймаут конвертации FFmpeg (сек) |
| `TRANSCRIPTION_TIMEOUT` | 3600 | Таймаут транскрипции (сек) |
| `REMOVE_SILENCE` | true | Удалять тишину при конвертации |
| `SILENCE_THRESHOLD` | -45.0 | Порог тишины (dB) |
| `SILENCE_DURATION` | 1.0 | Мин. длительность тишины (сек) |
| `DEFAULT_MODEL` | turbo | Модель по умолчанию |
| `DEFAULT_LANGUAGE` | None | Язык по умолчанию (None = auto) |
| `TRANSCRIBER_WORKERS` | 3 | Количество рабочих потоков |
| `QUEUE_MAX_SIZE` | 20 | Макс. размер очереди |
| `OMLX_ENABLED` | true | Включить VibeVoice механизм |
| `OMLX_BASE_URL` | | URL oMLX API |
| `OMLX_MODEL` | VibeVoice-ASR-4bit | Модель oMLX |

# Техническая спецификация для MLX-Transcriber REST API

## Обзор

MLX-Transcriber — это высокопроизводительный сервис транскрибации аудио, использующий оптимизированную модель Whisper от Apple (MLX-Transcriber) и внешний oMLX API (VibeVoice-ASR) для обработки аудиофайлов на системах macOS с чипами Apple Silicon. Сервис предоставляет как веб-интерфейс, так и REST‑API для преобразования речи в текст с поддержкой нескольких языков, параллельной обработки и LLM-генерации отчётов.

## Архитектура

### Системные компоненты

1. **FastAPI Web Server**: ядро приложения, обрабатывающее HTTP‑запросы и ответы.
2. **TranscriptionEngine ABC**: абстрактный базовый класс (паттерн Strategy), определяющий единый интерфейс `transcribe(file_path, **params) -> dict` для всех механизмов транскрипции.
3. **WhisperEngine**: реализация через MLX Whisper с кэшированием моделей в памяти, поддержка 6 моделей.
4. **VibeVoiceEngine**: реализация через oMLX HTTP API с автоматическим разбиением аудио по тишине (librosa), определением спикеров и парсингом JSON-сегментов.
5. **TranscriptionQueueManager**: синглтон с `ThreadPoolExecutor` (3 воркера, очередь до 20 заданий) для параллельной обработки.
6. **JobManager**: синглтон для управления метаданными заданий (JSON в `data/{job_id}/{job_id}.json`).
7. **TranscriptionService**: сервисный слой, обёртка над TranscriptionQueueManager + JobManager.
8. **FFmpeg Audio Processing**: преобразование аудиофайлов в требуемый WAV‑формат (16 kHz, моно).
9. **ModelCache**: синглтон для кэширования загруженных MLX-моделей в памяти.
10. **Web Interface**: HTML/JavaScript-фронтенд для удобной загрузки файлов и отображения результатов.

### Технологический стек

- **Backend Framework**: FastAPI (Python 3.8+)
- **MLX Integration**: mlx‑whisper (оптимизированная реализация Whisper от Apple)
- **External API**: oMLX / VibeVoice-ASR (HTTP API)
- **Audio Processing**: FFmpeg, librosa, pydub для конвертации и разбиения аудио
- **Frontend**: HTML, CSS, JavaScript с минималистичными стилями (светлая/тёмная темы)
- **Deployment**: Uvicorn ASGI сервер

### Структура проекта

```
mlx-whisper/
├── src/                          # Исходный код
│   ├── main.py                   # FastAPI приложение (точка входа)
│   ├── config.py                 # Конфигурация через environment variables
│   ├── api/
│   │   ├── router.py             # Все API эндпоинты
│   │   └── dependencies.py       # Auth зависимости
│   ├── services/                 # Сервисный слой
│   │   ├── transcription_service.py   # TranscriptionService (обёртка)
│   │   ├── transcription_queue.py     # TranscriptionQueueManager (очередь)
│   │   ├── transcription_engines.py   # TranscriptionEngine ABC + WhisperEngine
│   │   ├── vibevoice_engine.py        # VibeVoiceEngine (oMLX API)
│   │   ├── job_manager.py             # JobManager (метаданные заданий)
│   │   └── report_types.py            # Загрузка типов отчётов
│   ├── models/                   # Бизнес-логика
│   │   ├── transcription.py      # Транскрипция (backward-compat)
│   │   ├── model_cache.py        # ModelCache (кэш моделей)
│   │   └── report.py             # LLM-генерация отчётов
│   ├── utils/                    # Утилиты
│   │   ├── audio.py              # FFmpeg конвертация, длительность
│   │   ├── files.py              # Работа с файлами, пути
│   │   └── download.py           # Скачивание из URL, валидация
│   ├── static/
│   │   └── new_style.css         # Минималистичные стили
│   └── templates/
│       ├── index.html            # Главная страница
│       └── uploads.html          # Страница загрузок
├── tests/                        # Тесты
├── models/                       # MLX Whisper модели
├── data/                         # Данные заданий
│   └── {job_id}/                 # Папка задания
│       ├── {filename}            # Оригинальный файл
│       ├── {base_name}_converted.wav
│       ├── {base_name}.txt       # Полный текст
│       ├── {base_name}_segments.json
│       ├── {base_name}_raw.json  # Сырой ответ API
│       └── {job_id}.json         # Метаданные задания
├── uploads/                      # Временные файлы
├── logs/                         # Логи
├── .env                          # Конфигурация
├── README.md
└── docs/                         # Документация
```

## Основные функции

### Архитектура механизмов транскрипции

Приложение использует паттерн Strategy через абстрактный базовый класс `TranscriptionEngine`:

- **`TranscriptionEngine` (ABC)** — определяет единый интерфейс `transcribe(file_path, **params) -> dict`
- **`WhisperEngine`** — реализация через MLX Whisper, поддержка 6 моделей (tiny/base/small/medium/turbo/large), кэширование моделей в памяти
- **`VibeVoiceEngine`** — реализация через oMLX HTTP API, автоматическое разбиение длинного аудио по тишине (librosa, порог 40 dB, лимит 50 мин), определение спикеров (ID из ответа oMLX), парсинг JSON сегментов (прямой массив, конкатенированные oMLX объекты, code blocks, regex fallback)

**Единый формат результата транскрипции:**

```json
{
  "segments": [
    {"start": 0.0, "end": 1.2, "speaker": 0, "text": "..."}
  ],
  "text": "полный текст расшифровки",
  "speaker_detected": true,
  "transcription_duration": 4.5,
  "raw_response": "..."
}
```

### Цепочка обработки аудио

1. **Валидация загрузки файла**
   - проверка расширений (10 форматов: wav, mp3, m4a, flac, aac, ogg, wma, webm, mp4, mkv)
   - ограничение размера (MAX_FILE_SIZE_MB, по умолчанию 500 МБ)
   - для URL: проверка домена (ALLOWED_URL_DOMAINS)

2. **Преобразование формата**
   - использование FFmpeg для конвертации в WAV (16 kHz, моно)
   - опциональное удаление тишины (SILENCE_THRESHOLD, SILENCE_DURATION)
   - сохранение качества звука и совместимость с моделью Whisper

3. **Создание метаданных задания**
   - генерация UUID job_id
   - создание директории `data/{job_id}/`
   - сохранение оригинального файла и метаданных через JobManager (статус QUEUED)

4. **Добавление в очередь транскрипции**
   - TranscriptionQueueManager принимает JobPayload (job_id, wav_path, params)
   - Воркеры из ThreadPoolExecutor обрабатывают задания параллельно

5. **Транскрипция (воркер)**
   - проверка статуса (пропуск если CANCELLED)
   - обновление статуса на PROCESSING
   - вызов `engine.transcribe()` с блокировкой для Whisper (одна модель в памяти)
   - сохранение результатов: TXT, segments JSON, raw JSON
   - обновление статуса на COMPLETED / CANCELLED / FAILED
   - очистка памяти MLX (mx.clear_cache() + gc.collect для whisper)

6. **Генерация отчётов через LLM**
   - загрузка segments из директории задания
   - формирование промпта на основе report_type или OPENAI_REPORT_PROMPT
   - чанкинг текста (MAX_REPORT_CHUNK_SIZE)
   - отправка на OpenAI API для генерации Markdown отчёта
   - сохранение report.md в директории задания

### Параметры механизма транскрипции

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `mechanism` | `whisper` | Механизм транскрипции (`whisper` / `vibevoice`) |
| `model` | `large` | Размер модели (tiny/base/small/medium/turbo/large) |
| `language` | `null` | Код языка (пустая строка или null для auto-detect) |
| `task` | `transcribe` | `transcribe` / `translate` |
| `word_timestamps` | `false` | Временные метки слов |
| `condition_on_previous_text` | `true` | Контекст предыдущего текста |
| `no_speech_threshold` | `0.4` | Порог определения тишины |
| `hallucination_silence_threshold` | `0.8` | Порог галлюцинаций |
| `initial_prompt` | `null` | Начальный промт для контекста |
| `remove_silence` | `true` | Удаление тишины перед транскрипцией |
| `silence_threshold` | `-45.0` | Порог тишины (dB) |
| `silence_duration` | `1.0` | Мин. длительность тишины (сек) |

### Параметры VibeVoice (механизм `vibevoice`)

- Автоматическое разбиение аудио по тишине (librosa, порог 40 dB)
- Группировка интервалов с паузой < 2 секунд
- Максимальная длительность сегмента: 50 минут
- Максимальный размер загрузки: 100 MB
- Определение спикеров: ID спикеров из ответа oMLX API
- Парсинг JSON сегментов из ответа oMLX API

### Функции веб‑интерфейса

- drag & drop загрузка аудиофайлов
- выбор механизма (Whisper / VibeVoice)
- выбор языка (авто / вручную)
- выбор типа задачи и размера модели
- сворачиваемая панель расширенных настроек
- переключение светлой/тёмной темы
- отображение прогресса и результатов с возможностью скачивания
- отображение размеров файлов в карточках заданий
- страница загрузки (`/uploads`) со списком всех заданий

## Параметры конфигурации (.env файл)

### Основные параметры

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `MLX_WHISPER_HOST` | `0.0.0.0` | Хост сервера |
| `MLX_WHISPER_PORT` | `8801` | Порт сервера |
| `MLX_WHISPER_DEBUG` | `false` | Режим отладки |
| `MLX_WHISPER_API_KEY` | — | API ключ для защиты |

### Обработка аудио

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `MAX_FILE_SIZE_MB` | `500` | Макс. размер файла (MB) |
| `CHUNK_SIZE_KB` | `8` | Размер чанка при чтении (KB) |
| `CONVERSION_TIMEOUT` | `600` | Таймаут конвертации (сек) |
| `TRANSCRIPTION_TIMEOUT` | `3600` | Таймаут транскрипции (сек) |
| `REMOVE_SILENCE` | `true` | Удаление тишины |
| `SILENCE_THRESHOLD` | `-45.0` | Порог тишины (dB) |
| `SILENCE_DURATION` | `1.0` | Мин. длительность тишины (сек) |

### Модели и транскрипция

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `MODELS_DIR` | `models` | Директория моделей |
| `DEFAULT_MODEL` | `turbo` | Модель по умолчанию |
| `DEFAULT_LANGUAGE` | — | Язык по умолчанию |
| `NO_SPEECH_THRESHOLD` | `0.4` | Порог тишины |
| `HALLUCINATION_SILENCE_THRESHOLD` | `0.8` | Порог галлюцинаций |
| `INITIAL_PROMPT` | — | Начальный промт для контекста |

### Очередь

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `TRANSCRIBER_WORKERS` | `3` | Количество воркеров |
| `QUEUE_MAX_SIZE` | `20` | Макс. размер очереди |

### oMLX / VibeVoice

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `OMLX_BASE_URL` | — | URL oMLX API |
| `OMLX_MODEL` | `VibeVoice-ASR-4bit` | Модель VibeVoice |
| `OMLX_API_KEY` | — | API ключ oMLX |
| `OMLX_ENABLED` | `true` | Включён ли VibeVoice |

### Отчёты (OpenAI)

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `OPENAI_API_KEY` | — | API ключ OpenAI |
| `OPENAI_BASE_URL` | — | Base URL (для совместимых API) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Модель для генерации |
| `OPENAI_REPORT_PROMPT` | — | Пользовательский промт |
| `MAX_REPORT_CHUNK_SIZE` | `10000` | Размер чанка текста |

### URL-загрузки

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `ALLOWED_URL_DOMAINS` | `youtube.com,youtu.be,vimeo.com` | Разрешённые домены |
| `MAX_DOWNLOAD_SIZE_MB` | `2048` | Макс. размер загрузки (MB) |
| `DOWNLOAD_TIMEOUT_SECONDS` | `600` | Таймаут загрузки (сек) |

## API‑конечные точки

Все эндпоинты доступны с префиксом `/api/v1/`.

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/api/v1/health` | Проверка состояния сервиса |
| GET | `/api/v1/models` | Список поддерживаемых моделей |
| GET | `/api/v1/config` | Конфигурация приложения |
| POST | `/api/v1/transcribe` | Транскрипция загруженного файла |
| POST | `/api/v1/transcribe-url` | Транскрипция по URL |
| GET | `/api/v1/jobs` | Список всех заданий |
| GET | `/api/v1/jobs/{job_id}` | Детали задания с результатом |
| DELETE | `/api/v1/jobs/{job_id}` | Отмена/удаление задания |
| DELETE | `/api/v1/jobs/{job_id}/files/{filename}` | Удаление файла из задания |
| GET | `/api/v1/jobs/{job_id}/files/{filename}/download` | Скачивание файла из задания |
| GET | `/api/v1/files/{filename}/download` | Общее скачивание файла |
| GET | `/api/v1/files/{filename}/content` | Просмотр содержимого файла |
| GET | `/api/v1/omlx/health` | Проверка oMLX API (VibeVoice) |
| GET | `/api/v1/report-types` | Список типов отчётов |
| POST | `/api/v1/report/{job_id}` | Генерация отчёта по расшифровке |
| GET | `/api/v1/cache/models` | Статистика кэша моделей |
| POST | `/api/v1/cache/clear` | Очистка кэша моделей |
| POST | `/api/v1/cache/preload` | Предзагрузка модели в кэш |

### POST /api/v1/transcribe

**Описание:** Транскрипция загруженного аудиофайла.

**Параметры:** file (multipart), language, task, model, word_timestamps, condition_on_previous_text, no_speech_threshold, hallucination_silence_threshold, initial_prompt, remove_silence, silence_threshold, silence_duration, mechanism.

**Ответ:** `{"job_id": "...", "status": "queued"}`

### POST /api/v1/transcribe-url

**Описание:** Транскрипция аудио по URL (YouTube, Vimeo, прямые ссылки).

**Параметры:** url, language, task, model, word_timestamps, condition_on_previous_text, no_speech_threshold, hallucination_silence_threshold, initial_prompt, remove_silence, silence_threshold, silence_duration, mechanism.

**Ответ:** `{"job_id": "...", "status": "queued"}`

### GET /api/v1/jobs/{job_id}

**Описание:** Статус задачи с результатом (если completed).

**Ответ:** Метаданные задания + text, segments, files (с размерами). Обрабатывает orphaned директории (без метаданных).

### GET /api/v1/jobs

**Описание:** Список всех заданий (metadata из JobManager).

**Ответ:** Массив объектов заданий с файлами `{name, size}`.

### DELETE /api/v1/jobs/{job_id}

**Описание:** Отмена (если_queued/processing) и полное удаление задания со всеми файлами.

**Ответ:** `{"status": "deleted", "job_id": "..."}`

### POST /api/v1/report/{job_id}

**Описание:** Запуск асинхронной генерации Markdown отчёта по расшифровке через LLM.

**Параметры тела (опционально):** `{"report_type": "summary"}`

**Ответ:** `{"status": "started", "job_id": "...", "message": "..."}`

Результат сохраняется как `report.md` в директории задания.

### GET /api/v1/cache/models

**Описание:** Статистика кэша моделей (загруженные модели, размеры, hit rate).

### POST /api/v1/cache/clear

**Описание:** Очистка всех моделей из кэша.

### POST /api/v1/cache/preload?model=large

**Описание:** Предзагрузка модели в кэш.

## Технические детали реализации

### Архитектура очередей и воркеров

- `TranscriptionQueueManager` — синглтон с `ThreadPoolExecutor` (настраиваемое количество воркеров, по умолчанию 3)
- Bounded `Queue` (максимум 20 заданий, по умолчанию)
- Блокировка `_transcription_lock` для Whisper (одна модель в памяти одновременно)
- VibeVoice не блокируется (каждый запрос — отдельный HTTP-вызов к oMLX API)
- Воркеры проверяют статус задания перед обработкой (пропуск CANCELLED)
- Graceful shutdown: остановка воркеров, ожидание завершения (30s timeout)

### Управление памятью

- `ModelCache` — синглтон для кэширования загруженных MLX-моделей в памяти
- Предзагрузка моделей через `/cache/preload`
- Очистка кэша MLX после транскрипции (whisper): `mx.clear_cache()`
- Сборка мусора Python: `gc.collect()`
- Обработка файлов порциями по `CHUNK_SIZE` (8 КБ)

### Управление заданиями

- `JobManager` — синглтон для управления метаданными в filesystem
- Метаданные: `data/{job_id}/{job_id}.json` (JSON с полями: job_id, status, source, original_filename, model, language, task, word_timestamps, mechanism, duration, transcription_duration, result_file, error, created_at, updated_at)
- Статусы: QUEUED → PROCESSING → COMPLETED / FAILED / CANCELLED
- Поддержка orphaned директорий (без метаданных, но с результатами)
- Удаление заданий: `JobManager.delete()` + `shutil.rmtree()`

### Сохранение результатов

Для каждого задания в `data/{job_id}/` создаются:

- `{base_name}.txt` — полный текст расшифровки
- `{base_name}_segments.json` — сегменты в формате `{"segments": [...]}`
- `{base_name}_raw.json` — сырой ответ API (JSON для Whisper, текст для VibeVoice)
- `{job_id}.json` — метаданные задания

### Обработка ошибок и логирование

- Валидация входных параметров (расширения, размер, URL)
- Отлов ошибок FFmpeg и транскрипции
- Подробные сообщения об ошибках в логах
- Структурированное логирование: `logs/app.log` (INFO) и `logs/error.log` (ERROR)
- Ротация: 10 МБ, 5 резервных копий
- Дублирование в stdout

### Сериализация данных

- Рекурсивная очистка NaN/Infinity: `sanitize_result()`
- Преобразование NumPy-типов в нативные Python
- Формирование структурированного JSON с метаданными и сегментами

## Характеристики производительности

### Требования к ресурсам

- macOS с Apple Silicon (M1/M2/M3).
- 8 ГБ ОЗУ минимум.
- Диск для файлов (`data/`, `uploads/`).
- Оптимизация под нейронный процессор Apple.

### Сравнение производительности моделей

| Модель | Размер | Скорость | Точность |
|--------|--------|----------|----------|
| tiny   | ~39 МБ | Очень быстрая | Низкая |
| base   | ~74 МБ | Быстрая | Удовлетворительная |
| small  | ~249 МБ | Средняя | Хорошая |
| medium | ~769 МБ | Медленная | Высокая |
| turbo  | ~1.4 ГБ | Очень быстрая | Очень высокая |
| large  | ~3.1 ГБ | Медленная | Отличная |

### Жизненный цикл задания

```
Загрузка файла / URL
    ↓
Валидация (расширение, размер, URL)
    ↓
Конвертация в WAV (FFmpeg, 16kHz моно, удаление тишины)
    ↓
Создание метаданных (JobManager → QUEUED)
    ↓
Добавление в очередь (TranscriptionQueueManager)
    ↓
Воркер: проверка cancelled → PROCESSING
    ↓
Транскрипция (engine.transcribe() с блокировкой для whisper)
    ↓
Сохранение результатов (TXT, segments JSON, raw JSON)
    ↓
Обновление статуса (COMPLETED / CANCELLED / FAILED)
    ↓
Очистка памяти (MLX cache + gc.collect для whisper)
```

### Цепочка генерации отчёта через LLM

```
POST /api/v1/report/{job_id}
    ↓
Проверка директории задания: data/{job_id}/
    ↓
Загрузка сегментов: load_segments_file()
    ↓
Определение промпта: report_type → prompt / OPENAI_REPORT_PROMPT
    ↓
Чанкинг текста: MAX_REPORT_CHUNK_SIZE
    ↓
Вызов OpenAI API: gpt-4o-mini (или кастомная модель)
    ↓
Сохранение: save_report() → report.md
    ↓
Ответ: {"status": "started", ...}
```

## Соображения безопасности

- Проверка расширений и размера файла.
- Валидация URL (allowed domains).
- Защита от path traversal при скачивании файлов.
- API ключ через MLX_WHISPER_API_KEY (опциональная аутентификация).
- Ограничение частоты запросов через пул потоков и bounded queue.
- Безопасная обработка путей: `os.path.realpath()` + проверка префикса.

## Развертывание

### Системные предварительные условия

- macOS с Apple Silicon.
- Python 3.8+.
- Установлённый FFmpeg.
- 8 ГБ ОЗУ рекомендовано.

### Шаги установки

1. `git clone ... && cd mlx-whisper`
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r src/requirements.txt`
4. Загрузить модели в `models/whisper-*` или использовать Hugging Face.
5. Настроить `.env` переменные.
6. `python src/main.py`

### Производственные соображения

- Gunicorn вместо Uvicorn.
- Аутентификация для публичного доступа.
- Настройка логирования и балансировка нагрузки.
- Вынос очереди в Redis/RabbitMQ для распределённой обработки.

## Тестирование и проверка

### Стратегия тестирования

- Модульные тесты для функций и параметров.
- Интеграционные тесты полного цикла.
- Тесты на нагрузку и память.
- Playwright тесты для веб-интерфейса.

## Устранение неполадок

1. FFmpeg не найден — установить через Homebrew.
2. Модели отсутствуют — загрузить с Hugging Face.
3. Проблемы с памятью — использовать более мелкие модели.
4. Неподдерживаемый формат — убедиться в поддерживаемом расширении.
5. OMLX API недоступен — проверить OMLX_BASE_URL и OMLX_API_KEY.

## Будущие улучшения

1. **Масштабируемость**: Вынос очереди в Redis/RabbitMQ для распределённой обработки
2. **Безопасность**: Расширенная аутентификация, rate limiting
3. **Производительность**: Динамическое управление количеством воркеров
4. **UX**: WebSocket для real-time обновления статуса, drag-and-drop загрузка
5. **Экспорт**: PDF, SRT, VTT форматы
6. **Контейнеризация**: Docker поддержка (для non-Apple серверов с CUDA)

## Соответствие стандартам

### Стандарты разработки

- Стили кодирования PEP 8 для Python
- Аннотации типов для всех параметров функций и возвращаемых значений
- Правильная обработка исключений с HTTP-кодами статуса
- Асинхронные/ожидающие паттерны для операций ввода-вывода

### Стандарты данных

- Формат JSON для всех ответов API
- Кодировка UTF-8 для текстовых файлов
- Стандартные форматы временных меток в сегментах
- Последовательные соглашения по именованию для идентификаторов задач

## Ссылки

1. [MLX-Transcriber GitHub](https://github.com/ml-explore/mlx-whisper)
2. [OpenAI Whisper GitHub](https://github.com/openai/whisper)
3. [OpenAI API Speech-to-Text](https://developers.openai.com/api/docs/guides/speech-to-text)
4. [OpenAI Whisper Paper](https://arxiv.org/abs/2212.04356)
5. [Фреймворк Apple MLX](https://github.com/ml-explore/mlx)
6. [Документация FastAPI](https://fastapi.tiangolo.com/)
7. [Документация FFmpeg](https://ffmpeg.org/documentation.html)
8. [Microsoft VibeVoice GitHub](https://github.com/microsoft/VibeVoice)
9. [VibeVoice-ASR на Hugging Face](https://huggingface.co/microsoft/VibeVoice-ASR)
10. [VibeVoice-ASR Technical Report (arXiv)](https://arxiv.org/abs/2601.18184)
11. [VibeVoice ASR Transformers Docs](https://huggingface.co/docs/transformers/main/en/model_doc/vibevoice_asr)

## О MLX (Apple Machine Learning Framework)

MLX — это фреймворк машинного обучения от Apple, разработанный для эффективной работы на чипах Apple Silicon (M1, M2, M3 и т.д.). Основные особенности:

- **Нативная поддержка Metal Performance Shaders (MPS)** — максимальная производительность на Apple GPU
- **Динамический граф вычислений** — позволяет строить и изменять модели во время выполнения
- **Автоматическое дифференцирование** — встроенный autograd для обучения нейронных сетей
- **Лёгкий и минималистичный API** — похожий на NumPy, но с поддержкой ускорителей Apple
- **Бесплатный и открытый** — распространяется под лицензией MIT

MLX позволяет разработчикам использовать весь потенциал Apple Silicon для задач машинного обучения, включая транскрипцию аудио, обработку изображений и работу с языковыми моделями.

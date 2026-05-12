# План реализации: MLX-Whisper REST API

## Контекст

MLX-Whisper — это сервис транскрипции аудио, построенный на основе оптимизированной реализации Whisper от Apple (MLX). Приложение предоставляет REST API и веб-интерфейс для преобразования речи в текст с поддержкой нескольких механизмов транскрипции, параллельной обработки, определения спикеров и LLM-генерации отчётов.

## Обзор приложения

Приложение позволяет:
- Загружать аудиофайлы различных форматов (WAV, MP3, M4A, FLAC, AAC, OGG, WMA, WEBM, MP4, MKV)
- Транскрибировать аудио по загрузке файла или по URL (YouTube, Vimeo, прямые ссылки)
- Выбирать между двумя механизмами: MLX Whisper и VibeVoice (oMLX API)
- Обрабатывать несколько заданий параллельно через очередь с ThreadPoolExecutor
- Получать результат с сегментами, временными метками, определением спикеров
- Генерировать LLM-отчёты по расшифровкам
- Управлять кэшем моделей для ускорения повторной обработки

## Структура проекта

```
mlx-whisper/
├── src/                          # Исходный код
│   ├── main.py                   # FastAPI приложение (точка входа)
│   ├── config.py                 # Конфигурация через environment variables
│   ├── api/
│   │   ├── router.py             # Все API эндпоинты
│   │   └── dependencies.py       # Auth зависимости
│   ├── services/                 # Сервисный слой
│   │   ├── transcription_service.py   # Обёртка над очередью + job manager
│   │   ├── transcription_queue.py     # ThreadPoolExecutor очередь
│   │   ├── transcription_engines.py   # TranscriptionEngine ABC + WhisperEngine
│   │   ├── vibevoice_engine.py        # VibeVoiceEngine (oMLX API)
│   │   ├── job_manager.py             # Job metadata менеджер
│   │   └── report_types.py            # Типы отчётов
│   ├── models/                   # Бизнес-логика
│   │   ├── transcription.py      # Транскрипция (backward-compat)
│   │   ├── model_cache.py        # Кэш моделей MLX
│   │   └── report.py             # Генерация отчётов LLM
│   ├── utils/                    # Утилиты
│   │   ├── audio.py              # FFmpeg конвертация
│   │   ├── files.py              # Работа с файлами
│   │   └── download.py           # Скачивание из URL
│   ├── static/
│   │   └── new_style.css         # Стили интерфейса
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

## Архитектура обработки

### Механизмы транскрипции

Приложение использует паттерн Strategy через абстрактный базовый класс `TranscriptionEngine`:

- **`TranscriptionEngine` (ABC)** — определяет единый интерфейс `transcribe(file_path, **params) -> dict`
- **`WhisperEngine`** — реализация через MLX Whisper, поддержка 6 моделей (tiny/base/small/medium/turbo/large), кэширование моделей в памяти
- **`VibeVoiceEngine`** — реализация через oMLX HTTP API, автоматическое разбиение длинного аудио по тишине (librosa), определение спикеров (0→"Клиент", 1→"Терапевт"), парсинг JSON сегментов (прямой массив, конкатенированные oMLX объекты, code blocks, regex fallback)

**Единый формат результата:**
```json
{
  "segments": [{"start": 0.0, "end": 1.2, "speaker": 0, "text": "..."}],
  "text": "полный текст расшифровки",
  "speaker_detected": true,
  "transcription_duration": 4.5,
  "raw_response": "..."
}
```

### Сервисный слой

- **`TranscriptionService`** — обёртка над `TranscriptionQueueManager` + `JobManager`, предоставляет `submit()`, `get_job()`, `list_jobs()`, `cancel_job()`
- **`TranscriptionQueueManager`** — синглтон с `ThreadPoolExecutor` (3 воркера, очередь до 20 заданий), управляет жизненным циклом заданий
- **`JobManager`** — синглтон для управления метаданными заданий в filesystem (JSON-файл на задание: `data/{job_id}/{job_id}.json`)
- **`ModelCache`** — синглтон для кэширования загруженных моделей MLX в памяти

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

## Технические особенности

### Управление памятью
- Кэширование моделей MLX через `ModelCache` — модель загружается один раз и переиспользуется
- Очистка кэша MLX после транскрипции (whisper): `mx.clear_cache()`
- Сборка мусора Python: `gc.collect()`
- Обработка файлов частями по `CHUNK_SIZE` (8 КБ по умолчанию)

### Параллельная обработка
- `ThreadPoolExecutor` с настраиваемым количеством воркеров (по умолчанию 3)
- Бounded очередь (максимум 20 заданий, по умолчанию)
- Блокировка `_transcription_lock` для Whisper (одна модель в памяти)
- VibeVoice не блокируется (каждый запрос — отдельный HTTP-вызов)

### Обработка ошибок
- Валидация расширений файлов
- Ограничение размера файла (MAX_FILE_SIZE_MB)
- Валидация URL (allowed domains)
- Обработка FFmpeg таймаутов
- JSON-сериализация с очисткой NaN/Infinity
- Отмена заданий (QUEUED → CANCELLED, PROCESSING → CANCELLED)

### Логирование
- Два файла: `logs/app.log` (INFO) и `logs/error.log` (ERROR)
- Ротация: 10MB, 5 резервных копий
- Дублирование в stdout и файлы

### Сохранение результатов
Для каждого задания в папке `data/{job_id}/` создаются:
- `{base_name}.txt` — полный текст расшифровки
- `{base_name}_segments.json` — сегменты в формате `{"segments": [...]}`
- `{base_name}_raw.json` — сырой ответ API (JSON для Whisper, текст для VibeVoice)
- `{job_id}.json` — метаданные задания (статус, параметры, время)

## API Endpoints

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

### Параметры транскрипции (POST /transcribe, /transcribe-url)

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
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
| `mechanism` | `whisper` | Механизм транскрипции (`whisper` / `vibevoice`) |

### Параметры VibeVoice (механизм `vibevoice`)

- Автоматическое разбиение аудио по тишине (librosa, порог 40 dB)
- Группировка интервалов с паузой < 2 секунд
- Максимальная длительность сегмента: 50 минут
- Максимальный размер загрузки: 100 MB
- Определение спикеров: 0 → "Клиент", 1 → "Терапевт"
- Парсинг JSON сегментов из ответа oMLX API

## Параметры отчёта (POST /report/{job_id})

| Параметр | Описание |
|----------|----------|
| `report_type` | Тип отчёта (опционально, берётся из конфига `report_types.json`) |

Отчёт генерируется асинхронно в фоновом потоке. Результат сохраняется как `report.md` в директории задания.

## Параметры кэша моделей

| Эндпоинт | Описание |
|----------|----------|
| `GET /cache/models` | Статистика: загруженные модели, размеры, hit rate |
| `POST /cache/clear` | Очистка всех моделей из кэша |
| `POST /cache/preload?model=large` | Предзагрузка модели в кэш |

## Конфигурация

### Переменные окружения (.env)

**Основные:**
| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `MLX_WHISPER_HOST` | `0.0.0.0` | Хост сервера |
| `MLX_WHISPER_PORT` | `8801` | Порт сервера |
| `MLX_WHISPER_DEBUG` | `false` | Режим отладки |
| `MLX_WHISPER_API_KEY` | — | API ключ для защиты |

**Обработка аудио:**
| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `MAX_FILE_SIZE_MB` | `500` | Макс. размер файла (MB) |
| `CHUNK_SIZE_KB` | `8` | Размер чанка при чтении (KB) |
| `CONVERSION_TIMEOUT` | `600` | Таймаут конвертации (сек) |
| `TRANSCRIPTION_TIMEOUT` | `3600` | Таймаут транскрипции (сек) |
| `REMOVE_SILENCE` | `true` | Удаление тишины |
| `SILENCE_THRESHOLD` | `-45.0` | Порог тишины (dB) |
| `SILENCE_DURATION` | `1.0` | Мин. длительность тишины (сек) |

**Модели и транскрипция:**
| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `MODELS_DIR` | `models` | Директория моделей |
| `DEFAULT_MODEL` | `turbo` | Модель по умолчанию |
| `DEFAULT_LANGUAGE` | — | Язык по умолчанию |
| `NO_SPEECH_THRESHOLD` | `0.4` | Порог тишины |
| `HALLUCINATION_SILENCE_THRESHOLD` | `0.8` | Порог галлюцинаций |

**Очередь:**
| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TRANSCRIBER_WORKERS` | `3` | Количество воркеров |
| `QUEUE_MAX_SIZE` | `20` | Макс. размер очереди |

**oMLX / VibeVoice:**
| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `OMLX_BASE_URL` | — | URL oMLX API |
| `OMLX_MODEL` | `VibeVoice-ASR-4bit` | Модель VibeVoice |
| `OMLX_API_KEY` | — | API ключ oMLX |
| `OMLX_ENABLED` | `true` | Включён ли VibeVoice |

**Отчёты (OpenAI):**
| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `OPENAI_API_KEY` | — | API ключ OpenAI |
| `OPENAI_BASE_URL` | — | Base URL (для совместимых API) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Модель для генерации |
| `MAX_REPORT_CHUNK_SIZE` | `10000` | Размер чанка текста |

**URL-загрузки:**
| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `ALLOWED_URL_DOMAINS` | `youtube.com,youtu.be,vimeo.com` | Разрешённые домены |
| `MAX_DOWNLOAD_SIZE_MB` | `2048` | Макс. размер загрузки (MB) |
| `DOWNLOAD_TIMEOUT` | `600` | Таймаут загрузки (сек) |

## Зависимости

### Python
- fastapi — веб-фреймворк
- uvicorn — ASGI сервер
- mlx — Apple Machine Learning Framework
- mlx-whisper — оптимизированная реализация Whisper
- python-dotenv — управление переменными окружения
- pydub + librosa — обработка аудио (VibeVoice)
- ffmpeg-python — обёртка для FFmpeg
- requests — HTTP-клиент (VibeVoice API)
- openai — LLM API (отчёты)
- langchain-text-splitters — чанкинг текста (отчёты)

### Frontend
- HTML5 / CSS3 / Vanilla JavaScript
- Font Awesome — иконки

## Развертывание

### Требования
- macOS с Apple Silicon (M1/M2/M3)
- Python 3.8+
- FFmpeg

### Установка
```bash
git clone https://github.com/.../mlx_whisper
cd mlx_whisper
python -m venv .venv
source .venv/bin/activate
pip install -r src/requirements.txt
python src/main.py
```

## Будущие улучшения

1. **Масштабируемость**: Вынос очереди в Redis/RabbitMQ для распределённой обработки
2. **Безопасность**: Расширенная аутентификация, rate limiting
3. **Производительность**: Динамическое управление количеством воркеров
4. **UX**: WebSocket для real-time обновления статуса, drag-and-drop загрузка
5. **Экспорт**: PDF, SRT, VTT форматы
6. **Контейнеризация**: Docker поддержка (для non-Apple серверов с CUDA)

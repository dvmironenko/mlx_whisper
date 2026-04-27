# План реализации: MLX-Whisper REST API

## Контекст

MLX-Whisper — это сервис транскрипции аудио, построенный на основе оптимизированной реализации Whisper от Apple. Приложение предоставляет REST API и веб-интерфейс для преобразования речи в текст с поддержкой нескольких языков и гибких параметров обработки.

## Обзор приложения

Приложение позволяет:
- Загружать аудиофайлы различных форматов (WAV, MP3, M4A, FLAC, AAC, OGG, WMA, WEBM, MP4, MKV)
- Автоматически конвертировать в WAV (16kHz, моно) с помощью FFmpeg
- Транскрибировать аудио с использованием моделей MLX-Whisper (tiny, base, small, medium, large, turbo)
- Получать результат с временными метками слов при необходимости
- Управлять сохраненными заданиями через веб-интерфейс

## Основные компоненты

### 1. FastAPI Backend (`src/`)
- `main.py` — точка входа, инициализация сервера
- `config.py` — конфигурация через environment variables
- `api/router.py` — API роуты и обработчики
- `models/transcription.py` — бизнес-логика транскрипции
- `utils/audio.py` — FFmpeg конвертация
- `utils/files.py` — работа с файлами и directories

### 2. Веб-интерфейс
- `src/templates/index.html` — список заданий с карточками
- `src/templates/uploads.html` — форма загрузки аудио
- `src/static/new_style.css` — минималистичные стили с поддержкой тёмной темы

### 3. Модели MLX-Whisper
- Расположение: `models/whisper-*`
- Поддерживаемые: tiny, base, small, medium, large, turbo
- Оптимизация под Apple Silicon (MPS)

## Архитектура обработки

```
Загрузка файла
    ↓
Валидация (расширение, размер)
    ↓
Конвертация в WAV (FFmpeg, удаление тишины)
    ↓
Транскрипция (MLX-Whisper)
    ↓
Сохранение результатов (TXT, сегменты JSON)
    ↓
Возврат JSON ответа
```

## Технические особенности

### Управление памятью
- Обработка файлов частями по `CHUNK_SIZE` (8 КБ по умолчанию)
- Очистка кэша MLX после транскрипции: `mx.clear_cache()`
- Сборка мусора Python: `gc.collect()`

### Обработка ошибок
- Валидация расширений файлов
- Ограничение размера файла (MAX_FILE_SIZE_MB)
- Обработка FFmpeg таймаутов
- JSON-сериализация с очисткой NaN/Infinity

### Логирование
- Два файла: `logs/app.log` (INFO) и `logs/error.log` (ERROR)
- Ротация: 10MB, 5 резервных копий
- Дублирование в stdout и файлы

## API Endpoints

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/health` | Проверка состояния |
| GET | `/models` | Список моделей |
| GET | `/api/v1/config` | Получить конфигурацию |
| GET | `/api/v1/jobs` | Список заданий |
| GET | `/api/v1/jobs/{job_id}` | Статус задания |
| POST | `/api/v1/transcribe` | Транскрибация аудио |
| DELETE | `/api/v1/jobs/{job_id}` | Удалить задание |
| GET | `/api/v1/files/{filename}/download` | Скачать файл |
| GET | `/api/v1/files/{filename}/content` | Просмотр содержимого |
| DELETE | `/api/v1/jobs/{job_id}/files/{filename}` | Удалить файл |

## Параметры транскрипции

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `model` | `turbo` | Размер модели |
| `language` | `auto` | Код языка |
| `task` | `transcribe` | transcribe / translate |
| `word_timestamps` | `true` | Временные метки слов |
| `condition_on_previous_text` | `true` | Контекст предыдущего текста |
| `remove_silence` | `true` | Удаление тишины |
| `silence_threshold` | `-60.0` | Порог тишины (dB) |
| `silence_duration` | `0.5` | Мин. длительность тишины |

## Структура проекта

```
mlx-whisper/
├── src/                      # Исходный код
│   ├── main.py              # FastAPI приложение
│   ├── config.py            # Конфигурация
│   ├── api/                 # API роуты
│   │   ├── router.py
│   │   └── dependencies.py
│   ├── models/              # Бизнес-логика
│   │   └── transcription.py
│   └── utils/               # Утилиты
│       ├── audio.py
│       └── files.py
├── docs/                    # Документация
├── tests/                   # Тесты
├── models/                  # Модели MLX-Whisper
├── uploads/                 # Временное хранилище
├── data/                    # Сохраненные результаты
│   └── uploads/{job_id}/    # Файлы заданий
├── logs/                    # Логи
├── .env                     # Конфигурация
└── README.md
```

## Зависимости

### Python
- fastapi — веб-фреймворк
- mlx — Apple Machine Learning Framework
- mlx-whisper — оптимизированная реализация Whisper
- uvicorn — ASGI сервер
- python-dotenv — управление переменными окружения
- ffmpeg-python — обертка для FFmpeg

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

### Переменные окружения (.env)
```
MODEL=turbo
LANGUAGE=
TASK=transcribe
WORD_TIMESTAMPS=true
CONDITION_ON_PREVIOUS=true
REMOVE_SILENCE=true
SILENCE_THRESHOLD=-60.0
SILENCE_DURATION=0.5
NO_SPEECH_THRESHOLD=0.6
HALLUCINATION_SILENCE_THRESHOLD=2.0
MAX_FILE_SIZE_MB=100
```

## Будущие улучшения

1. **Безопасность**: Аутентификация через API ключ
2. **Производительность**: Кэширование моделей, пакетная обработка
3. **UX**: Индикаторы прогресса, горячие клавиши
4. **Экспорт**: PDF, SRT форматы
5. **Контейнеризация**: Docker поддержка

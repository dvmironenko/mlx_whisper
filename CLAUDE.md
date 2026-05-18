# CLAUDE.md

## Общий вводный текст

Файл предоставляет руководство для Claude Code при работе с репозиторием `mlx_whisper`. Все ответы, объяснения, комментарии и описания коммитов пишутся на русском, а код — в английском. 

## Рабочий процесс разработки

- Следовать PEP 8, использовать аннотации типов и async/await.
- Документация в папке `docs/`. Всю документацию размещай в этой папке.
- Тесты в папке `tests/`. Все тесты размещай в этой папке.
- Веб-интерфейс использует минималистичные стили (`src/templates/new_index.html`, `src/static/new_style.css`).


## Структура проекта

```
mlx-whisper/
├── src/                      # Исходный код
│   ├── main.py              # FastAPI приложение (точка входа)
│   ├── config.py            # Конфигурация через environment variables
│   ├── api/                 # API роуты и зависимости
│   │   ├── router.py        # FastAPI роуты
│   │   └── dependencies.py  # Зависимости (auth, auth check)
│   ├── models/              # Бизнес-логика
│   │   └── transcription.py # Логика транскрипции
│   └── utils/               # Утилиты
│       ├── audio.py         # FFmpeg конвертация
│       └── files.py         # Работа с файлами
├── docs/                    # Документация
│   ├── dev-commands.md      # Команды разработки
│   ├── technical_specification.md  # Техническая спецификация
│   └── TODO.md              # План задач
├── tests/                   # Тесты
├── models/                  # Модели MLX-Whisper
├── uploads/                 # Временное хранилище
└── logs/                    # Логи
```

## Ключевые особенности реализации

### Модульность
Приложение построено по принципу модульности:
- `src/api/router.py` — FastAPI роуты
- `src/models/transcription.py` — бизнес-логика транскрипции
- `src/utils/` — вспомогательные функции

### Оптимизация памяти
- Обработка файлов порциями по `CHUNK_SIZE` (по умолчанию 8 КБ)
- Очистка кэша MLX после транскрипции: `mx.clear_cache()`
- Сборка мусора Python: `gc.collect()`

### Логирование
- Два файла логов: `app.log` (INFO) и `error.log` (ERROR)
- Ротация: 10MB, 5 резервных копий
- Дублирование вывода в stdout и файлы

### Обработка ошибок
- Валидация расширений файлов
- Ограничение размера файла (MAX_FILE_SIZE_MB)
- Обработка FFmpeg таймаутов
- JSON-сериализация с очисткой NaN/Infinity

## Ссылки на документацию

- **Команды разработки**: [`docs/dev-commands.md`](docs/dev-commands.md)
- **Техническая спецификация**: [`docs/technical_specification.md`](docs/technical_specification.md)
- **README**: [`README.md`](README.md) — полная документация пользователя
- **Implementation Plan**: [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — план реализации функциональности

Все файлы тестов размещать в папке tests/

## Running the Application

**Важно:** Приложение всегда должно запускаться в виртуальном окружении `.venv`:

```bash
source .venv/bin/activate 
python src/main.py
```

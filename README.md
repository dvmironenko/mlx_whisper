# MLX-Whisper REST API

[Документация](docs/technical_specification.md)

## Обзор проекта

Это высокопроизводительный веб-сервис для транскрибации и перевода аудио с использованием оптимизированной модели Whisper от Apple (MLX-Whisper). Сервис предоставляет как веб-интерфейс, так и REST API для преобразования речи в текст с поддержкой нескольких языков и гибких параметров обработки.

### Основные особенности:
- Оптимизировано для чипов Apple Silicon (M1/M2)
- Веб-интерфейс для удобной загрузки и обработки аудиофайлов
- REST API для программного доступа через HTTP-запросы
- Поддержка различных аудиоформатов (WAV, MP3, M4A, FLAC, AAC, OGG, WMA, WEBM, MP4)
- Поддержка нескольких размеров моделей (tiny, base, small, medium, turbo, large) для баланса между производительностью и точностью
- Временные метки слов и контекстно-осознанная обработка
- Раздельный возврат основного текста и информации о сегментах при включенных временных метках

## Начало работы

### Предварительные требования
- macOS с чипом Apple Silicon (M1/M2) - **обязательно**
- Python 3.8+
- pip и venv
- ffmpeg (для конвертации аудиоформатов)

### Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/your-username/mlx-whisper.git
cd mlx-whisper
```

2. Создайте и активируйте виртуальное окружение:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r src/requirements.txt
```

4. Загрузите модели MLX-Whisper:
```bash
mkdir -p models/whisper-turbo
# Загрузите config.json и weights.npz с Hugging Face в models/whisper-turbo/
# Пример: https://huggingface.co/mlx-community/whisper-turbo
```

### Базовое использование

Запустите сервер:
```bash
python src/main.py
```

Сервер запустится на `http://localhost:8801`. Откройте этот URL в браузере для использования веб-интерфейса.

### Запуск тестов

Используйте аудиофайлы из директории `tests/` для ручного тестирования:
```bash
# В одном терминале запустите сервер:
python src/main.py

# В другом терминале отправьте тестовый запрос:
curl -X POST "http://localhost:8801/transcribe" \
  -F "file=@tests/test.wav" \
  -F "language=ru"
```

## Структура проекта

```
mlx_whisper/
├── docs/                   # Documentation directory
│   └── technical_specification.md  # Technical specification document
├── models/                 # MLX-Whisper model files (config.json, weights.npz)
│   ├── whisper-tiny/
│   ├── whisper-base/
│   ├── whisper-small/
│   ├── whisper-medium/
│   ├── whisper-turbo/
│   └── whisper-large/
├── src/
│   ├── main.py             # FastAPI application and transcription logic
│   ├── requirements.txt    # Python dependencies
│   ├── static/
│   │   └── style.css       # Web interface styling
│   └── templates/
│       └── index.html      # HTML template for web interface
├── tests/                  # Test audio files
│   ├── test.wav
│   └── 2_5258335770527167268.ogg
├── uploads/                # Temporary file storage directory (created automatically)
├── .gitignore              # Git ignore rules
└── README.md               # Project documentation
```

## Рабочий процесс разработки

### Стандарты кодирования
- Следуйте руководству по стилю PEP 8 для Python
- Используйте аннотации типов для параметров функций и возвращаемых значений
- Реализуйте правильную обработку ошибок с помощью HTTP исключений
- Используйте async/await для операций ввода-вывода для поддержания производительности

### Подход к тестированию
- Ручное тестирование с аудиофайлами в директории `tests/`
- Модульные тесты для отдельных функций (пока не реализованы)
- Интеграционное тестирование через API конечные точки

### Сборка и развертывание
Приложение предназначено для запуска на Mac с Apple Silicon с:
- Виртуальным окружением Python
- Установленными моделями MLX-Whisper
- FFmpeg для конвертации аудиоформатов

Для производственного развертывания рассмотрите использование Gunicorn вместо Uvicorn.

## Ключевые концепции

### Фреймворк MLX-Whisper
Этот проект использует фреймворк MLX от Apple для запуска оптимизированных моделей Whisper для чипов Apple Silicon. Это обеспечивает лучшую производительность по сравнению с традиционными реализациями на CUDA.

### Пайплайн обработки аудио
1. Загрузка файла с проверкой (формат и размер)
2. Конвертация формата в WAV с помощью FFmpeg (16kHz, моно)
3. Транскрибация с использованием модели MLX-Whisper
4. Форматирование результатов и сериализация в JSON
5. Генерация текстового файла для скачивания

### Система управления задачами
Приложение реализует систему отслеживания задач:
- Каждый запрос на транскрибацию создает уникальный ID задачи
- Статус задачи отслеживается в памяти (`job_status` словарь)
- Результаты хранятся с метаданными, включая продолжительность и параметры

### Оптимизация памяти
- Чтение/запись файлов частями для обработки больших файлов эффективно
- Использование пула потоков для CPU-интенсивных задач транскрибации
- Автоматическая очистка временных файлов после обработки

## Распространенные задачи

### Транскрибация аудиофайлов через веб-интерфейс
1. Откройте `http://localhost:8801` в браузере
2. Выберите аудиофайл с помощью поля выбора файла
3. Настройте параметры обработки:
   - Язык (автоопределение или конкретный)
   - Задача (транскрибировать или перевести)
   - Размер модели (tiny, base, small, medium, turbo, large)
   - Временные метки слов (включить/выключить)
   - Контекстно-осознанная обработка (включить/выключить)
4. Нажмите "Транскрибировать"
5. Просмотрите результаты и скачайте как текстовый файл

### Использование REST API
```bash
curl -X POST "http://localhost:8801/transcribe" \
  -F "file=@/path/to/audio.wav" \
  -F "language=ru" \
  -F "task=transcribe" \
  -F "model=turbo" \
  -F "word_timestamps=true" \
  -F "condition_on_previous_text=true"
```

При включенных временных метках (word_timestamps=true) API создает два отдельных текстовых файла:
1. Основной файл с транскрибированным текстом
2. Файл с информацией о сегментах в формате "[start - end] text"

Эти файлы доступны для скачивания через веб-интерфейс или API.

### Добавление новых моделей
1. Создайте новую директорию в `models/` (например, `models/whisper-custom`)
2. Загрузите файлы модели (`config.json` и `weights.npz`) в эту директорию
3. Добавьте модель в словарь `SUPPORTED_MODELS` в `src/main.py`:
```python
"SUPPORTED_MODELS": {
    "tiny": "models/whisper-tiny",
    "base": "models/whisper-base",
    "small": "models/whisper-small",
    "medium": "models/whisper-medium",
    "turbo": "models/whisper-turbo",
    "large": "models/whisper-large",
    "custom": "models/whisper-custom",  # Добавьте эту строку
}
```

## Устранение неполадок

### Распространенные проблемы и решения

1. **FFmpeg не найден**
   - Ошибка: "FFmpeg not found. Please install ffmpeg..."
   - Решение: Установите FFmpeg с помощью Homebrew:
     ```bash
     brew install ffmpeg
     ```

2. **Файлы моделей отсутствуют**
   - Ошибка: "Model not found" или "File not found"
   - Решение: Загрузите файлы моделей с Hugging Face в соответствующую директорию модели

3. **Проблемы с памятью при больших файлах**
   - Ошибка: "Out of memory" или медленная обработка
   - Решение: Используйте более мелкие размеры моделей или обрабатывайте файлы частями

4. **Формат файла не поддерживается**
   - Ошибка: "Unsupported audio format"
   - Решение: Убедитесь, что файл имеет один из поддерживаемых расширений (.wav, .mp3 и т.д.)

5. **Ошибки доступа**
   - Ошибка: "Permission denied" при записи в директорию uploads
   - Решение: Проверьте права доступа к директории uploads

### Советы по отладке
- Включите логирование, изменив `logging.basicConfig(level=logging.INFO)` в `src/main.py`
- Проверяйте вывод терминала для получения подробных сообщений об ошибках
- Используйте инструменты разработчика браузера для проверки ответов API
- Мониторьте ресурсы системы (CPU, память) во время обработки

## Ссылки

### Документация и ресурсы
- [MLX-Whisper GitHub](https://github.com/ml-explore/mlx-whisper)
- [Статья OpenAI Whisper](https://arxiv.org/abs/2212.04356)
- [Фреймворк Apple MLX](https://github.com/ml-explore/mlx)
- [Документация FastAPI](https://fastapi.tiangolo.com/)
- [Документация FFmpeg](https://ffmpeg.org/documentation.html)

### Поддерживаемые модели
| Модель | Путь | Размер | Скорость | Точность |
|--------|------|--------|----------|----------|
| `tiny` | models/whisper-tiny | ~39 МБ | Очень высокая | Низкая |
| `base` | models/whisper-base | ~74 МБ | Высокая | Удовлетворительная |
| `small` | models/whisper-small | ~249 МБ | Хорошая | Средняя |
| `medium` | models/whisper-medium | ~769 МБ | Умеренная | Высокая |
| `turbo` | models/whisper-turbo | ~1.4 ГБ | Очень высокая | Очень высокая |
| `large` | models/whisper-large | ~3.1 ГБ | Умеренная | Очень высокая |

### Поддерживаемые аудиоформаты
- WAV (.wav)
- MP3 (.mp3)
- M4A (.m4a)
- FLAC (.flac)
- AAC (.aac)
- OGG (.ogg)
- WMA (.wma)
- WEBM (.webm)
- MP4 (.mp4)

### Требования к оборудованию
- **Обязательно**: Apple Silicon (M1/M2) Mac
- Рекомендуется: 8+ ГБ ОЗУ
- **Не поддерживается**: Intel Mac, Windows, Linux
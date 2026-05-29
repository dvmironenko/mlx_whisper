# oMLXEngine — механизм транскрибации через oMLX API

`oMLXEngine` — один из двух механизмов транскрипции в MLX-Transcriber (наряду с `WhisperEngine`). Реализует паттерн Strategy через абстрактный базовый класс `TranscriptionEngine`, обеспечивая единый формат результата для всех механизмов.

## Описание

Механизм выполняет транскрипцию аудио через HTTP API oMLX (oMLX-ASR модель). Автоматически разбивает длинное аудио на сегменты по тишине, транскрибирует каждый сегмент, объединяет результаты с корректными временными метками.

**Ключевые особенности:**

- Автоматическое разбиение аудио по тишине (librosa, порог 40 dB)
- Поддержка аудио любой длительности (группировка интервалов + разбиение по 50 мин)
- Определение спикеров (ID из ответа oMLX)
- Многоформатный парсинг JSON сегментов из ответа oMLX API
- Единый формат результата с `WhisperEngine`

## Использование

### Через API

```bash
# oMLX (по умолчанию)
curl -X POST http://localhost:8801/api/v1/transcribe \
  -F "file=@audio.wav" \
  -F "mechanism=omlx" \
  -F "language=ru"

# Через URL
curl -X POST http://localhost:8801/api/v1/transcribe-url \
  -F "url=https://example.com/audio.mp3" \
  -F "mechanism=omlx"
```

### Программно

```python
from src.services.whisper_engines import get_engine

engine = get_engine("omlx")
result = engine.transcribe(
    file_path="audio.wav",
    language="ru",
)

for seg in result["segments"]:
    print(f"[{seg['start']:.2f}-{seg['end']:.2f}] Speaker {seg['speaker']}: {seg['text']}")
```

## Единый формат результата

`oMLXEngine` возвращает результат в том же формате, что и `WhisperEngine`:

```json
{
  "segments": [
    {"start": 0.0, "end": 6.72, "speaker": 0, "text": "Здравствуйте."},
    {"start": 9.34, "end": 16.06, "speaker": 1, "text": "Добрый день."}
  ],
  "text": "Здравствуйте.\nДобрый день.",
  "speaker_detected": true,
  "transcription_duration": 12.5,
  "raw_response": "[{\"Start\":0,\"End\":6.72,\"Speaker\":0,\"Content\":\"Здравствуйте.\"},...]"
}
```

**Поля:**

- `segments` — массив сегментов с временными метками и спикерами
- `text` — полный текст расшифровки (сегменты объединены)
- `speaker_detected` — `true`, если в сегментах есть спикеры отличные от 0
- `transcription_duration` — общее время транскрипции в секундах
- `raw_response` — сырой ответ oMLX API (для отладки)

## Автоматическое разбиение аудио

### Поиск речевых интервалов

Используется `librosa.effects.split()` с порогом `top_db=40` (константа `SILENCE_THRESHOLD_DB`).

### Группировка интервалов

Интервалы с паузами менее 2 секунд объединяются в один, чтобы избежать создания множества мелких сегментов.

### Ограничения сегментов

- **Максимальная длительность:** 50 минут (`MAX_AUDIO_DURATION_SEC = 50 * 60`)
- **Максимальный размер загрузки:** 100 MB (`MAX_UPLOAD_BYTES = 100 * 1024 * 1024`)
- Если интервал превышает лимит, он разбивается на части по 50 минут

### Коррекция временных меток

При разбиении на сегменты каждый сегмент транскрибируется отдельно. Временные метки корректируются с учётом сдвига (`offset_sec = seg_start_samples / 16000.0`), чтобы сохранить глобальную временную шкалу.

## Парсинг JSON сегментов

oMLX API может возвращать сегменты в различных форматах. `oMLXEngine` поддерживает несколько стратегий парсинга:

### 1. Прямой JSON-массив

```json
[
  {"Start": 0, "End": 6.72, "Speaker": 0, "Content": "Текст"},
  {"Start": 9.34, "End": 16.06, "Speaker": 1, "Content": "Текст"}
]
```

### 2. Конкатенированные JSON-объекты oMLX

oMLX может возвращать объект, где поле `text` содержит JSON-массив сегментов. При длинном аудио объекты склеиваются:

```
{"text":"[{\"Start\":0,...}]"}{"text":"[{\"Start\":9,...}]"}
```

Функция `_split_concatenated_json()` разбивает строку на отдельные JSON-объекты с помощью `json.JSONDecoder.raw_decode()`.

### 3. JSON в code block

```json
```json
[{"Start": 0, ...}]
```

Извлекается по поиску маркеров ````json` и ````.

### 4. Regex fallback для обрезанного текста

Если ответ oMLX обрезан (неполный JSON), используется regex-паттерн для извлечения сегментов:

```python
r'\{"Start"\s*:\s*([\d.]+)(?:\s*,\s*"End"\s*:\s*([\d.]+))?(?:\s*,\s*"Speaker"\s*:\s*(\d+))?(?:\s*,\s*"Content"\s*:\s*"([^"]*(?:\\"[^"]*)*)")?\s*\}'
```

### 5. Текстовый fallback

Если JSON-парсинг полностью не удался, используется fallback-парсер для формата `[MM:SS] Speaker N: text`:

```
[00:00] Speaker 0: Текст речи
[00:15] Speaker 1: Ответ
```

## Модель VibeVoice-ASR-7B

`oMLXEngine` использует модель **VibeVoice-ASR-7B** от Microsoft — LLM-based STT (Speech-to-Text) модель, работающая через oMLX HTTP API.

### Архитектура

- **Базовая модель:** Qwen2.5-7B (LLM)
- **Механизм:** Next-token diffusion framework — LLM + diffusion head для генерации акустических деталей
- **Токенизаторы:** Continuous speech tokenizers — Acoustic + Semantic с frame rate 7.5 Hz
- **Языки:** 50+ языков (multilingual)
- **Макс. длительность:** До 60 минут аудио в один проход (без сегментации на входе)
- **Лицензия:** MIT License (ICLR 2026 Oral)

### Формат вывода модели

Модель генерирует LLM-вывод, который затем парсится через `parse_transcription()` (из `mlx_audio.stt.models.vibevoice_asr.vibevoice_asr`, строки 896-955).

**Системный промпт:**
```
You are a helpful assistant that transcribes audio input into text output in JSON format.
```

**Пользовательский промпт:**
```
This is {duration} seconds audio, please transcribe it with these keys: Start time, End time, Speaker ID, Content
```

**Сырой вывод (LLM-generated JSON):**
```json
[
  {"Start time": 0.0, "End time": 5.2, "Speaker ID": 0, "Content": "Привет"},
  {"Start time": 6.1, "End time": 10.5, "Speaker ID": 1, "Content": "Добрый день"}
]
```

Может быть обернут в markdown code block:
```json
```json
[{"Start time": 0.0, "End time": 5.2, "Speaker ID": 0, "Content": "Привет"}]
```
```

**Нормализация ключей:**

| Сырой ключ | Нормализованный ключ | Тип |
|------------|---------------------|-----|
| `"Start time"` или `"Start"` | `"start"` | float (секунды) |
| `"End time"` или `"End"` | `"end"` | float (секунды) |
| `"Speaker ID"` или `"Speaker"` | `"speaker_id"` | int (опционально) |
| `"Content"` | `"text"` | string |

**Извлечение JSON:**

1. Если есть ````json` — извлекает текст между ````json` и ````
2. Иначе ищет `[` или `{` и использует bracket counting для определения границ JSON
3. Парсит через `json.loads()`
4. Если результат — dict, оборачивает в список `[result]`
5. Применяет key mapping для нормализации
6. При любой ошибке (`json.JSONDecodeError` или другое исключение) возвращает пустой список `[]`

**Надёжность:** Ниже чем у Whisper, так как вывод LLM-генерируемый. JSON может быть некорректным, обрезанным или полностью отсутствовать. В случае неудачи `parse_transcription()` возвращает `[]`.

## Whisper-модели в oMLX

oMLX поддерживает Whisper-модели через бэкенд [mlx-audio](https://github.com/ml-explore/mlx-audio). Модели загружаются лениво при первом запросе транскрипции.

### Доступные модели

| Модель ID | Описание |
|-----------|----------|
| `whisper-large-v3-asr-fp16` | Whisper large v3, fp16 точность |
| `whisper-large-v3-turbo-asr-fp16` | Whisper large v3 turbo, fp16 точность |
| `whisper-medium-asr-fp16` | Whisper medium, fp16 точность |

### API

Используется тот же эндпоинт `POST /v1/audio/transcriptions`. Whisper-модели поддерживают дополнительный параметр `word_timestamps` — при `true` каждый сегмент включает массив `words` с пословными таймкодами:

```json
{
  "text": "Привет, мир.",
  "language": "russian",
  "duration": 2.5,
  "segments": [
    {
      "start": 0.0,
      "end": 1.2,
      "text": "Привет",
      "words": [
        {"word": "Привет", "start": 0.0, "end": 0.6, "probability": 0.95}
      ]
    }
  ]
}
```

### Пример curl

```bash
curl -X POST http://localhost:8880/v1/audio/transcriptions \
  -H "Authorization: Bearer 1234" \
  -F "file=@audio.wav" \
  -F "model=whisper-large-v3-asr-fp16" \
  -F "language=ru" \
  -F "word_timestamps=true"
```

### Особенности реализации

- **Нормализация языка:** ISO-коды маппятся на названия (`ru` → `russian`, `en` → `english`) для mlx-audio
- **preprocessor_config.json:** Обязателен для Whisper-моделей. Если файл отсутствует в MLX-конвертации, модель не загрузится с ошибкой 500. Фикс: скопировать `preprocessor_config.json`, `tokenizer.json` и `special_tokens_map.json` из HuggingFace репозитория в локальную модель
- **max_tokens:** По умолчанию 8192 (~24 минут аудио). Для длинных файлов увеличить через `settings.json` или параметр `max_tokens` в запросе
- **Diarization:** Whisper не поддерживает определение спикеров (diarization). Параметр `diarize` игнорируется
- **STTEngine:** Загрузка через `mlx_audio.stt.utils.load_model()`, транскрипция через `model.generate(audio_path, language=...)`

### Сравнение с VibeVoice-ASR

| Возможность | VibeVoice-ASR | Whisper |
|:------------|:--------------|:--------|
| Diarization (спикеры) | Да | Нет |
| Word timestamps | Нет | Да (`word_timestamps=true`) |
| Макс. длительность | До 60 мин | ~24 мин (без max_tokens) |
| Параметр `diarize` | Работает | Игнорируется |
| Требуется processor | Нет | `preprocessor_config.json` обязателен |

## Определение спикеров (VibeVoice)

oMLX API возвращает идентификаторы спикеров (0, 1, 2+). В текстовом выводе они отображаются как:

- `0`, `1`, `2+` — идентификаторы спикеров из ответа oMLX API (поле `speaker` в сегментах)

## Конфигурация

Переменные окружения для работы `oMLXEngine`:

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `OMLX_BASE_URL` | — | URL oMLX API (обязательно) |
| `OMLX_MODEL` | `oMLX-ASR-8bit` | Модель транскрипции |
| `OMLX_API_KEY` | — | API ключ для аутентификации |
| `OMLX_ENABLED` | `true` | Включён ли oMLX |

Если `OMLX_ENABLED=false` или `OMLX_BASE_URL` не указан, `oMLXEngine.transcribe()` выбросит `RuntimeError`.

## Архитектура

### Компоненты

**`oMLXEngine`** — основной класс, реализующий `TranscriptionEngine`:
- `transcribe(file_path, **params)` — полная транскрипция с разбиением
- `_transcribe_segment(file_path, language)` — транскрипция одного сегмента

**Модульные функции:**
- `_split_audio_by_silence(file_path)` — разбиение аудио на сегменты
- `_group_intervals(intervals, gap_samples)` — группировка интервалов
- `_save_segment(segment)` — сохранение сегмента во временный WAV
- `_parse_segments_from_json(raw_text)` — многоформатный парсинг JSON
- `_normalize_segments(items)` — нормализация в единый формат
- `_parse_segments_from_raw_text(raw_text)` — текстовый fallback-парсер

### Поток выполнения

```
audio.wav
    ↓
_split_audio_by_silence() — librosa.effects.split + группировка
    ↓
Для каждого сегмента:
    _transcribe_segment() — POST /audio/transcriptions
    ↓
    Коррекция временных меток (offset_sec)
    ↓
Объединение всех сегментов
    ↓
Возврат единого результата
```

## Ошибки и решения

### oMLX не настроен
**Причина:** `OMLX_ENABLED=false` или `OMLX_BASE_URL` не указан
**Решение:** Убедиться, что переменные окружения настроены корректно

### 401 Unauthorized
**Причина:** Отсутствует или неверный `OMLX_API_KEY`
**Решение:** Проверить API ключ в `.env` файле

### 404 Model not found
**Причина:** Модель не найдена на oMLX сервере
**Решение:** Проверить `OMLX_MODEL` и список доступных моделей через `GET /api/v1/omlx/health`

### 413 Payload Too Large
**Причина:** Сегмент превышает 100 MB
**Решение:** Автоматически обрабатывается — `_split_audio_by_silence()` разобьёт аудио на более мелкие сегменты

### Парсинг не находит сегменты
**Причина:** Непредсказуемый формат ответа oMLX
**Решение:** Функция `_parse_segments_from_json()` последовательно пробует все стратегии; текстовый fallback (`_parse_segments_from_raw_text()`) обрабатывает формат `[MM:SS] Speaker N: text`

## Зависимости

- `librosa` — анализ аудио (поиск тишины)
- `pydub` — работа с аудио-сегментами
- `requests` — HTTP-клиент для oMLX API
- `librosa` и `pydub` импортируются лениво (внутри функций), чтобы не нагружать основную транскрипцию

## Внешняя документация

- [oMLX API — audio_models.py](https://github.com/jundot/omlx/blob/main/omlx/api/audio_models.py) — спецификация API endpoints и моделей для аудио-транскрипции
- [oMLX API — audio_routes.py](https://github.com/jundot/omlx/blob/main/omlx/api/audio_routes.py) — маршрутизация API endpoints для аудио-транскрипции
- [oMLX API — stt.py](https://github.com/jundot/omlx/blob/main/omlx/engine/stt.py) — STTEngine: загрузка моделей и транскрипция через mlx-audio
- [mlx-audio STT](https://github.com/ml-explore/mlx-audio) — бэкенд для STT/ASR в oMLX, поддерживает Whisper и VibeVoice
- [VibeVoice-ASR на Hugging Face](https://huggingface.co/microsoft/VibeVoice-ASR) — архитектура модели, веса и документация от Microsoft
- [VibeVoice на GitHub](https://github.com/microsoft/VibeVoice) — репозиторий Microsoft с исходным кодом и описанием архитектуры

## Лицензия

MIT License

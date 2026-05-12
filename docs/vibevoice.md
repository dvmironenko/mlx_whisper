# VibeVoiceEngine — механизм транскрибации через oMLX API

`VibeVoiceEngine` — один из двух механизмов транскрипции в MLX-Whisper (наряду с `WhisperEngine`). Реализует паттерн Strategy через абстрактный базовый класс `TranscriptionEngine`, обеспечивая единый формат результата для всех механизмов.

## Описание

Механизм выполняет транскрипцию аудио через HTTP API oMLX (VibeVoice-ASR модель). Автоматически разбивает длинное аудио на сегменты по тишине, транскрибирует каждый сегмент, объединяет результаты с корректными временными метками.

**Ключевые особенности:**

- Автоматическое разбиение аудио по тишине (librosa, порог 40 dB)
- Поддержка аудио любой длительности (группировка интервалов + разбиение по 50 мин)
- Определение спикеров (0 → "Клиент", 1 → "Терапевт")
- Многоформатный парсинг JSON сегментов из ответа oMLX API
- Единый формат результата с `WhisperEngine`

## Использование

### Через API

```bash
# MLX Whisper (по умолчанию)
curl -X POST http://localhost:8801/api/v1/transcribe \
  -F "file=@audio.wav" \
  -F "mechanism=vibevoice" \
  -F "language=ru"

# Через URL
curl -X POST http://localhost:8801/api/v1/transcribe-url \
  -F "url=https://example.com/audio.mp3" \
  -F "mechanism=vibevoice"
```

### Программно

```python
from src.services.transcription_engines import get_engine

engine = get_engine("vibevoice")
result = engine.transcribe(
    file_path="audio.wav",
    language="ru",
)

for seg in result["segments"]:
    print(f"[{seg['start']:.2f}-{seg['end']:.2f}] Speaker {seg['speaker']}: {seg['text']}")
```

## Единый формат результата

`VibeVoiceEngine` возвращает результат в том же формате, что и `WhisperEngine`:

```json
{
  "segments": [
    {"start": 0.0, "end": 6.72, "speaker": 0, "text": "Здравствуйте."},
    {"start": 9.34, "end": 16.06, "speaker": 1, "text": "Добрый день."}
  ],
  "text": "Клиент: Здравствуйте.\nТерапевт: Добрый день.",
  "speaker_detected": true,
  "transcription_duration": 12.5,
  "raw_response": "[{\"Start\":0,\"End\":6.72,\"Speaker\":0,\"Content\":\"Здравствуйте.\"},...]"
}
```

**Поля:**

- `segments` — массив сегментов с временными метками и спикерами
- `text` — текст с метками спикеров (Клиент/Терапевт)
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

oMLX API может возвращать сегменты в различных форматах. `VibeVoiceEngine` поддерживает несколько стратегий парсинга:

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

## Определение спикеров

oMLX API возвращает идентификаторы спикеров (0, 1, 2...). В текстовом выводе они отображаются как:

- `0` → "Клиент"
- `1` → "Терапевт"
- `2+` → "Speaker N"

## Конфигурация

Переменные окружения для работы `VibeVoiceEngine`:

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `OMLX_BASE_URL` | — | URL oMLX API (обязательно) |
| `OMLX_MODEL` | `VibeVoice-ASR-4bit` | Модель транскрипции |
| `OMLX_API_KEY` | — | API ключ для аутентификации |
| `OMLX_ENABLED` | `true` | Включён ли VibeVoice |

Если `OMLX_ENABLED=false` или `OMLX_BASE_URL` не указан, `VibeVoiceEngine.transcribe()` выбросит `RuntimeError`.

## Архитектура

### Компоненты

**`VibeVoiceEngine`** — основной класс, реализующий `TranscriptionEngine`:
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

## Лицензия

MIT License

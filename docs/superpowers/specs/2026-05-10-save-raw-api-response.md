# Сохранение исходного ответа API транскрибации

**Дата:** 2026-05-10

## Контекст

Модели транскрибации (Whisper и VibeVoice/oMLX) возвращают структурированные данные, которые парсятся и нормализуются внутри приложения. Исходный ответ API теряется после парсинга. Это затрудняет отладку и анализ — невозможно посмотреть, что именно вернула модель "как есть".

**Цель:** Сохранять исходный ответ каждой модели транскрибации в папке задания.

## Принятые решения

1. **Что сохранять:** Исходный ответ API (сырые данные до парсинга)
2. **Где сохранять:** В `TranscriptionQueueManager._worker_process()` — там же, где текущие `.txt` и `_segments.json` файлы
3. **Подход:** Добавить optional поле `raw_response` в возвращаемый словарь каждого механизма транскрибации

## Архитектура

### 1. TranscriptionEngine ABC

Обновить docstring метода `transcribe()` — добавить optional поле `raw_response` в описание возвращаемого словаря. Реализационно изменений нет — это чисто документационное изменение.

**Файл:** `src/services/transcription_engines.py:22-48`

### 2. WhisperEngine

MLX Whisper возвращает Python dict с полями `segments`, `text`, `transcribe_duration`, `audio_duration`.

- Добавить `import json`
- Сериализовать `result` в JSON-строку **до** нормализации
- Добавить `"raw_response": raw_json` в возвращаемый словарь
- Если сериализация не удалась — `raw_response = None`

**Файл:** `src/services/transcription_engines.py:62-130`

### 3. VibeVoiceEngine

oMLX API возвращает JSON в `response.text`. Ответ приходит по частям (конкатенированные JSON-объекты).

- В `_transcribe_segment()` собрать все `raw_text` из каждого сегмента
- Добавить `"raw_response": raw_text` в return
- В `transcribe()` агрегировать `raw_response` из всех сегментов
- Если парсинг не удался для всех сегментов — `raw_response = None`

**Файл:** `src/services/vibevoice_engine.py:316-398`

### 4. TranscriptionQueueManager

В `_worker_process()` после получения `result` от движка:

```python
raw_response = result.get("raw_response")
if raw_response:
    raw_path = os.path.join(job_dir, f"{base_name}_raw.json")
    if isinstance(raw_response, dict):
        raw_response = json.dumps(raw_response, ensure_ascii=False, indent=2)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_response)
```

**Файл:** `src/services/transcription_queue.py:201-216`

## Формат файлов

После транскрипции в папке задания (`results/<job_id>/`) будут создаваться:

| Файл | Описание |
|------|----------|
| `{имя}.txt` | Нормализованный текст с метками спикеров |
| `{имя}_segments.json` | Нормализованные сегменты |
| `{имя}_raw.json` | **Новый:** исходный ответ API |

## Форматы raw_response

- **Whisper:** JSON-строка с полями `segments`, `text`, `transcribe_duration`, `audio_duration`
- **VibeVoice:** JSON-массив сегментов с полями `Start`, `End`, `Speaker`, `Content` (возможно, конкатенированные объекты)

## Тестирование

1. `python -m pytest tests/test_transcription_engines.py -v` — тесты WhisperEngine
2. `python -m pytest tests/test_vibevoice_engine.py -v` — тесты VibeVoiceEngine
3. `python -m pytest tests/test_transcription_queue.py -v` — тесты TranscriptionQueueManager
4. Ручная проверка: запустить сервер, транскрибировать аудио, проверить наличие `{имя}_raw.json` в `results/<job_id>/`

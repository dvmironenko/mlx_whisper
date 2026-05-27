# oMLX Segment Format: MP3 → OPUS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить MP3 на OPUS при сохранении сегментов oMLX для уменьшения размера временных файлов.

**Architecture:** Прямая замена формата в `_save_segment()` и MIME-маппинга в `_transcribe_segment()` в `omlx_engine.py`. pydub + FFmpeg уже поддерживают OPUS.

**Tech Stack:** Python, pydub, FFmpeg

---

### Task 1: Заменить формат сегментов на OPUS

**Files:**
- Modify: `src/services/omlx_engine.py:137-150`
- Modify: `src/services/omlx_engine.py:342-343`

- [ ] **Step 1: Обновить `_save_segment()` — suffix, format, bitrate**

В `src/services/omlx_engine.py`, функция `_save_segment()` (строки 137-150):

```python
# Было (строка 138-139):
def _save_segment(segment: AudioSegment) -> str:
    """Сохранить сегмент во временный MP3 файл для отправки в oMLX API."""
    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="omlx_segment_")

# Стало:
def _save_segment(segment: AudioSegment) -> str:
    """Сохранить сегмент во временный OPUS файл для отправки в oMLX API."""
    fd, path = tempfile.mkstemp(suffix=".opus", prefix="omlx_segment_")
```

- [ ] **Step 2: Обновить `_save_segment()` — format и bitrate**

В той же функции (строка 142):

```python
# Было (строка 142):
segment.export(path, format="mp3", bitrate="64k")

# Стало:
segment.export(path, format="opus", bitrate="48k")
```

- [ ] **Step 3: Обновить MIME-маппинг в `_transcribe_segment()`**

В `src/services/omlx_engine.py`, функция `_transcribe_segment()` (строка 343):

```python
# Было (строка 343):
mime_type = {"wav": "audio/wav", ".mp3": "audio/mpeg"}.get(ext, "application/octet-stream")

# Стало:
mime_type = {"wav": "audio/wav", ".opus": "audio/opus"}.get(ext, "application/octet-stream")
```

- [ ] **Step 4: Запустить приложение и проверить что транскрибация проходит**

Перезапустить сервер MLX-Transcriber и выполнить быструю транскрибацию короткого файла через oMLX механизм. Убедиться что:
- Сегменты сохраняются как `.opus`
- oMLX API принимает файлы без ошибок
- Транскрибация завершается успешно

- [ ] **Step 5: Commit**

```bash
git add src/services/omlx_engine.py
git commit -m "feat: use OPUS format for oMLX segment files

Replace MP3 with OPUS (48k) for segment files to reduce temp file size.
OPUS is a native format supported by oMLX API.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

## Self-Review

1. **Spec coverage:** Все требования из спецификации покрыты — suffix, format, bitrate, MIME type, docstring.
2. **Placeholder scan:** Нет placeholder'ов, все шаги содержат конкретный код.
3. **Type consistency:** Типы и сигнатуры не меняются, только значения параметров.

## Execution Handoff

План готов. Два варианта исполнения:

**1. Subagent-Driven (рекомендуется)** — отдельный саб-agent на задачу, ревью между задачами

**2. Inline Execution** — выполняю задачи в этой сессии

Какой подход?

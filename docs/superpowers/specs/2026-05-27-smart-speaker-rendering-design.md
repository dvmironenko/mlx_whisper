# Автоопределение спикеров в расшифровке

## Контекст

Функция `_build_formatted_text_from_segments` в [whisper_engines.py:152-179](src/services/whisper_engines.py#L152-L179) принимает параметр `include_speaker=True` и всегда рендерит метки спикеров (например, `[00:00] Спикер 0 : текст`).

OMLXEngine вызывает эту функцию с `include_speaker=True` ([omlx_engine.py:300-301](src/services/omlx_engine.py#L300-L301)), даже когда API возвращает новый формат `{"segments": [{"start": 0, "end": 12.67, "text": "..."}]}` без поля `speaker` — в результате отображается "Спикер 0" для всех сегментов, что вводит в заблуждение.

Старый формат API `{"text": "[{...Speaker:0...}]"} ` содержит информацию о спикерах и корректно отображает их.

## Цель

Функция `_build_formatted_text_from_segments` должна автоматически определять, содержат ли сегменты информацию о спикерах, и рендерить метки только при их наличии.

## Подход

**Автоопределение по наличию поля `speaker != 0` в сегментах.**

Изменить `_build_formatted_text_from_segments` — убрать параметр `include_speaker`, заменить на сканирование сегментов. Если хотя бы один сегмент имеет `speaker != 0`, рендерить с метками. Иначе — без меток.

### Изменения в `_build_formatted_text_from_segments`

**Было** ([whisper_engines.py:152-179](src/services/whisper_engines.py#L152-L179)):
```python
def _build_formatted_text_from_segments(
    segments: list[dict],
    *,
    include_speaker: bool = False,
    include_timestamps: bool = True,
) -> str:
    lines: list[str] = []
    for seg in segments:
        start = seg.get("start", 0)
        speaker = seg.get("speaker", 0)
        text = seg.get("text", "").strip()
        if not text:
            continue
        if include_timestamps:
            minutes = int(start) // 60
            seconds = int(start) % 60
            if include_speaker:
                lines.append(f"[{minutes:02d}:{seconds:02d}] Спикер {speaker} : {text}")
            else:
                lines.append(f"[{minutes:02d}:{seconds:02d}]: {text}")
        else:
            lines.append(text)
    return "\n".join(lines)
```

**Стало**:
```python
def _build_formatted_text_from_segments(
    segments: list[dict],
    *,
    include_timestamps: bool = True,
) -> str:
    # Автоопределение: спикеры есть, если хотя бы у одного сегмента
    # speaker != 0
    has_speakers = any(seg.get("speaker", 0) != 0 for seg in segments)

    lines: list[str] = []
    for seg in segments:
        start = seg.get("start", 0)
        speaker = seg.get("speaker", 0)
        text = seg.get("text", "").strip()
        if not text:
            continue
        if include_timestamps:
            minutes = int(start) // 60
            seconds = int(start) % 60
            if has_speakers:
                lines.append(f"[{minutes:02d}:{seconds:02d}] Спикер {speaker} : {text}")
            else:
                lines.append(f"[{minutes:02d}:{seconds:02d}]: {text}")
        else:
            lines.append(text)
    return "\n".join(lines)
```

### Изменения на вызывающих

1. **[omlx_engine.py:300-301](src/services/omlx_engine.py#L300-L301)** — убрать `include_speaker=True`:
```python
formatted_text = _build_formatted_text_from_segments(
    all_segments, include_timestamps=include_timestamps
)
```

2. **[whisper_engines.py:136](src/services/whisper_engines.py#L136)** — WhisperEngine тоже вызывает эту функцию, убрать `include_speaker=False` (он всегда False, и автоопределение даст тот же результат).

### WhisperEngine

Для локального Whisper спикеры не поддерживаются (`speaker_detected: False`), поэтому автоопределение будет корректно рендерить без меток.

## Файлы для изменения

1. `src/services/whisper_engines.py` — `_build_formatted_text_from_segments`, вызов в WhisperEngine
2. `src/services/omlx_engine.py` — вызов `_build_formatted_text_from_segments`

## Верификация

1. Запустить сервер: `source .venv/bin/activate && python src/main.py`
2. Транскрибировать аудио через oMLX (новый формат API без спикеров) — в модальном окне результата не должно быть "Спикер 0"
3. Транскрибировать аудио через oMLX со старым форматом API (со спикерами) — метки спикеров должны отображаться
4. Транскрибировать через локальный Whisper — без меток спикеров

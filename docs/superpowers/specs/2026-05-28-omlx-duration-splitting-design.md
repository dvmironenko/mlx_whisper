# oMLX Duration Check and Silence-Based Splitting Design

> **Problem:** OMLXEngine.transcribe() отправляет весь WAV-файл одним запросом без проверки длительности. Если файл > 60 минут, oMLX API может отказать.
>
> **Solution:** Проверять длительность перед отправкой. Если > 60 мин — разбить аудио по тишине на сегменты ≤ 60 мин, транскрибировать каждый отдельно, скорректировать таймкоды.

---

## Architecture

### Текущий поток (REMOVE_SILENCE=True)

```
file_path (WAV, silence removed by FFmpeg)
  → _transcribe_file(file_path)
    → open(file) → requests.post()
    → JSON → _normalize_segments()
    → _reconcile_speaker_ids()
    → result
```

### Новый поток (duration ≤ 60 мин)

```
file_path (WAV)
  → get_audio_duration(file_path) → ≤ 3600s
  → _transcribe_file(file_path)
    → open(file) → requests.post()
    → result
```

### Новый поток (duration > 60 мин)

```
file_path (WAV)
  → get_audio_duration(file_path) → > 3600s
  → _split_and_transcribe(file_path)
    → pydub AudioSegment.from_file()
    → _detect_silence_chunks() → non-silent intervals
    → for each interval:
        → split into ≤ 60 min chunks
        → export each chunk as WAV bytes (BytesIO)
        → _transcribe_segment(audio_bytes)
        → offset correction (start_ms / 1000)
    → _reconcile_speaker_ids(all_segments)
    → result
```

---

## Components

### 1. Константы

**File:** `src/services/omlx_engine.py`

```python
MAX_AUDIO_DURATION_SEC: int = 60 * 60  # 60 минут
```

### 2. `OMLXEngine.transcribe()` — проверка длительности

**File:** `src/services/omlx_engine.py:176-212`

Добавить проверку после валидации OMLX:

```python
duration = get_audio_duration(file_path)
if duration and duration > MAX_AUDIO_DURATION_SEC:
    return self._split_and_transcribe(file_path, language=language, model=omlx_model, include_timestamps=include_timestamps)
```

### 3. `OMLXEngine._split_and_transcribe()` — новый метод

**File:** `src/services/omlx_engine.py`

```python
def _split_and_transcribe(
    self,
    file_path: str,
    language: Optional[str] = None,
    model: Optional[str] = None,
    include_timestamps: bool = True,
) -> Dict[str, Any]:
    """Разбить аудио по тишине на сегменты ≤ 60 мин и транскрибировать каждый."""
    from pydub import AudioSegment
    
    audio = AudioSegment.from_file(file_path)
    non_silent = _detect_silence_chunks(audio, gap_ms=SILENCE_GAP_MS)
    
    if not non_silent:
        # Чистая тишина — fallback
        return {"segments": [], "text": "", "raw_response": None}
    
    all_segments: List[Dict[str, Any]] = []
    max_chunk_ms = MAX_AUDIO_DURATION_SEC * 1000
    
    for start_ms, end_ms in non_silent:
        duration_ms = end_ms - start_ms
        for chunk_start in range(0, duration_ms, max_chunk_ms):
            abs_start = start_ms + chunk_start
            abs_end = min(abs_start + max_chunk_ms, end_ms)
            
            segment = audio[abs_start:abs_end]
            buf = BytesIO()
            segment.export(buf, format="wav")
            
            seg_result = self._transcribe_segment(
                buf.getvalue(), language=language, model=model
            )
            
            # Offset correction: добавить смещение сегмента к таймкодам
            offset_sec = abs_start / 1000.0
            for seg in seg_result["segments"]:
                seg["start"] += offset_sec
                seg["end"] += offset_sec
            
            all_segments.extend(seg_result["segments"])
    
    all_segments = _reconcile_speaker_ids(all_segments)
    
    formatted_text = _build_formatted_text_from_segments(
        all_segments, include_timestamps=include_timestamps
    )
    
    return {
        "segments": all_segments,
        "text": formatted_text,
        "speaker_detected": bool(all_segments and any(s.get("speaker", 0) != 0 for s in all_segments)),
        "transcription_duration": round(time.time() - start_time, 2),
        "raw_response": None,
    }
```

### 4. Вернуть удалённые функции

Для сегментации нужны:
- `_detect_silence_chunks()` — RMS-детекция тишины по raw samples pydub AudioSegment
- `_transcribe_segment()` — POST аудио-байтов через BytesIO

Обе функции были удалены при упрощении (commit 75c764c).

### 5. Импорт `get_audio_duration`

**File:** `src/services/omlx_engine.py`

```python
from src.utils.audio import get_audio_duration
```

---

## Data Flow

### REMOVE_SILENCE=True, duration ≤ 60 мин

```
file_path → get_audio_duration() → ≤ 3600s
  → _transcribe_file(file_path)
    → open(file) → requests.post()
    → result (1 запрос)
```

### REMOVE_SILENCE=True, duration > 60 мин

```
file_path → get_audio_duration() → > 3600s
  → _split_and_transcribe(file_path)
    → pydub AudioSegment.from_file()
    → _detect_silence_chunks() → non-silent intervals
    → for each interval → split into ≤ 60 min chunks
    → for each chunk:
        → BytesIO + WAV export
        → _transcribe_segment(audio_bytes)
        → offset correction
    → _reconcile_speaker_ids()
    → result (N запросов)
```

---

## Error Handling

- `get_audio_duration()` возвращает `None` → fallback на `_transcribe_file()` (предполагаем, что файл < 60 мин)
- `AudioSegment.from_file()` падает → propagate to caller
- `_transcribe_segment()` падает → logging + continue (как в старом коде)
- `OMLXModelNotFoundError` → raise immediately (как в старом коде)

---

## Testing

### Unit tests (tests/test_omlx_engine.py)

1. **Test `transcribe` with duration ≤ 60 min** — mock `get_audio_duration` → 300s, verify `_transcribe_file` called
2. **Test `transcribe` with duration > 60 min** — mock `get_audio_duration` → 4000s, verify `_split_and_transcribe` called
3. **Test `_split_and_transcribe` splits correctly** — mock AudioSegment + `_detect_silence_chunks`, verify correct number of segments
4. **Test `_split_and_transcribe` offset correction** — verify timestamps are adjusted by segment start offset
5. **Test `_split_and_transcribe` handles pure silence** — returns empty segments
6. **Test `_detect_silence_chunks`** — restore existing tests for the function

### Integration tests

- No changes needed — integration tests test behavior, not internal dispatch logic

---

## Files Modified

| File | Changes |
|---|---|
| `src/services/omlx_engine.py` | Add `MAX_AUDIO_DURATION_SEC`, add `get_audio_duration` import, restore `_detect_silence_chunks` + `_transcribe_segment`, add `_split_and_transcribe()`, modify `transcribe()` dispatch |
| `tests/test_omlx_engine.py` | Add tests for duration check, `_split_and_transcribe`, restore `_detect_silence_chunks` tests |

## Files NOT Modified

- `src/utils/audio.py` — `get_audio_duration()` уже существует, без изменений
- `src/api/router.py` — без изменений
- `src/services/transcription_queue.py` — без изменений
- `_normalize_segments()`, `_repair_truncated_json()`, `_reconcile_speaker_ids()` — без изменений

---

## Performance Impact

| Metric | Before | After (≤ 60 min) | After (> 60 min) |
|---|---|---|---|
| Duration check | None | `ffprobe` subprocess (~50ms) | `ffprobe` subprocess (~50ms) |
| pydub loads | 0 | 0 | 1 + N_chunks |
| WAV exports | 0 | 0 | N_chunks |
| API requests | 1 | 1 | N_chunks |
| Total latency | ~T | ~T | ~T × N_chunks |

**Net result:** +50ms overhead для проверки длительности. Для файлов > 60 мин — необходимая сегментация вместо потенциального API-отказа.

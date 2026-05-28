# oMLX Silence Detection Optimization Design

> **Problem:** Audio is processed by FFmpeg `silenceremove` filter during WAV conversion, then `_split_audio_by_silence()` runs pydub-based silence detection AGAIN on the already-cleaned WAV. This is redundant CPU work.

> **Solution:** When `REMOVE_SILENCE=True`, skip pydub silence detection entirely and pass the WAV file directly to the oMLX API as a single segment.

---

## Architecture

### Current flow (REMOVE_SILENCE=True)

```
Upload → FFmpeg silenceremove → WAV (silence removed)
       → pydub AudioSegment.from_file() → struct.unpack → RMS per chunk
       → _detect_silence_chunks() → merge gaps → _split_audio_by_silence()
       → per-segment BytesIO + WAV export → oMLX API per segment
```

### New flow (REMOVE_SILENCE=True)

```
Upload → FFmpeg silenceremove → WAV (silence removed)
       → oMLX API (single request, direct file)
```

**Eliminated:** pydub loading, struct.unpack, RMS computation, silence merging, per-segment WAV export.

### Flow (REMOVE_SILENCE=False)

No changes — existing `_split_audio_by_silence()` path remains intact.

---

## Components

### 1. `OMLXEngine.transcribe()` — conditional dispatch

**File:** `src/services/omlx_engine.py:287-343`

Add conditional check on `REMOVE_SILENCE` from config:

- **True:** Call `_transcribe_file(file_path, ...)` — direct file to API
- **False:** Call `_split_audio_by_silence(file_path)` → iterate → `_transcribe_segment(audio_bytes, ...)`

### 2. `OMLXEngine._transcribe_file()` — new method

**File:** `src/services/omlx_engine.py`

```python
def _transcribe_file(
    self,
    file_path: str,
    language: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Transcribe a single file directly via oMLX API (no segmentation)."""
    url = f"{OMLX_BASE_URL}/audio/transcriptions"
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "audio/wav")}
    data = {"model": model or OMLX_MODEL, "diarize": True}
    if language:
        data["language"] = language
    headers = {"Authorization": f"Bearer {OMLX_API_KEY}"} if OMLX_API_KEY else {}
    response = requests.post(url, files=files, data=data, headers=headers, timeout=(10, 3600))
    ...parse response same as _transcribe_segment...
```

Key differences from `_transcribe_segment`:
- Accepts `file_path` instead of `audio_bytes`
- Opens file with `open()` instead of creating BytesIO
- No timestamp offset correction (single segment, no offset needed)
- No speaker reconciliation needed (single segment = single speaker ID space)

### 3. Import additions

**File:** `src/services/omlx_engine.py`

```python
import os
from src.config import REMOVE_SILENCE  # add to existing config imports
```

---

## Data Flow

### REMOVE_SILENCE=True

```
file_path (WAV, silence removed)
  → _transcribe_file(file_path)
    → requests.post(file=...)
    → JSON response
    → _normalize_segments(items)
    → segments (single entry or multi from API)
    → _reconcile_speaker_ids(segments)  # no-op for single segment
    → _build_formatted_text_from_segments(segments)
    → result dict
```

### REMOVE_SILENCE=False

```
file_path (WAV, silence NOT removed)
  → _split_audio_by_silence(file_path)
    → pydub AudioSegment.from_file()
    → struct.unpack raw samples
    → RMS per 100ms chunk
    → silence threshold check → non-silent intervals
    → merge gaps (2s)
    → per-interval WAV export via BytesIO
    → list of (start_ms, end_ms, audio_bytes)
  → for each segment:
      → _transcribe_segment(audio_bytes)
      → timestamp offset correction (start_ms / 1000)
  → _reconcile_speaker_ids(all_segments)
  → _build_formatted_text_from_segments(all_segments)
  → result dict
```

---

## Error Handling

- `_transcribe_file` reuses same error handling as `_transcribe_segment`:
  - 404 with `not_found_error` → `OMLXModelNotFoundError`
  - Other HTTP errors → `raise_for_status()`
  - JSON parse errors → logged and empty segments returned
- File open errors (permission, missing) → propagate to caller
- No change to existing error handling semantics

---

## Testing

### Unit tests (tests/test_omlx_engine.py)

1. **Test `_transcribe_file` sends direct file** — mock `open()` and `requests.post`, verify file is passed as-is
2. **Test `transcribe` with REMOVE_SILENCE=True** — verify `_transcribe_file` called, `_split_audio_by_silence` NOT called
3. **Test `transcribe` with REMOVE_SILENCE=False** — verify existing path unchanged
4. **Test `_transcribe_file` response parsing** — same as existing `_transcribe_segment` tests

### Integration tests

- No changes needed — integration tests test behavior, not internal dispatch logic

---

## Files Modified

| File | Changes |
|---|---|
| `src/services/omlx_engine.py` | Add `import os`, add `REMOVE_SILENCE` to config imports, add `_transcribe_file()` method, modify `transcribe()` dispatch logic |
| `tests/test_omlx_engine.py` | Add tests for `_transcribe_file` and conditional dispatch |

## Files NOT Modified

- `src/utils/audio.py` — FFmpeg silenceremove unchanged
- `src/api/router.py` — WAV conversion unchanged
- `src/services/transcription_queue.py` — queue worker unchanged
- `_split_audio_by_silence()` — kept for REMOVE_SILENCE=False path
- `_detect_silence_chunks()` — kept for REMOVE_SILENCE=False path
- `_normalize_segments()` — unchanged
- `_reconcile_speaker_ids()` — unchanged (still needed for multi-segment case)

---

## Performance Impact

| Metric | Before (REMOVE_SILENCE=True) | After (REMOVE_SILENCE=True) |
|---|---|---|
| pydub loads | 1 + N_segments | 0 |
| WAV exports | N_segments | 0 |
| RMS computations | ~30 per second of audio | 0 |
| API requests | N_segments | 1 |
| CPU time (pre-processing) | ~2-5s for 5min audio | ~0s |

**Net result:** Elimination of ~2-5s CPU overhead per transcription when `REMOVE_SILENCE=True`.

# oMLX Transcription — Design Spec

**Date:** 2026-05-08
**Status:** Approved

## Context

Проект mlx_whisper поддерживает один механизм транскрипции — MLX Whisper. Необходимо добавить второй механизм через oMLX API (oMLX-ASR модель).

## Architecture

```
src/
├── services/
│   ├── transcription_engines.py    # NEW: TranscriptionEngine ABC + WhisperEngine + oMLXEngine
│   ├── transcription_queue.py      # MODIFY: accept engine
│   └── ...
├── models/
│   └── transcription.py            # MODIFY: encapsulate Whisper logic into WhisperEngine
├── config.py                       # MODIFY: add OMLX_* vars
├── api/
│   └── router.py                   # MODIFY: mechanism parameter
└── main.py                         # MODIFY: resolve engine at startup

templates/
└── uploads.html                    # MODIFY: mechanism select

static/
└── new_style.css                   # MODIFY: styles for select
```

## TranscriptionEngine Interface

```python
class TranscriptionEngine(ABC):
    @abstractmethod
    def transcribe(self, file_path: str, **params) -> dict:
        """
        Returns normalized dict:
        {
            "segments": [{"id": int, "text": str, "start": float, "end": float, "speaker": int?}],
            "text": str,
            "speaker_detected": bool
        }
        """
```

### WhisperEngine
Encapsulates current `transcribe_audio()` logic from `src/models/transcription.py`. Uses MLX Whisper. No speaker detection (sets `speaker_detected: false`).

### oMLXEngine
New implementation:
1. Check audio duration via `ffprobe`
2. If > 50 min: split by silence (librosa + pydub, same logic as `transcribe_audio.py` from omlx.md)
3. For each segment: POST to `OMLX_BASE_URL/v1/audio/transcriptions`
4. Parse result: JSON first, fallback to text parsing
5. Normalize to unified segment format with speaker info

## Configuration (env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `OMLX_BASE_URL` | — | oMLX server URL (required for oMLX) |
| `OMLX_MODEL` | `oMLX-ASR-4bit` | Model identifier |
| `OMLX_API_KEY` | `None` | API key (optional) |
| `OMLX_ENABLED` | `true` | Enable/disable oMLX |

## API Changes

### POST /api/v1/transcribe
New form parameter:
- `mechanism: str = Form("whisper")` — values: `whisper` | `omlx`

When `mechanism=omlx`:
- Whisper-specific params (remove_silence, silence_threshold, etc.) are accepted but ignored
- Only `language` and `model` are used

### GET /api/v1/config
Extended response:
```json
{
  "omlx_enabled": true,
  "omlx_available": true,
  "...existing fields..."
}
```

### GET /api/v1/omlx/health (NEW)
Health check for oMLX connection. Returns `{"available": true}` or `{"available": false, "error": "..."}`.

## Frontend Changes

### uploads.html
- Add `<select name="mechanism">` with options: Whisper (MLX), oMLX (oMLX)
- Default: `whisper`
- JS behavior:
  - Switching to `omlx`: hide `remove_silence`, `silence_threshold`, `silence_duration`, `word_timestamps`, `condition_on_previous_text`, `no_speech_threshold`, `hallucination_silence_threshold`, `initial_prompt` fields
  - Switching to `whisper`: show all Whisper fields
- Form submission includes `mechanism` field

### Config loading
- `loadConfig()` uses `omlx_enabled` to show/hide mechanism select
- If `omlx_available: false`, disable oMLX option

## Error Handling

| Error | Behavior |
|-------|----------|
| oMLX unavailable | Job `Failed`, error message in metadata |
| Segment transcription fails | Skip segment, log error, continue |
| File > 100 MB | Auto-split into < 100 MB parts |
| 401/403 from oMLX | Job `Failed` with specific message |

## Dependencies

Add to `requirements.txt` (conditional):
- `requests` (for oMLX HTTP calls)
- `librosa` (for silence detection in oMLX)
- `pydub` (for audio splitting in oMLX)

Conditional import in `oMLXEngine`:
```python
try:
    import librosa
    import pydub
except ImportError:
    raise RuntimeError("librosa and pydub required for oMLX")
```

## Verification

1. Run `python src/main.py`
2. Upload audio via UI, select oMLX
3. Verify: results appear in jobs list, segments with speaker, text is correct
4. Switch to Whisper — verify Whisper path still works
5. Run `pytest tests/` — all existing tests pass

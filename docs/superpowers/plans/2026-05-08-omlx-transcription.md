# oMLX Transcription — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить второй механизм транскрипции (oMLX/oMLX API) alongside existing MLX Whisper с выбором через UI.

**Architecture:** Strategy pattern — TranscriptionEngine ABC, WhisperEngine + oMLXEngine. Queue manager выбирает engine по механизму. Фронтенд показывает/скрывает Whisper-параметры при переключении.

**Tech Stack:** Python, FastAPI, MLX Whisper, oMLX HTTP API (requests), librosa, pydub, Jinja2

---

## Task 1: Install dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add librosa and pydub to requirements.txt**

Убедиться что в `requirements.txt` есть:
```
librosa>=0.10.0
pydub>=0.25.1
```

Опционально: если `requests` уже есть — добавлять не нужно.

- [ ] **Step 2: Install dependencies**

```bash
pip install librosa pydub requests
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add librosa and pydub for oMLX engine"
```

---

## Task 2: Add OMLX config variables

**Files:**
- Modify: `src/config.py:~1-30`

- [ ] **Step 1: Add OMLX config variables to config.py**

После существующих MLX_ переменных добавить:

```python
# OMLX / oMLX Configuration
OMLX_BASE_URL: str = os.getenv("OMLX_BASE_URL", "")
OMLX_MODEL: str = os.getenv("OMLX_MODEL", "oMLX-ASR-4bit")
OMLX_API_KEY: Optional[str] = os.getenv("OMLX_API_KEY") or None
OMLX_ENABLED: bool = os.getenv("OMLX_ENABLED", "true").lower() == "true"
```

Создать helpers:
```python
def omlx_available() -> bool:
    """Check if oMLX is configured and enabled."""
    if not OMLX_ENABLED:
        return False
    return bool(OMLX_BASE_URL)
```

- [ ] **Step 2: Test config loads**

```bash
python -c "from src.config import OMLX_BASE_URL, OMLX_ENABLED, omlx_available; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat: add OMLX config variables for oMLX"
```

---

## Task 3: Create TranscriptionEngine ABC + WhisperEngine

**Files:**
- Create: `src/services/transcription_engines.py`
- Modify: `src/models/transcription.py` (extract to WhisperEngine)

- [ ] **Step 1: Create TranscriptionEngine ABC in new file**

Создать `src/services/transcription_engines.py`:

```python
"""Transcription engine abstraction with Whisper and oMLX implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class TranscriptionEngine(ABC):
    """Abstract base class for transcription engines."""

    @abstractmethod
    def transcribe(self, file_path: str, **params) -> Dict[str, Any]:
        """
        Transcribe audio file. Returns normalized dict:
        {
            "segments": [{"id": int, "text": str, "start": float, "end": float, "speaker": int?}],
            "text": str,
            "speaker_detected": bool
        }
        """
        ...
```

- [ ] **Step 2: Extract WhisperEngine from transcribe_audio()**

В `src/models/transcription.py` перенести логику `transcribe_audio()` в класс `WhisperEngine`:

```python
class WhisperEngine(TranscriptionEngine):
    """MLX Whisper transcription engine."""

    def transcribe(self, file_path: str, **params) -> Dict[str, Any]:
        # ... current transcribe_audio() logic ...
        # Параметры: language, task, model, word_timestamps,
        #            condition_on_previous_text, no_speech_threshold,
        #            hallucination_silence_threshold, initial_prompt
        # Вернуть нормализованный формат с speaker_detected: False
```

Также оставить бэкенд-совместимость:
```python
# Legacy compatibility — для прямого вызова как функция
def transcribe_audio(file_path: str, **kwargs) -> Any:
    """Backward compatibility wrapper."""
    return WhisperEngine().transcribe(file_path, **kwargs)
```

- [ ] **Step 3: Test WhisperEngine transcribes**

```bash
python -c "from src.services.transcription_engines import WhisperEngine; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/services/transcription_engines.py src/models/transcription.py
git commit -m "refactor: create TranscriptionEngine ABC + WhisperEngine"
```

---

## Task 4: Create oMLXEngine

**Files:**
- Create: `src/services/omlx_engine.py`
- Modify: `src/services/transcription_engines.py` (import oMLXEngine)

- [ ] **Step 1: Create oMLXEngine**

Создать `src/services/omlx_engine.py`:

```python
"""oMLX transcription engine using oMLX API."""

import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from src.services.transcription_engines import TranscriptionEngine
from src.config import OMLX_BASE_URL, OMLX_MODEL, OMLX_API_KEY


def _get_audio_duration(file_path: str) -> float:
    """Get audio duration in seconds via ffprobe."""
    import subprocess
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return float(result.stdout.strip())


def _split_audio_by_silence(
    file_path: str,
    silence_threshold_db: int = 40,
    max_segment_sec: float = 50 * 60,
) -> List[Tuple[float, float]]:
    """
    Split audio by silence, return list of (start, end) time tuples.
    Uses librosa.effects.split + grouping with 2s gap threshold.
    """
    import librosa
    import pydub
    import pydub.utils

    audio = pydub.AudioSegment.from_file(file_path)
    samples = audio.get_array_of_samples()
    sr = audio.frame_rate

    # librosa expects numpy array
    import numpy as np
    samples_np = np.array(samples, dtype=np.float32)

    # Find speech intervals
    intervals = librosa.effects.split(samples_np, top_db=silence_threshold_db)

    # Group intervals with gaps < 2s
    grouped = []
    for start, end in intervals:
        start_sec = start / sr
        end_sec = end / sr
        if grouped and start_sec - grouped[-1][1] < 2.0:
            grouped[-1] = (grouped[-1][0], end_sec)
        else:
            grouped.append((start_sec, end_sec))

    # Split segments > max_segment_sec
    result = []
    for start, end in grouped:
        duration = end - start
        if duration <= max_segment_sec:
            result.append((start, end))
        else:
            # Sub-split
            t = start
            while t < end:
                seg_end = min(t + max_segment_sec, end)
                result.append((t, seg_end))
                t = seg_end
    return result


class oMLXEngine(TranscriptionEngine):
    """oMLX ASR transcription via oMLX API."""

    SILENCE_THRESHOLD_DB = 40
    MAX_SEGMENT_SEC = 50 * 60
    MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB

    def __init__(self) -> None:
        import requests
        self._requests = requests

    def _api_key_header(self) -> Dict[str, str]:
        if OMLX_API_KEY:
            return {"Authorization": f"Bearer {OMLX_API_KEY}"}
        return {}

    def _transcribe_segment(
        self, file_path: str, start: float, end: float, language: Optional[str]
    ) -> str:
        """Transcribe a single audio segment (start-end seconds) via oMLX API."""
        import tempfile
        import pydub

        # Extract segment
        audio = pydub.AudioSegment.from_file(file_path)
        segment = audio[start * 1000 : end * 1000]  # pydub uses ms

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            segment.export(tmp.name, format="wav")
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                files = {"file": (tmp_path.split("/")[-1], f, "audio/wav")}
                data = {"model": OMLX_MODEL}
                if language:
                    data["language"] = language

                headers = self._api_key_header()
                url = f"{OMLX_BASE_URL}/v1/audio/transcriptions"
                resp = self._requests.post(url, files=files, data=data, headers=headers)
                resp.raise_for_status()

            result = resp.json()
            # oMLX returns segments array with Start, End, Speaker, Content
            # or a simple text response
            if isinstance(result, dict) and "segments" in result:
                return result["segments"]
            elif isinstance(result, dict) and "text" in result:
                return [{"text": result["text"], "start": 0, "end": _get_audio_duration(file_path)}]
            else:
                # Fallback: parse raw text
                raw = result.get("text", str(result))
                return _parse_raw_text(raw, start)
        finally:
            os.unlink(tmp_path)

    def transcribe(self, file_path: str, **params) -> Dict[str, Any]:
        """Transcribe using oMLX/oMLX API."""
        language = params.get("language")

        # Check duration
        duration = _get_audio_duration(file_path)
        if duration <= self.MAX_SEGMENT_SEC:
            intervals = [(0, duration)]
        else:
            intervals = _split_audio_by_silence(
                file_path,
                silence_threshold_db=self.SILENCE_THRESHOLD_DB,
                max_segment_sec=self.MAX_SEGMENT_SEC,
            )

        # Transcribe each interval
        all_segments = []
        for start, end in intervals:
            try:
                seg_result = self._transcribe_segment(file_path, start, end, language)
                all_segments.extend(seg_result)
            except Exception as e:
                # Log error, continue with next segment
                import logging
                logging.getLogger(__name__).error(
                    f"oMLX segment transcription failed [{start:.1f}-{end:.1f}]: {e}"
                )
                continue

        # Normalize to unified format
        normalized_segments = []
        speaker_detected = False
        for i, seg in enumerate(all_segments):
            seg_dict = {}
            if isinstance(seg, dict):
                seg_dict = seg
                # Map oMLX format (Start, End, Speaker, Content)
                if "Start" in seg_dict:
                    seg_dict["start"] = seg_dict.pop("Start")
                if "End" in seg_dict:
                    seg_dict["end"] = seg_dict.pop("End")
                if "Speaker" in seg_dict:
                    seg_dict["speaker"] = seg_dict.pop("Speaker")
                    speaker_detected = True
                if "Content" in seg_dict:
                    seg_dict["text"] = seg_dict.pop("Content")
            else:
                # Fallback from _transcribe_segment
                if "text" in seg_dict:
                    text = seg_dict.get("text", "")
                    start = seg_dict.get("start", start)
                    end = seg_dict.get("end", end)
                    normalized_segments.append({
                        "id": i,
                        "text": text,
                        "start": start,
                        "end": end,
                    })
                    continue
            normalized_segments.append({
                "id": i,
                "text": seg_dict.get("text", ""),
                "start": seg_dict.get("start", 0),
                "end": seg_dict.get("end", 0),
                **({"speaker": seg_dict["speaker"]} if "speaker" in seg_dict else {}),
            })

        # Build full text
        full_text = " ".join(s["text"] for s in normalized_segments if s["text"])

        return {
            "segments": normalized_segments,
            "text": full_text,
            "speaker_detected": speaker_detected,
        }
```

Также добавить вспомогательную функцию `_parse_raw_text` для fallback парсинга.

- [ ] **Step 2: Import oMLXEngine in transcription_engines.py**

Добавить:
```python
from src.services.omlx_engine import oMLXEngine
```

- [ ] **Step 3: Test oMLXEngine imports**

```bash
python -c "from src.services.transcription_engines import oMLXEngine; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/services/omlx_engine.py src/services/transcription_engines.py
git commit -m "feat: add oMLXEngine for oMLX API transcription"
```

---

## Task 5: Modify TranscriptionQueueManager to use engines

**Files:**
- Modify: `src/services/transcription_queue.py`

- [ ] **Step 1: Update imports and engine resolution**

Заменить:
```python
import src.models.transcription as _transcription_module
```

На:
```python
from src.services.transcription_engines import WhisperEngine, oMLXEngine
```

В `TranscriptionQueueManager.__init__` добавить параметр `mechanism` и разрешить engine:
```python
def __init__(
    self,
    max_workers: int = 2,
    max_queue_size: int = 20,
    mechanism: str = "whisper",  # new parameter
):
    self._engine = WhisperEngine() if mechanism == "omlx" else WhisperEngine()
```

- [ ] **Step 2: Update worker to use engine**

Заменить прямой вызов `_transcription_module.transcribe_audio()` на:
```python
result = self._engine.transcribe(wav_path, **params)
```

- [ ] **Step 3: Update TranscriptionService.submit() to pass mechanism**

В `src/services/transcription_service.py` добавить параметр `mechanism` в `submit()` и передать в queue:
```python
def submit(..., mechanism: str = "whisper") -> ...:
    payload["mechanism"] = mechanism
```

- [ ] **Step 4: Test imports work**

```bash
python -c "from src.services.transcription_queue import TranscriptionQueueManager; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add src/services/transcription_queue.py src/services/transcription_service.py
git commit -m "refactor: use engine abstraction in TranscriptionQueueManager"
```

---

## Task 6: Modify POST /api/v1/transcribe for mechanism

**Files:**
- Modify: `src/api/router.py:110-231`

- [ ] **Step 1: Add mechanism Form parameter**

Добавить в `POST /api/v1/transcribe` Form:
```python
mechanism: str = Form("whisper"),
```

Сразу после `file`:
```python
file: UploadFile = File(...),
mechanism: str = Form("whisper"),
```

Валидация:
```python
if mechanism not in ("whisper", "omlx"):
    raise HTTPException(status_code=400, detail="Invalid mechanism. Must be 'whisper' or 'omlx'.")
```

- [ ] **Step 2: Pass mechanism through the service layer**

Изменить вызов `transcription_service.submit()`:
```python
job_id, success = transcription_service.submit(
    ...,
    mechanism=mechanism,
)
```

- [ ] **Step 3: Update queue creation with mechanism**

При submit проверить `mechanism == "omlx"` и пересоздать TranscriptionQueueManager с нужным mechanism, либо использовать module-level паттерн:
```python
if mechanism == "omlx":
    TranscriptionQueueManager._instance = None  # force reinit
    qm = TranscriptionQueueManager(mechanism="omlx")
else:
    qm = TranscriptionQueueManager(mechanism="whisper")
```

Или лучше — создать queue manager с engine на уровне сервиса:
```python
engine = oMLXEngine() if mechanism == "omlx" else WhisperEngine()
transcription_service = TranscriptionService(qm, jm, engine)
```

- [ ] **Step 4: Commit**

```bash
git add src/api/router.py
git commit -m "feat: add mechanism parameter to POST /api/v1/transcribe"
```

---

## Task 7: Add GET /api/v1/omlx/health endpoint

**Files:**
- Modify: `src/api/router.py`

- [ ] **Step 1: Add health check endpoint**

```python
@router.get("/omlx/health")
async def omlx_health() -> Dict[str, Any]:
    """Check oMLX connection health."""
    from src.config import OMLX_BASE_URL, OMLX_ENABLED
    import requests

    if not OMLX_ENABLED or not OMLX_BASE_URL:
        return {"available": False, "error": "oMLX not enabled or configured"}

    try:
        resp = requests.get(f"{OMLX_BASE_URL}/v1/models", timeout=10)
        if resp.status_code == 200:
            return {"available": True}
        else:
            return {"available": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"available": False, "error": str(e)}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/router.py
git commit -m "feat: add GET /api/v1/omlx/health endpoint"
```

---

## Task 8: Extend GET /api/v1/config

**Files:**
- Modify: `src/api/router.py:240-263`

- [ ] **Step 1: Add omlx fields to config response**

В `GET /api/v1/config` добавить:
```python
from src.config import OMLX_ENABLED, omlx_available

config["omlx_enabled"] = OMLX_ENABLED
config["omlx_available"] = omlx_available()
```

- [ ] **Step 2: Commit**

```bash
git add src/api/router.py
git commit -m "feat: extend config with omlx_enabled and omlx_available"
```

---

## Task 9: Add mechanism select to uploads.html + show/hide logic

**Files:**
- Modify: `src/templates/uploads.html`

- [ ] **Step 1: Add mechanism select dropdown**

Добавить select сразу после `file` input (или в начале формы):
```html
<div class="form-group">
    <label for="mechanism">Transcription Mechanism:</label>
    <select id="mechanism" name="mechanism">
        <option value="whisper" selected>Whisper (MLX)</option>
        <option value="omlx">oMLX (oMLX)</option>
    </select>
</div>
```

- [ ] **Step 2: Add show/hide JavaScript logic**

В `loadConfig()`:
```javascript
function loadConfig() {
    fetch('/api/v1/config')
        .then(r => r.json())
        .then(config => {
            // ...existing code...

            // Configure mechanism selector
            const mechanismSelect = document.getElementById('mechanism');
            const whisperAccordion = document.getElementById('whisper-params-accordion');

            if (!config.omlx_enabled) {
                // oMLX not available — disable select, force Whisper
                const omlxOption = mechanismSelect.querySelector('[value="omlx"]');
                if (omlxOption) omlxOption.disabled = true;
                mechanismSelect.value = 'whisper';
            }

            if (!config.omlx_available) {
                // oMLX not configured — disable oMLX option
                const omlxOption = mechanismSelect.querySelector('[value="omlx"]');
                if (omlxOption) omlxOption.disabled = true;
            }

            // Mechanism change handler
            mechanismSelect.addEventListener('change', function() {
                const isWhisper = this.value === 'whisper';
                whisperAccordion.style.display = isWhisper ? 'block' : 'none';

                // Disable/enable mechanism select if oMLX unavailable
                if (!config.omlx_available) {
                    this.value = 'whisper';
                }
            });

            // Initial state
            mechanismSelect.dispatchEvent(new Event('change'));
        });
}
```

- [ ] **Step 3: Include mechanism in form submission**

В `submitUpload()`:
```javascript
formData.append('mechanism', document.getElementById('mechanism').value);
```

- [ ] **Step 4: Commit**

```bash
git add src/templates/uploads.html
git commit -m "feat: add mechanism select to uploads.html with show/hide logic"
```

---

## Task 10: Add CSS for mechanism selector

**Files:**
- Modify: `src/static/new_style.css`

- [ ] **Step 1: Add styles for mechanism select**

```css
select[name="mechanism"],
#mechanism {
    width: 100%;
    padding: 10px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 15px;
    transition: border-color 0.2s ease;
}

select[name="mechanism"]:focus,
#mechanism:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

select[name="mechanism"]:disabled,
#mechanism:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/new_style.css
git commit -m "style: add CSS for mechanism selector dropdown"
```

---

## Task 11: Write tests

**Files:**
- Create: `tests/test_transcription_engines.py`
- Create: `tests/test_omlx_health.py`
- Create: `tests/test_omlx_engine.py` (optional, skip if no oMLX server)

- [ ] **Step 1: Test TranscriptionEngine ABC and WhisperEngine import**

Создать `tests/test_transcription_engines.py`:
```python
"""Tests for TranscriptionEngine ABC and WhisperEngine."""

import pytest

from src.services.transcription_engines import (
    TranscriptionEngine,
    WhisperEngine,
)


def test_whisper_engine_is_transcription_engine():
    """WhisperEngine should be a subclass of TranscriptionEngine."""
    assert issubclass(WhisperEngine, TranscriptionEngine)
    engine = WhisperEngine()
    assert isinstance(engine, TranscriptionEngine)


def test_transcription_engine_cannot_be_instantiated():
    """TranscriptionEngine ABC cannot be instantiated directly."""
    with pytest.raises(TypeError):
        TranscriptionEngine()
```

- [ ] **Step 2: Test config variables**

Добавить в тесты:
```python
from src.config import OMLX_BASE_URL, OMLX_ENABLED, OMLX_MODEL, omlx_available


def test_omlx_config_variables_exist():
    assert hasattr(__import__("src.config", fromlist=["OMLX_BASE_URL"]), "OMLX_BASE_URL")
    assert hasattr(__import__("src.config", fromlist=["OMLX_ENABLED"]), "OMLX_ENABLED")
    assert hasattr(__import__("src.config", fromlist=["OMLX_MODEL"]), "OMLX_MODEL")
    assert callable(omlx_available)


def test_omlx_available_without_config():
    """Without OMLX_BASE_URL, omlx_available should return False."""
    assert omlx_available() is False
```

- [ ] **Step 3: Run all tests**

```bash
pytest tests/test_transcription_engines.py -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_transcription_engines.py
git commit -m "test: add tests for TranscriptionEngine ABC and WhisperEngine"
```

---

## Task 12: Integration test — existing Whisper path still works

**Files:**
- Modify: `tests/test_transcription_engines.py` (add)

- [ ] **Step 1: Add integration test for WhisperEngine.transcribe()**

```python
import os
import tempfile

import pytest
from src.services.transcription_engines import WhisperEngine


@pytest.mark.skipif(
    not os.path.exists(os.path.join("tests", "test_audio.wav")),
    reason="No test audio file available"
)
def test_whisper_engine_transcribe_small_file():
    """WhisperEngine should transcribe a small audio file and return normalized result."""
    engine = WhisperEngine()
    result = engine.transcribe(
        os.path.join("tests", "test_audio.wav"),
        language="en",
        task="transcribe",
        model="tiny",
    )

    assert "segments" in result
    assert "text" in result
    assert "speaker_detected" in result
    assert isinstance(result["segments"], list)
    assert isinstance(result["text"], str)
    assert isinstance(result["speaker_detected"], bool)
    assert result["speaker_detected"] is False  # Whisper doesn't detect speakers
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_transcription_engines.py
git commit -m "test: add integration test for WhisperEngine.transcribe()"
```

---

## Verification

1. **Install deps**: `pip install librosa pydub requests`
2. **Run app**: `source .venv/bin/activate && python src/main.py`
3. **Check UI**: Open uploads page, verify mechanism select shows Whisper (MLX) / oMLX (oMLX)
4. **Test Whisper**: Upload audio with Whisper — should work as before
5. **Test oMLX**: Switch to oMLX, upload audio — should transcribe via oMLX
6. **Test health endpoint**: `curl http://localhost:8000/api/v1/omlx/health`
7. **Test config**: `curl http://localhost:8000/api/v1/config` — should include `omlx_enabled` and `omlx_available`
8. **Run tests**: `pytest tests/ -v` — all existing tests pass

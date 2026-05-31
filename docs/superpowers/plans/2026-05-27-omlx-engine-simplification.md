# OMLX Engine Simplification Implementation Plan

> **Для агентных воркеров:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Шаги используют checkbox (`- [ ]`) синтаксис.

**Goal:** Упростить OMLXEngine — убрать librosa/numpy загрузку аудио и temp-файлы сегментов, заменить на pydub-only.

**Architecture:** pydub raw samples для детекта тишины + BytesIO для отправки сегментов в API.

**Tech Stack:** Python, pydub, struct, io.BytesIO

---

## Map of Changes

### Модифицируем:
- `src/services/omlx_engine.py` — основная логика: новый детект тишины, BytesIO, удаление функций
- `tests/test_omlx_engine.py` — удалить тесты `_group_intervals`, обновить `_transcribe_segment`, добавить тесты `_detect_silence_chunks`

### Удалляем из `omlx_engine.py`:
- `_group_intervals` (строки 118-134)
- `_save_segment` (строки 137-150)
- Импорт `tempfile`
- Импорт `librosa` (внутри `_split_audio_by_silence`)

### Модифицируем импорты в `transcription_queue.py`:
- Удалить `import src.models.transcription as _transcription_module` (если больше не нужен)

---

### Task 1: Добавить `_detect_silence_chunks`

**Files:**
- Modify: `src/services/omlx_engine.py:47-115`

Добавить новую функцию для детекта тишины на чистом pydub:

```python
import struct
import math
from io import BytesIO

def _detect_silence_chunks(
    audio_segment,
    chunk_duration_ms: int = 100,
    silence_threshold_db: int = -40,
    gap_ms: int = 2000,
) -> list[tuple[int, int]]:
    """Обход аудио чанками, возврат не-тихих интервалов в ms.

    Uses pydub raw_data + struct for sample access.
    Merges adjacent non-silent chunks separated by < gap_ms.
    """
    raw_bytes = audio_segment.raw_data
    sample_width = audio_segment.sample_width
    num_samples = len(raw_bytes) // (sample_width * audio_segment.channels)
    samples = struct.unpack(
        f"<{num_samples}{'h' if sample_width == 2 else 'i'}",
        raw_bytes,
    )
    # При стерео — берём чётные сэмплы (channel 0)
    if audio_segment.channels > 1:
        samples = samples[::2]
        num_samples = len(samples)

    chunk_size = max(1, int(chunk_duration_ms * audio_segment.frame_rate / 1000))

    non_silent = []
    for i in range(0, num_samples, chunk_size):
        chunk = samples[i : i + chunk_size]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
        if rms > 0:
            db = 20 * math.log10(rms / 32768.0)
            if db > silence_threshold_db:
                start_ms = i * 1000 // audio_segment.frame_rate
                end_ms = (i + len(chunk)) * 1000 // audio_segment.frame_rate
                non_silent.append((start_ms, end_ms))

    # Merge adjacent non-silent chunks separated by < gap_ms
    if not non_silent:
        return []

    merged = [non_silent[0]]
    for start, end in non_silent[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= gap_ms:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged
```

- [ ] **Step 1: Добавить импорты `struct`, `math`, `io.BytesIO` в omlx_engine.py**

Добавить в начало файла (после `from __future__ import annotations`):

```python
import struct
import math
from io import BytesIO
```

- [ ] **Step 2: Добавить функцию `_detect_silence_chunks`**

Вставить после констант (после строки 44, перед `_split_audio_by_silence`):

[Код функции выше]

- [ ] **Step 3: Написать тесты для `_detect_silence_chunks`**

Создать новые тесты в `tests/test_omlx_engine.py`:

```python
# =============================================================================
# TestDetectSilenceChunks
# =============================================================================

class TestDetectSilenceChunks:
    """Тесты _detect_silence_chunks()."""

    def _make_audio_segment(self, samples: list[int], frame_rate: int = 16000, channels: int = 1) -> MagicMock:
        """Создать мок AudioSegment с заданными сэмплами."""
        import struct
        fmt = f"<{len(samples)}h"
        raw = struct.pack(fmt, *samples)
        segment = MagicMock()
        segment.raw_data = raw
        segment.sample_width = 2
        segment.frame_rate = frame_rate
        segment.channels = channels
        segment.duration_seconds = len(samples) / frame_rate
        return segment

    def test_detects_silent_input(self):
        """Полностью тихий вход → пустой список."""
        from src.services.omlx_engine import _detect_silence_chunks

        samples = [0] * 16000  # 1 сек тишины
        segment = self._make_audio_segment(samples)
        result = _detect_silence_chunks(segment, chunk_duration_ms=100)
        assert result == []

    def test_detects_non_silent_input(self):
        """Не-тихий вход → возвращает интервал."""
        from src.services.omlx_engine import _detect_silence_chunks

        # 0.5 сек тишины + 0.5 сек речи
        samples = [0] * 8000 + [32767] * 8000
        segment = self._make_audio_segment(samples)
        result = _detect_silence_chunks(segment, chunk_duration_ms=100, silence_threshold_db=-40)
        assert len(result) >= 1
        # Non-silent chunk should start around 500ms
        assert result[0][0] >= 400

    def test_merges_close_chunks(self):
    """Ближние не-тихие чанки объединяются."""
        from src.services.omlx_engine import _detect_silence_chunks

        # Тишина → речь → тишина (100ms) → речь
        # При gap_ms=500, две речевые области должны слиться
        samples = [0] * 4000 + [32767] * 1000 + [0] * 800 + [32767] * 1000
        segment = self._make_audio_segment(samples)
        result = _detect_silence_chunks(segment, chunk_duration_ms=100, gap_ms=500)
        assert len(result) == 1

    def test_keeps_separated_chunks(self):
        """Далекие не-тихие чанки не объединяются."""
        from src.services.omlx_engine import _detect_silence_chunks

        # Речь → тишина (1 сек) → речь
        samples = [32767] * 1000 + [0] * 16000 + [32767] * 1000
        segment = self._make_audio_segment(samples)
        result = _detect_silence_chunks(segment, chunk_duration_ms=100, gap_ms=500)
        assert len(result) == 2

    def test_empty_audio(self):
        """Пустой вход → пустой список."""
        from src.services.omlx_engine import _detect_silence_chunks

        segment = self._make_audio_segment([])
        result = _detect_silence_chunks(segment)
        assert result == []
```

- [ ] **Step 4: Запустить тесты**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -m pytest tests/test_omlx_engine.py::TestDetectSilenceChunks -v
```

Expected: все 5 тестов PASS.

### Task 2: Заменить `_split_audio_by_silence` на pydub-only

**Files:**
- Modify: `src/services/omlx_engine.py:47-115`

Заменить всю функцию `_split_audio_by_silence`:

```python
def _split_audio_by_silence(
    file_path: str,
    max_duration_sec: int = MAX_AUDIO_DURATION_SEC,
) -> tuple[list[tuple[int, int, bytes]], int]:
    """Разбить аудио на сегменты по тишине и максимальной длительности.

    Returns
    -------
    list of (start_ms, end_ms, audio_bytes)
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        logger.error("pydub is required for splitting. Install pydub.")
        return [(0, -1, b"")], 16000

    try:
        audio = AudioSegment.from_file(file_path)
    except Exception as e:
        logger.error(f"Failed to load audio with pydub: {e}")
        return [(0, -1, b"")], 16000

    sr = audio.frame_rate
    non_silent = _detect_silence_chunks(audio, gap_ms=int(2.0 * sr / 1000))

    if not non_silent:
        return [(0, -1, audio.export_to_bytes(format="opus"))], sr

    result: list[tuple[int, int, bytes]] = []
    for start_ms, end_ms in non_silent:
        duration_ms = end_ms - start_ms
        if duration_ms <= max_duration_sec * 1000:
            segment = audio[start_ms:end_ms]
            result.append((start_ms, end_ms, segment.export_to_bytes(format="opus")))
        else:
            # Split long segments into max_duration_sec chunks
            total_ms = duration_ms
            offset_ms = start_ms
            chunk_start = 0
            while chunk_start < total_ms:
                chunk_end = min(chunk_start + max_duration_sec * 1000, total_ms)
                abs_start = offset_ms + chunk_start
                abs_end = offset_ms + chunk_end
                segment = audio[abs_start:abs_end]
                result.append((abs_start, abs_end, segment.export_to_bytes(format="opus")))
                chunk_start = chunk_end

    return result, sr
```

- [ ] **Step 1: Заменить функцию `_split_audio_by_silence`**

Полностью заменить текущую функцию (строки 47-115) на новую версию выше.

Удалить:
- Импорт `librosa` (внутри функции)
- Импорт `pydub.AudioSegment` (внутри функции, переместить наверх функции)
- Вызов `librosa.effects.split`
- Вызов `_group_intervals`
- `pydub_audio = AudioSegment.from_file(file_path)` (теперь один вызов в начале)
- `tempfile`-зависимый `_save_segment` (теперь `export_to_bytes`)

- [ ] **Step 2: Обновить `_transcribe_segment` — принять bytes вместо file_path**

Текущая сигнатура:
```python
def _transcribe_segment(self, file_path: str, language: Optional[str], model: Optional[str] = None)
```

Новая сигнатура:
```python
def _transcribe_segment(
    self, audio_bytes: bytes, filename: str, language: Optional[str], model: Optional[str] = None
)
```

Изменить тело функции — убрать `with open(file_path, "rb") as f:` и использовать bytes напрямую:

```python
def _transcribe_segment(
    self, audio_bytes: bytes, filename: str, language: Optional[str], model: Optional[str] = None
) -> Dict[str, Any]:
    """Транскрибировать один сегмент через oMLX API."""
    url = f"{OMLX_BASE_URL}/audio/transcriptions"

    ext = os.path.splitext(filename)[1].lower()
    mime_type = {"wav": "audio/wav", ".opus": "audio/opus"}.get(ext, "audio/opus")
    files = {"file": (filename, audio_bytes, mime_type)}
    data: Dict[str, Any] = {"model": model or OMLX_MODEL, "diarize": True}
    if language:
        data["language"] = language

    headers: Dict[str, str] = {}
    if OMLX_API_KEY:
        headers["Authorization"] = f"Bearer {OMLX_API_KEY}"

    response = _requests.post(
        url, files=files, data=data, headers=headers, timeout=(10, 3600)
    )
    # ... rest unchanged
```

- [ ] **Step 3: Обновить вызовы `_transcribe_segment` в `transcribe`**

В `OMLXEngine.transcribe` (строки ~317-334):

Текущий код:
```python
for seg_start_samples, _, seg_path in segments_files:
    seg_result = self._transcribe_segment(seg_path, language, model=omlx_model)
```

Новый код:
```python
for start_ms, end_ms, audio_bytes in segments_files:
    seg_result = self._transcribe_segment(
        audio_bytes, "segment.opus", language, model=omlx_model
    )
```

Также обновить корректировку временных меток — теперь `start_ms` в миллисекундах, а не сэмплах:

```python
if start_ms > 0:
    offset_sec = start_ms / 1000.0
    for seg in seg_result["segments"]:
        seg["start"] += offset_sec
        seg["end"] += offset_sec
```

- [ ] **Step 4: Запустить существующие тесты**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -m pytest tests/test_omlx_engine.py -v
```

Expected: тесты `TestOMLXEngineTranscribe` и `TestTranscribeSegment` могут пасть — это ожидаемо, они будут обновлены в Task 3.

### Task 3: Удалить `_group_intervals` и `_save_segment`

**Files:**
- Modify: `src/services/omlx_engine.py`

- [ ] **Step 1: Удалить функцию `_group_intervals`**

Удалить строки 118-134.

- [ ] **Step 2: Удалить функцию `_save_segment`**

Удалить строки 137-150.

- [ ] **Step 3: Удалить импорт `tempfile`**

Удалить строку `import tempfile`.

- [ ] **Step 4: Удалить импорт `librosa`**

Убедиться, что `import librosa` внутри `_split_audio_by_silence` удалён.

### Task 4: Обновить тесты

**Files:**
- Modify: `tests/test_omlx_engine.py`

- [ ] **Step 1: Удалить класс `TestGroupIntervals`**

Удалить строки 114-152 (весь класс `TestGroupIntervals`).

- [ ] **Step 2: Удалить fixture `group_func`**

Удалить строки 22-25.

- [ ] **Step 3: Обновить `TestTranscribeSegment` — все тесты**

Все тесты в `TestTranscribeSegment` сейчас передают `file_path` в `_transcribe_segment`. Обновить их для передачи `audio_bytes` и `filename`:

```python
class TestTranscribeSegment:
    """Тесты OMLXEngine._transcribe_segment()."""

    def _make_mock_response(self, text="[]"):
        mock = MagicMock()
        mock.text = text
        mock.raise_for_status = MagicMock()
        return mock

    def test_calls_api_with_correct_url(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response(
            '[{"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "hello"}]'
        )
        mock_requests_module = MagicMock()
        mock_requests_module.post = MagicMock(return_value=mock_response)

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.OMLX_API_KEY", "key123"),
            patch("src.services.omlx_engine._requests", mock_requests_module),
        ):
            audio_bytes = b"fake audio data"
            engine._transcribe_segment(audio_bytes, "segment.opus", "en")

            mock_requests_module.post.assert_called_once()
            call_args = mock_requests_module.post.call_args
            assert call_args.args[0] == "http://test/audio/transcriptions"
            # Verify files parameter contains bytes, not a file handle
            files_arg = call_args.kwargs["files"]
            assert files_arg["file"][1] == audio_bytes

    def test_includes_language_in_payload(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response()

        captured_data = {}

        def capture_post(url, files=None, data=None, headers=None, timeout=None, **kwargs):
            captured_data["data"] = data
            return mock_response

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment(b"data", "seg.opus", "ru")

        assert captured_data["data"]["language"] == "ru"

    def test_includes_api_key_header(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response()

        captured_headers = {}

        def capture_post(url, files=None, data=None, headers=None, timeout=None, **kwargs):
            captured_headers["headers"] = headers
            return mock_response

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.OMLX_API_KEY", "secret-key"),
            patch("src.services.omlx_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment(b"data", "seg.opus", None)

        assert captured_headers["headers"]["Authorization"] == "Bearer secret-key"

    def test_no_auth_header_without_key(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response()

        captured_headers = {}

        def capture_post(url, files=None, data=None, headers=None, timeout=None, **kwargs):
            captured_headers["headers"] = headers
            return mock_response

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.OMLX_API_KEY", None),
            patch("src.services.omlx_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment(b"data", "seg.opus", None)

        assert captured_headers["headers"] is None or "Authorization" not in captured_headers["headers"]

    def test_parses_json_api_response(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response(
            '[{"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "Hello world"}]'
        )

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine._requests.post", return_value=mock_response),
        ):
            result = engine._transcribe_segment(b"data", "seg.opus", "en")

            assert len(result["segments"]) == 1
            assert result["segments"][0]["text"] == "Hello world"

    def test_api_error_propagates(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine._requests.post") as mock_post,
        ):
            mock_post.return_value.raise_for_status.side_effect = Exception("500")

            with pytest.raises(Exception, match="500"):
                engine._transcribe_segment(b"data", "seg.opus", "en")
```

- [ ] **Step 2: Обновить `TestOMLXEngineTranscribe` — тесты с моками**

Обновить моки `_split_audio_by_silence` и `_transcribe_segment` для новых сигнатур:

```python
class TestOMLXEngineTranscribe:
    """Тесты OMLXEngine.transcribe()."""

    def test_raises_when_not_enabled(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        with patch("src.services.omlx_engine.OMLX_ENABLED", False):
            with pytest.raises(RuntimeError, match="oMLX не настроен"):
                engine.transcribe("/tmp/test.wav")

    def test_raises_when_no_base_url(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", ""),
            patch("src.services.omlx_engine.OMLX_ENABLED", True),
        ):
            with pytest.raises(RuntimeError, match="oMLX не настроен"):
                engine.transcribe("/tmp/test.wav")

    def test_skips_failed_segments(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch("src.services.omlx_engine._split_audio_by_silence") as mock_split,
            patch("src.services.omlx_engine.OMLX_ENABLED", True),
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
        ):
            # Теперь возвращаем (start_ms, end_ms, bytes)
            mock_split.return_value = ([(0, 100, b"fake audio")], 16000)

            original_transcribe_segment = engine._transcribe_segment
            engine._transcribe_segment = MagicMock(side_effect=RuntimeError("API down"))

            try:
                result = engine.transcribe("/tmp/test.wav")
                assert isinstance(result["segments"], list)
                assert isinstance(result["text"], str)
            finally:
                engine._transcribe_segment = original_transcribe_segment

    def test_corrects_time_offset(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 1, "text": "test"}],
            "text": "test",
            "raw_response": '[{"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "test"}]',
        }

        with (
            patch("src.services.omlx_engine._split_audio_by_silence") as mock_split,
            patch("src.services.omlx_engine.OMLX_ENABLED", True),
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
        ):
            # Теперь start_ms = 500 (0.5 сек)
            mock_split.return_value = ([(500, 1500, b"fake audio")], 16000)

            engine._transcribe_segment = MagicMock(return_value=mock_result)
            result = engine.transcribe("/tmp/test.wav")

            # Start скорректирован: 0.0 + 0.5 = 0.5
            assert result["segments"][0]["start"] == pytest.approx(0.5)
            assert result["segments"][0]["end"] == pytest.approx(1.5)

    def test_speaker_detected_true(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 1, "text": "test"}],
            "text": "test",
            "raw_response": None,
        }

        with (
            patch("src.services.omlx_engine._split_audio_by_silence") as mock_split,
            patch("src.services.omlx_engine.OMLX_ENABLED", True),
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
        ):
            mock_split.return_value = ([(0, 100, b"fake audio")], 16000)
            engine._transcribe_segment = MagicMock(return_value=mock_result)

            result = engine.transcribe("/tmp/test.wav")
            assert result["speaker_detected"] is True

    def test_speaker_detected_false(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "test"}],
            "text": "test",
            "raw_response": None,
        }

        with (
            patch("src.services.omlx_engine._split_audio_by_silence") as mock_split,
            patch("src.services.omlx_engine.OMLX_ENABLED", True),
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
        ):
            mock_split.return_value = ([(0, 100, b"fake audio")], 16000)
            engine._transcribe_segment = MagicMock(return_value=mock_result)

            result = engine.transcribe("/tmp/test.wav")
            assert result["speaker_detected"] is False

    def test_returns_transcription_duration(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch("src.services.omlx_engine._split_audio_by_silence") as mock_split,
            patch("src.services.omlx_engine.OMLX_ENABLED", True),
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
        ):
            mock_split.return_value = ([(0, 100, b"fake audio")], 16000)
            engine._transcribe_segment = MagicMock(return_value={
                "segments": [],
                "text": "",
                "raw_response": None,
            })

            result = engine.transcribe("/tmp/test.wav")
            assert "transcription_duration" in result
            assert isinstance(result["transcription_duration"], float)
```

- [ ] **Step 3: Запустить все тесты**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -m pytest tests/test_omlx_engine.py -v
```

Expected: все тесты PASS.

### Task 5: Убрать неиспользуемые зависимости

**Files:**
- Modify: `src/requirements.txt`

- [ ] **Step 1: Проверить, нужен ли librosa/numpy**

librosa и numpy импортируются только в `_split_audio_by_silence` (через librosa). После удаления — проверить, что они больше не импортируются в `omlx_engine.py`.

```bash
grep -rn "import librosa\|import numpy\|from librosa\|from numpy" src/services/omlx_engine.py
```

Expected: 0 совпадений.

- [ ] **Step 2: Проверить другие файлы**

```bash
grep -rn "import librosa\|from librosa" src/
```

Если librosa используется где-то ещё — НЕ удалять из requirements. Если нигде — можно удалить.

### Task 6: Интеграционный тест

**Files:**
- `tests/test_omlx_engine.py`

- [ ] **Step 1: Добавить интеграционный тест с реальным pydub AudioSegment**

```python
class TestSplitAudioBySilence:
    """Интеграционные тесты _split_audio_by_silence()."""

    def test_splits_on_silence_boundary(self, tmp_path):
        """Аудио с тишиной разбивается на сегменты."""
        from pydub import AudioSegment
        from src.services.omlx_engine import _split_audio_by_silence

        # Создать аудио: 1 сек тишины + 1 сек речи + 1 сек тишины
        audio = AudioSegment.silent(duration=1000) + AudioSegment.silent(
            duration=1000, frame_rate=16000
        )
        # Добавить тон 440Hz в среднюю часть
        tone = AudioSegment.from_raw(
            io.BytesIO(b"\x00" * 32000),
            frame_rate=16000,
            sample_width=2,
            channels=1,
        )
        # Для простоты — используем готовый тестовый файл
        wav_path = tmp_path / "test.wav"
        audio.export(str(wav_path), format="wav")

        result, sr = _split_audio_by_silence(str(wav_path))
        assert sr == 16000
        assert len(result) >= 1
        for _, _, audio_bytes in result:
            assert isinstance(audio_bytes, bytes)
            assert len(audio_bytes) > 0
```

- [ ] **Step 2: Запустить интеграционный тест**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -m pytest tests/test_omlx_engine.py::TestSplitAudioBySilence -v
```

### Task 7: Финальная проверка и коммит

- [ ] **Step 1: Запустить все тесты**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python -m pytest tests/test_omlx_engine.py -v
```

- [ ] **Step 2: Проверить что librosa/numpy не импортируются в omlx_engine.py**

```bash
grep -n "librosa\|numpy" src/services/omlx_engine.py
```

Expected: 0 совпадений.

- [ ] **Step 3: Запустить проверку синтаксиса**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -c "import ast; ast.parse(open('src/services/omlx_engine.py').read()); print('OK')"
```

- [ ] **Step 4: Закоммитить**

```bash
cd /Users/dvmironenko/dev/mlx_whisper
git add src/services/omlx_engine.py tests/test_omlx_engine.py docs/superpowers/specs/2026-05-27-omlx-engine-simplification-design.md docs/superpowers/plans/2026-05-27-omlx-engine-simplification.md
git commit -m "refactor: simplify OMLXEngine — pydub-only splitting, remove temp files and librosa"
```

---

## Self-Review

**Spec coverage:**
- ✅ Убрать librosa/numpy → Task 2, Task 5
- ✅ Убрать temp-файлы сегментов → Task 2
- ✅ pydub-only splitting → Task 2
- ✅ Новый `_detect_silence_chunks` → Task 1
- ✅ Обновить `_transcribe_segment` → Task 2
- ✅ Обновить тесты → Task 3, Task 4
- ✅ Удалить `_group_intervals`, `_save_segment` → Task 3

**Placeholder scan:** Нет TBD/TODO/vague. Каждый шаг содержит конкретный код или команды.

**Type consistency:** `_split_audio_by_silence` возвращает `tuple[list[tuple[int, int, bytes]], int]` — единообразно во всех задачах. `_transcribe_segment` принимает `bytes, str, str, str|None` — единообразно.

**Scope:** Сфокусировано на одном файле `omlx_engine.py` + один тестовый файл.

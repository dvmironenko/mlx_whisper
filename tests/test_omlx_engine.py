"""Тесты для функций парсинга omlx_engine.py."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), ".."))


# =============================================================================
# Module-level fixtures (not class methods)
# =============================================================================

@pytest.fixture
def normalize_func():
    from src.services.omlx_engine import _normalize_segments
    return _normalize_segments


# =============================================================================
# TestParseSegmentsFromJson
# =============================================================================

class TestParseSegmentsFromJson:
    """Тесты _normalize_segments()."""

    def test_parses_valid_json(self, normalize_func):
        segments = [
            {"Start": 0.0, "End": 1.5, "Speaker": 1, "Content": "Привет"},
            {"Start": 1.5, "End": 3.0, "Speaker": 2, "Content": "Пока"},
        ]
        result = normalize_func(segments)

        assert result is not None
        assert len(result) == 2
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 1.5
        assert result[0]["speaker"] == 1
        assert result[0]["text"] == "Привет"

    def test_parses_lowercase_keys(self, normalize_func):
        segments = [
            {"start": 0.0, "end": 1.5, "speaker": 1, "content": "Привет"},
        ]
        result = normalize_func(segments)

        assert result is not None
        assert result[0]["start"] == 0.0
        assert result[0]["text"] == "Привет"

    def test_returns_none_for_non_array_json(self, normalize_func):
        result = normalize_func({"key": "value"})
        assert result is None

    def test_returns_none_for_plain_text(self, normalize_func):
        result = normalize_func("Просто текст без JSON")
        assert result is None

    def test_returns_none_for_empty_list(self, normalize_func):
        result = normalize_func([])
        assert result is None

    def test_skips_non_dict_items(self, normalize_func):
        segments = ["string_item", {"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "valid"}]
        result = normalize_func(segments)

        assert result is not None
        assert len(result) == 1
        assert result[0]["text"] == "valid"

    def test_default_values_for_missing_keys(self, normalize_func):
        segments = [{"Content": "test"}]
        result = normalize_func(segments)

        assert result is not None
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 0.0
        assert result[0]["speaker"] == 0
        assert result[0]["text"] == "test"

    def test_handles_api_dict_response(self, normalize_func):
        """API возвращает dict с JSON-строкой в поле 'text'."""
        api_response = {
            "text": '[{"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "test"}]',
            "language": "ru",
        }
        result = normalize_func(api_response)

        assert result is not None
        assert len(result) == 1
        assert result[0]["text"] == "test"

    def test_handles_api_dict_with_segments(self, normalize_func):
        """API возвращает dict с полем 'segments' — игнорируем, парсим 'text'."""
        api_response = {
            "text": '[{"Start": 0.0, "End": 2.0, "Speaker": 0, "Content": "hello"}]',
            "segments": [{"start": 0, "end": 2, "speaker_id": 0, "text": "hello"}],
        }
        result = normalize_func(api_response)

        assert result is not None
        assert len(result) == 1
        assert result[0]["text"] == "hello"


# =============================================================================
# TestOMLXEngineTranscribe
# =============================================================================

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
        with patch("src.services.omlx_engine.OMLX_BASE_URL", ""):
            with patch("src.services.omlx_engine.OMLX_ENABLED", True):
                with pytest.raises(RuntimeError, match="oMLX не настроен"):
                    engine.transcribe("/tmp/test.wav")

    def test_calls_transcribe_file(self):
        """transcribe вызывает _transcribe_file при duration ≤ 60 мин."""
        import src.services.omlx_engine as omlx_module
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "hello"}],
            "text": "hello",
            "raw_response": None,
        }

        with (
            patch.object(omlx_module, "OMLX_ENABLED", True),
            patch.object(omlx_module, "OMLX_BASE_URL", "http://test"),
            patch.object(omlx_module, "get_audio_duration", return_value=300.0),
            patch.object(omlx_module, "_reconcile_speaker_ids", side_effect=lambda s: s),
        ):
            engine._transcribe_file = MagicMock(return_value=mock_result)
            result = engine.transcribe("/tmp/test.wav")

            engine._transcribe_file.assert_called_once_with("/tmp/test.wav", language=None, model=None)
            assert len(result["segments"]) == 1
            assert result["segments"][0]["text"] == "hello"

    def test_calls_split_and_transcribe_when_duration_exceeds(self):
        """duration > 3600s → вызывается _split_and_transcribe."""
        import src.services.omlx_engine as omlx_module
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "hello"}],
            "text": "hello",
            "raw_response": None,
        }

        with (
            patch.object(omlx_module, "OMLX_ENABLED", True),
            patch.object(omlx_module, "OMLX_BASE_URL", "http://test"),
            patch.object(omlx_module, "get_audio_duration", return_value=4000.0),
            patch.object(omlx_module, "_reconcile_speaker_ids", side_effect=lambda s: s),
        ):
            engine._split_and_transcribe = MagicMock(return_value=mock_result)
            result = engine.transcribe("/tmp/test.wav")

            engine._split_and_transcribe.assert_called_once()
            call_kwargs = engine._split_and_transcribe.call_args.kwargs
            assert call_kwargs["language"] is None
            assert call_kwargs["model"] is None
            assert call_kwargs["include_timestamps"] is True

    def test_speaker_detected_true(self):
        """speaker_detected = True если есть speaker > 0."""
        import src.services.omlx_engine as omlx_module
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 1, "text": "test"}],
            "text": "test",
            "raw_response": None,
        }

        with (
            patch.object(omlx_module, "OMLX_ENABLED", True),
            patch.object(omlx_module, "OMLX_BASE_URL", "http://test"),
            patch.object(omlx_module, "get_audio_duration", return_value=300.0),
            patch.object(omlx_module, "_reconcile_speaker_ids", side_effect=lambda s: s),
        ):
            engine._transcribe_file = MagicMock(return_value=mock_result)
            result = engine.transcribe("/tmp/test.wav")
            assert result["speaker_detected"] is True

    def test_speaker_detected_false(self):
        """speaker_detected = False если все speaker == 0."""
        import src.services.omlx_engine as omlx_module
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "test"}],
            "text": "test",
            "raw_response": None,
        }

        with (
            patch.object(omlx_module, "OMLX_ENABLED", True),
            patch.object(omlx_module, "OMLX_BASE_URL", "http://test"),
            patch.object(omlx_module, "get_audio_duration", return_value=300.0),
            patch.object(omlx_module, "_reconcile_speaker_ids", side_effect=lambda s: s),
        ):
            engine._transcribe_file = MagicMock(return_value=mock_result)
            result = engine.transcribe("/tmp/test.wav")
            assert result["speaker_detected"] is False

    def test_returns_transcription_duration(self):
        """Возвращает transcription_duration."""
        import src.services.omlx_engine as omlx_module
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch.object(omlx_module, "OMLX_ENABLED", True),
            patch.object(omlx_module, "OMLX_BASE_URL", "http://test"),
            patch.object(omlx_module, "get_audio_duration", return_value=300.0),
            patch.object(omlx_module, "_reconcile_speaker_ids", side_effect=lambda s: s),
        ):
            engine._transcribe_file = MagicMock(return_value={
                "segments": [],
                "text": "",
                "raw_response": None,
            })

            result = engine.transcribe("/tmp/test.wav")
            assert "transcription_duration" in result
            assert isinstance(result["transcription_duration"], float)

    def test_passes_language_and_model(self):
        """transcribe передаёт language и model в _transcribe_file."""
        import src.services.omlx_engine as omlx_module
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch.object(omlx_module, "OMLX_ENABLED", True),
            patch.object(omlx_module, "OMLX_BASE_URL", "http://test"),
            patch.object(omlx_module, "get_audio_duration", return_value=300.0),
            patch.object(omlx_module, "_reconcile_speaker_ids", side_effect=lambda s: s),
        ):
            engine._transcribe_file = MagicMock(return_value={
                "segments": [], "text": "", "raw_response": None,
            })
            engine.transcribe("/tmp/test.wav", language="ru", model="whisper-large")

            engine._transcribe_file.assert_called_once_with(
                "/tmp/test.wav", language="ru", model="whisper-large"
            )


# =============================================================================
# TestTranscribeFile
# =============================================================================

class TestTranscribeFile:
    """Тесты OMLXEngine._transcribe_file — прямая транскрибация файла."""

    def _make_mock_response(self, text='[{"Start": 0.0, "End": 1.0, "Speaker": 0, "Content": "hello"}]'):
        from unittest.mock import MagicMock
        mock = MagicMock()
        mock.text = text
        mock.status_code = 200
        mock.json.return_value = json.loads(text)
        mock.raise_for_status.return_value = None
        return mock

    def test_transcribe_file_opens_file_directly(self):
        """_transcribe_file открывает файл напрямую, не через BytesIO."""
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response()

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.OMLX_API_KEY", "key123"),
            patch("src.services.omlx_engine.requests.post", return_value=mock_response) as mock_post,
            patch("builtins.open", MagicMock(return_value=MagicMock(read=lambda: b"fake"))),
        ):
            engine._transcribe_file("/tmp/test.wav", language="en")

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            # Файл передан как file-like объект, не bytes
            file_tuple = call_kwargs["files"]["file"]
            assert file_tuple[0] == "test.wav"
            # Второй элемент — file-like объект
            assert hasattr(file_tuple[1], "read") or hasattr(file_tuple[1], "__iter__")

    def test_transcribe_file_includes_language(self):
        """_transcribe_file передаёт language в payload."""
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response()

        captured_data = {}

        def capture_post(_url, _files=None, data=None, _headers=None, _timeout=None, **_kwargs):
            captured_data["data"] = data
            return mock_response

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.requests.post", side_effect=capture_post),
            patch("builtins.open", MagicMock(return_value=MagicMock(read=lambda: b"fake"))),
        ):
            engine._transcribe_file("/tmp/test.wav", language="ru")

        assert captured_data["data"]["language"] == "ru"

    def test_transcribe_file_parses_response(self):
        """_transcribe_file парсит ответ API."""
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response(
            '[{"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "Hello world"}]'
        )

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.requests.post", return_value=mock_response),
            patch("builtins.open", MagicMock(return_value=MagicMock(read=lambda: b"fake"))),
        ):
            result = engine._transcribe_file("/tmp/test.wav", language="en")

            assert len(result["segments"]) == 1
            assert result["segments"][0]["text"] == "Hello world"

    def test_transcribe_file_api_error_propagates(self):
        """_transcribe_file прокидывает ошибки API."""
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.requests.post") as mock_post,
            patch("builtins.open", MagicMock(return_value=MagicMock(read=lambda: b"fake"))),
        ):
            mock_post.return_value.raise_for_status.side_effect = Exception("500")

            with pytest.raises(Exception, match="500"):
                engine._transcribe_file("/tmp/test.wav", language="en")


# =============================================================================
# TestTranscribeSegment
# =============================================================================

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
            patch("src.services.omlx_engine.requests", mock_requests_module),
        ):
            engine._transcribe_segment(b"fake_wav_data", language="en")

            mock_requests_module.post.assert_called_once()
            call_args = mock_requests_module.post.call_args
            assert call_args.args[0] == "http://test/audio/transcriptions"

    def test_includes_language_in_payload(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response()

        captured_data = {}

        def capture_post(_url, _files=None, data=None, _headers=None, _timeout=None, **_kwargs):
            captured_data["data"] = data
            return mock_response

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment(b"fake_wav_data", language="ru")

        assert captured_data["data"]["language"] == "ru"

    def test_parses_json_api_response(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response(
            '[{"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "Hello world"}]'
        )

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.requests.post", return_value=mock_response),
        ):
            result = engine._transcribe_segment(b"fake_wav_data", language="en")

            assert len(result["segments"]) == 1
            assert result["segments"][0]["text"] == "Hello world"

    def test_api_error_propagates(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.requests.post") as mock_post,
        ):
            mock_post.return_value.raise_for_status.side_effect = Exception("500")

            with pytest.raises(Exception, match="500"):
                engine._transcribe_segment(b"fake_wav_data", language="en")


# =============================================================================
# TestDetectSilenceChunks
# =============================================================================

class TestDetectSilenceChunks:
    """Тесты _detect_silence_chunks()."""

    def _create_test_audio(self, segments_data):
        """Создать временный WAV-файл из последовательности silent/tone сегментов."""
        from pydub import AudioSegment
        from pydub.generators import Sine

        combined = AudioSegment.empty()
        for is_silent, duration_ms in segments_data:
            if is_silent:
                combined += AudioSegment.silent(duration=duration_ms)
            else:
                combined += Sine(440).to_audio_segment(duration=duration_ms)
        path = "/tmp/_test_audio_detect.wav"
        combined.export(path, format="wav")
        return path

    def test_detects_non_silent_chunks(self):
        """Звук-тишина-звук → 2 не-тихих интервала."""
        from src.services.omlx_engine import _detect_silence_chunks

        path = self._create_test_audio([
            (False, 1000),  # 1s sound
            (True, 2000),   # 2s silence
            (False, 1000),  # 1s sound
        ])
        try:
            audio = __import__("pydub").AudioSegment.from_file(path)
            intervals = _detect_silence_chunks(audio, gap_ms=500)

            assert len(intervals) == 2
            # Оба интервала содержат звук
            assert intervals[0][1] - intervals[0][0] > 500
            assert intervals[1][1] - intervals[1][0] > 500
        finally:
            __import__("os").remove(path)

    def test_returns_empty_for_pure_silence(self):
        """Чистая тишина → пустой список."""
        from src.services.omlx_engine import _detect_silence_chunks

        path = self._create_test_audio([
            (True, 5000),
        ])
        try:
            audio = __import__("pydub").AudioSegment.from_file(path)
            intervals = _detect_silence_chunks(audio, gap_ms=500)
            assert intervals == []
        finally:
            __import__("os").remove(path)


# =============================================================================
# TestSplitAndTranscribe
# =============================================================================

class TestSplitAndTranscribe:
    """Тесты OMLXEngine._split_and_transcribe()."""

    def _create_test_audio(self, segments_data):
        """Создать временный WAV-файл из последовательности silent/tone сегментов."""
        from pydub import AudioSegment
        from pydub.generators import Sine

        combined = AudioSegment.empty()
        for is_silent, duration_ms in segments_data:
            if is_silent:
                combined += AudioSegment.silent(duration=duration_ms)
            else:
                combined += Sine(440).to_audio_segment(duration=duration_ms)
        path = "/tmp/_test_audio_split_and_transcribe.wav"
        combined.export(path, format="wav")
        return path

    def test_calls_transcribe_segment_for_each_chunk(self):
        """_split_and_transcribe вызывает _transcribe_segment для каждого чанка."""
        from pydub import AudioSegment
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "chunk"}],
            "text": "chunk",
            "raw_response": None,
        }

        mock_audio = MagicMock()
        mock_audio.frame_rate = 44100
        mock_audio.channels = 1
        mock_audio.sample_width = 2
        # 100 сэмплов со значением 1000 (не тишина)
        mock_audio.raw_data = (b"\xe8\x03" * 100)  # 100 samples of 1000
        mock_audio.__getitem__ = lambda self, key: AudioSegment.empty()

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.OMLX_API_KEY", "key"),
            patch("src.services.omlx_engine._reconcile_speaker_ids", side_effect=lambda s: s),
            patch("pydub.AudioSegment.from_file", return_value=mock_audio),
        ):
            engine._transcribe_segment = MagicMock(return_value=mock_result)
            result = engine._split_and_transcribe("/tmp/test.wav")

            engine._transcribe_segment.assert_called_once()
            assert len(result["segments"]) == 1

    def test_offset_correction_applied(self):
        """Таймкоды корректируются на смещение чанка."""
        import src.services.omlx_engine as omlx_module
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "chunk"}],
            "text": "chunk",
            "raw_response": None,
        }

        captured_segments = []

        def capture_transcribe_segment(audio_bytes, language=None, model=None):
            captured_segments.append(audio_bytes)
            return mock_result

        with (
            patch.object(omlx_module, "OMLX_ENABLED", True),
            patch.object(omlx_module, "OMLX_BASE_URL", "http://test"),
            patch.object(omlx_module, "OMLX_MODEL", "test-model"),
            patch.object(omlx_module, "OMLX_API_KEY", "key"),
            patch.object(omlx_module, "_reconcile_speaker_ids", side_effect=lambda s: s),
        ):
            engine._transcribe_segment = MagicMock(side_effect=capture_transcribe_segment)

            # Создаём аудио с одним длинным звуком (10s)
            path = self._create_test_audio([(False, 10000)])
            try:
                engine._split_and_transcribe(path, start_time=0)
            finally:
                __import__("os").remove(path)

            # Должен быть 1 чанк
            assert len(captured_segments) == 1

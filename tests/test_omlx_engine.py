"""Тесты для функций парсинга omlx_engine.py."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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

    def test_skips_failed_segments(self):
        """Упавший сегмент не ломает весь процесс."""
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch("src.services.omlx_engine._split_audio_by_silence") as mock_split,
            patch("src.services.omlx_engine.OMLX_ENABLED", True),
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
        ):
            # Один сегмент, который упадёт при транскрипции
            mock_split.return_value = ([(0, 5000, b"fake_opus_data")], 16000)

            original_transcribe_segment = engine._transcribe_segment
            engine._transcribe_segment = MagicMock(side_effect=RuntimeError("API down"))

            try:
                result = engine.transcribe("/tmp/test.wav")

                assert isinstance(result["segments"], list)
                assert isinstance(result["text"], str)
            finally:
                engine._transcribe_segment = original_transcribe_segment

    def test_corrects_time_offset(self):
        """Корректировка временных меток по сдвигу сегмента."""
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
            # Начальный сдвиг 500 мс
            mock_split.return_value = ([(500, 5500, b"fake_opus_data")], 16000)

            engine._transcribe_segment = MagicMock(return_value=mock_result)
            result = engine.transcribe("/tmp/test.wav")

            # Start должен быть скорректирован: 0.0 + 0.5 = 0.5
            assert result["segments"][0]["start"] == pytest.approx(0.5)
            assert result["segments"][0]["end"] == pytest.approx(1.5)

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

        def passthrough_segments(segments):
            return segments

        with (
            patch.object(omlx_module, "_split_audio_by_silence", return_value=([(0, -1, b"fake_opus_data")], 16000)),
            patch.object(omlx_module, "_reconcile_speaker_ids", side_effect=passthrough_segments),
            patch.object(omlx_module, "OMLX_ENABLED", True),
            patch.object(omlx_module, "OMLX_BASE_URL", "http://test"),
        ):
            engine._transcribe_segment = MagicMock(return_value=mock_result)

            result = engine.transcribe("/tmp/test.wav")
            assert result["speaker_detected"] is True

    def test_speaker_detected_false(self):
        """speaker_detected = False если все speaker == 0."""
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
            mock_split.return_value = ([(0, -1, "/tmp/seg.wav")], 16000)
            engine._transcribe_segment = MagicMock(return_value=mock_result)

            result = engine.transcribe("/tmp/test.wav")
            assert result["speaker_detected"] is False

    def test_returns_transcription_duration(self):
        """Возвращает transcription_duration."""
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()

        with (
            patch("src.services.omlx_engine._split_audio_by_silence") as mock_split,
            patch("src.services.omlx_engine.OMLX_ENABLED", True),
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
        ):
            mock_split.return_value = ([(0, -1, "/tmp/seg.wav")], 16000)
            engine._transcribe_segment = MagicMock(return_value={
                "segments": [],
                "text": "",
                "raw_response": None,
            })

            result = engine.transcribe("/tmp/test.wav")
            assert "transcription_duration" in result
            assert isinstance(result["transcription_duration"], float)


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
            patch("src.services.omlx_engine._requests", mock_requests_module),
        ):
            engine._transcribe_segment(b"fake_opus_data", language="en")

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
            patch("src.services.omlx_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment(b"fake_opus_data", language="ru")

        assert captured_data["data"]["language"] == "ru"

    def test_includes_api_key_header(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response()

        captured_headers = {}

        def capture_post(_url, _files=None, _data=None, headers=None, _timeout=None, **_kwargs):
            captured_headers["headers"] = headers
            return mock_response

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.OMLX_API_KEY", "secret-key"),
            patch("src.services.omlx_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment(b"fake_opus_data", language="en")

        assert captured_headers["headers"]["Authorization"] == "Bearer secret-key"

    def test_no_auth_header_without_key(self):
        from src.services.omlx_engine import OMLXEngine

        engine = OMLXEngine()
        mock_response = self._make_mock_response()

        captured_headers = {}

        def capture_post(_url, _files=None, _data=None, headers=None, _timeout=None, **_kwargs):
            captured_headers["headers"] = headers
            return mock_response

        with (
            patch("src.services.omlx_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.omlx_engine.OMLX_MODEL", "test-model"),
            patch("src.services.omlx_engine.OMLX_API_KEY", None),
            patch("src.services.omlx_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment(b"fake_opus_data")

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
            result = engine._transcribe_segment(b"fake_opus_data", language="en")

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
                engine._transcribe_segment(b"fake_opus_data", language="en")


# =============================================================================
# TestSplitAudioBySilenceIntegration
# =============================================================================

class TestSplitAudioBySilenceIntegration:
    """Интеграционные тесты _split_audio_by_silence с реальным pydub AudioSegment."""

    def _create_test_audio(self, segments_data):
        """Создать временный WAV-файл из последовательности silent/tone сегментов.

        segments_data: list of (is_silent: bool, duration_ms: int)
        """
        from pydub import AudioSegment
        from pydub.generators import Sine

        combined = AudioSegment.empty()
        for is_silent, duration_ms in segments_data:
            if is_silent:
                combined += AudioSegment.silent(duration=duration_ms)
            else:
                combined += Sine(440).to_audio_segment(duration=duration_ms)
        path = "/tmp/_test_audio_split.wav"
        combined.export(path, format="wav")
        return path

    def test_splits_on_silence_gaps(self):
        """Тихий-звук-тихий-звук-тихий → 2 сегмента."""
        from src.services.omlx_engine import _split_audio_by_silence

        path = self._create_test_audio([
            (True, 2000),   # 2s silence
            (False, 1000),  # 1s sound
            (True, 3000),   # 3s silence (gap)
            (False, 1500),  # 1.5s sound
            (True, 1000),   # 1s silence
        ])
        try:
            segments, sr = _split_audio_by_silence(path)

            assert sr == 44100  # pydub default for Sine
            assert len(segments) == 2
            # Первый сегмент: ~1s, второй: ~1.5s
            assert segments[0][1] - segments[0][0] > 500
            assert segments[1][1] - segments[1][0] > 500
            # Оба содержат данные
            assert len(segments[0][2]) > 0
            assert len(segments[1][2]) > 0
        finally:
            os.remove(path)

    def test_returns_single_segment_no_silence(self):
        """Без тишины — один сегмент на всё аудио."""
        from src.services.omlx_engine import _split_audio_by_silence

        path = self._create_test_audio([
            (False, 3000),
        ])
        try:
            segments, _ = _split_audio_by_silence(path)
            assert len(segments) == 1
            assert segments[0][0] == 0
            assert segments[0][1] == 3000  # end_ms = duration for single segment
            assert len(segments[0][2]) > 0
        finally:
            os.remove(path)

    def test_returns_empty_for_pure_silence(self):
        """Чистая тишина → fallback (0, -1, b'')."""
        from src.services.omlx_engine import _split_audio_by_silence

        path = self._create_test_audio([
            (True, 5000),
        ])
        try:
            segments, _ = _split_audio_by_silence(path)
            # При чистой тишине возвращается fallback
            assert len(segments) == 1
            assert segments[0] == (0, -1, b"")
        finally:
            os.remove(path)

    def test_respects_max_duration(self):
        """Длинный сегмент разбивается на чанки по max_duration_sec."""
        from src.services.omlx_engine import _split_audio_by_silence

        # 15s sound — больше MAX_AUDIO_DURATION_SEC (300s), но для теста
        # используем маленький max_duration
        path = self._create_test_audio([
            (False, 15000),  # 15s sound
        ])
        try:
            segments, _ = _split_audio_by_silence(path, max_duration_sec=5)
            # 15s / 5s = 3 чанка
            assert len(segments) == 3
            for seg in segments:
                assert seg[1] == -1  # промежуточные чанки имеют -1
                assert len(seg[2]) > 0
        finally:
            os.remove(path)

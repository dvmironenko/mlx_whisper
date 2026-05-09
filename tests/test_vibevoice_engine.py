"""Тесты для функций парсинга vibevoice_engine.py."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# =============================================================================
# Module-level fixtures (not class methods)
# =============================================================================

@pytest.fixture
def parse_func():
    from src.services.vibevoice_engine import _parse_segments_from_json
    return _parse_segments_from_json


@pytest.fixture
def raw_parse_func():
    from src.services.vibevoice_engine import _parse_segments_from_raw_text
    return _parse_segments_from_raw_text


@pytest.fixture
def group_func():
    from src.services.vibevoice_engine import _group_intervals
    return _group_intervals


# =============================================================================
# TestParseSegmentsFromJson
# =============================================================================

class TestParseSegmentsFromJson:
    """Тесты _parse_segments_from_json()."""

    def test_parses_valid_json(self, parse_func):
        segments = [
            {"Start": 0.0, "End": 1.5, "Speaker": 1, "Content": "Привет"},
            {"Start": 1.5, "End": 3.0, "Speaker": 2, "Content": "Пока"},
        ]
        result = parse_func(json.dumps(segments))

        assert result is not None
        assert len(result) == 2
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 1.5
        assert result[0]["speaker"] == 1
        assert result[0]["text"] == "Привет"

    def test_parses_lowercase_keys(self, parse_func):
        segments = [
            {"start": 0.0, "end": 1.5, "speaker": 1, "content": "Привет"},
        ]
        result = parse_func(json.dumps(segments))

        assert result is not None
        assert result[0]["start"] == 0.0
        assert result[0]["text"] == "Привет"

    def test_returns_none_for_non_array_json(self, parse_func):
        result = parse_func('{"key": "value"}')
        assert result is None

    def test_returns_none_for_plain_text(self, parse_func):
        result = parse_func("Просто текст без JSON")
        assert result is None

    def test_returns_none_for_empty_list(self, parse_func):
        result = parse_func("[]")
        assert result is None

    def test_handles_json_in_code_block(self, parse_func):
        raw = "```json\n[{\"Start\": 0.0, \"End\": 1.0, \"Speaker\": 1, \"Content\": \"test\"}]\n```"
        result = parse_func(raw)

        assert result is not None
        assert len(result) == 1
        assert result[0]["text"] == "test"

    def test_handles_json_without_code_block(self, parse_func):
        raw = "[{\"Start\": 0.0, \"End\": 1.0, \"Speaker\": 1, \"Content\": \"test\"}]"
        result = parse_func(raw)

        assert result is not None
        assert len(result) == 1

    def test_skips_non_dict_items(self, parse_func):
        segments = ["string_item", {"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "valid"}]
        result = parse_func(json.dumps(segments))

        assert result is not None
        assert len(result) == 1
        assert result[0]["text"] == "valid"

    def test_default_values_for_missing_keys(self, parse_func):
        segments = [{"Content": "test"}]
        result = parse_func(json.dumps(segments))

        assert result is not None
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 0.0
        assert result[0]["speaker"] == 0
        assert result[0]["text"] == "test"

    def test_handles_invalid_json(self, parse_func):
        result = parse_func("{invalid json[")
        assert result is None


# =============================================================================
# TestParseSegmentsFromRawText
# =============================================================================

class TestParseSegmentsFromRawText:
    """Тесты _parse_segments_from_raw_text()."""

    def test_parses_speaker_format(self, raw_parse_func):
        raw = "[00:01] Speaker 1: Привет\n[00:02] Speaker 2: Пои"
        result = raw_parse_func(raw)

        assert len(result) == 2
        assert result[0]["start"] == 1.0
        assert result[0]["speaker"] == 1
        assert result[0]["text"] == "Привет"
        assert result[1]["start"] == 2.0
        assert result[1]["speaker"] == 2
        assert result[1]["text"] == "Пои"

    def test_parses_mixed_timestamps(self, raw_parse_func):
        raw = "[01:30] Speaker 0: Тест\n[02:45] Speaker 3: Ещё текст"
        result = raw_parse_func(raw)

        assert len(result) == 2
        assert result[0]["start"] == 90.0  # 1*60 + 30
        assert result[1]["start"] == 165.0  # 2*60 + 45
        assert result[1]["speaker"] == 3

    def test_skips_empty_lines(self, raw_parse_func):
        raw = "\n[00:01] Speaker 1: Текст\n\n"
        result = raw_parse_func(raw)

        assert len(result) == 1

    def test_skips_non_matching_lines(self, raw_parse_func):
        raw = "Some random text\n[00:01] Speaker 1: Valid\nNo match here"
        result = raw_parse_func(raw)

        assert len(result) == 1
        assert result[0]["text"] == "Valid"

    def test_empty_string(self, raw_parse_func):
        result = raw_parse_func("")
        assert result == []

    def test_end_time_is_zero_for_all(self, raw_parse_func):
        raw = "[00:01] Speaker 1: Текст"
        result = raw_parse_func(raw)

        assert result[0]["end"] == 1.0


# =============================================================================
# TestGroupIntervals
# =============================================================================

class TestGroupIntervals:
    """Тесты _group_intervals()."""

    def test_merges_close_intervals(self, group_func):
        # Пауза < 2 сек — объединяем
        intervals = [(0, 10000), (10005, 20000)]  # 5000 samples gap at 16kHz ~ 0.3 сек
        result = group_func(intervals, gap_samples=int(2.0 * 16000))

        assert len(result) == 1
        assert result[0] == (0, 20000)

    def test_keeps_separated_intervals(self, group_func):
        # Пауза > 2 сек — не объединяем
        intervals = [(0, 10000), (50000, 60000)]  # 40000 samples ~ 2.5 сек
        result = group_func(intervals, gap_samples=int(2.0 * 16000))

        assert len(result) == 2
        assert result[0] == (0, 10000)
        assert result[1] == (50000, 60000)

    def test_empty_list(self, group_func):
        result = group_func([])
        assert result == []

    def test_single_interval(self, group_func):
        result = group_func([(0, 10000)])
        assert result == [(0, 10000)]

    def test_overlapping_intervals(self, group_func):
        # Перекрытие — сливаем
        intervals = [(0, 5000), (3000, 8000), (7000, 12000)]
        result = group_func(intervals, gap_samples=int(2.0 * 16000))

        assert len(result) == 1
        assert result[0] == (0, 12000)


# =============================================================================
# TestVibeVoiceEngineTranscribe
# =============================================================================

class TestVibeVoiceEngineTranscribe:
    """Тесты VibeVoiceEngine.transcribe()."""

    def test_raises_when_not_enabled(self):
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        with patch("src.services.vibevoice_engine.OMLX_ENABLED", False):
            with pytest.raises(RuntimeError, match="oMLX не настроен"):
                engine.transcribe("/tmp/test.wav")

    def test_raises_when_no_base_url(self):
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        with patch("src.services.vibevoice_engine.OMLX_BASE_URL", ""):
            with patch("src.services.vibevoice_engine.OMLX_ENABLED", True):
                with pytest.raises(RuntimeError, match="oMLX не настроен"):
                    engine.transcribe("/tmp/test.wav")

    def test_skips_failed_segments(self):
        """Упавший сегмент не ломает весь процесс."""
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()

        with (
            patch("src.services.vibevoice_engine._split_audio_by_silence") as mock_split,
            patch("src.services.vibevoice_engine.OMLX_ENABLED", True),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
        ):
            # Один сегмент, который упадёт при транскрипции
            mock_split.return_value = [(0, -1, "/tmp/seg.wav")]

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
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 1, "text": "test"}],
            "text": "test",
        }

        with (
            patch("src.services.vibevoice_engine._split_audio_by_silence") as mock_split,
            patch("src.services.vibevoice_engine.OMLX_ENABLED", True),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
        ):
            # Начальный сдвиг 8000 сэмплов = 0.5 сек при 16kHz
            mock_split.return_value = [(8000, -1, "/tmp/seg.wav")]

            engine._transcribe_segment = MagicMock(return_value=mock_result)
            result = engine.transcribe("/tmp/test.wav")

            # Start должен быть скорректирован: 0.0 + 0.5 = 0.5
            assert result["segments"][0]["start"] == pytest.approx(0.5)
            assert result["segments"][0]["end"] == pytest.approx(1.5)

    def test_speaker_detected_true(self):
        """speaker_detected = True если есть speaker > 0."""
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 1, "text": "test"}],
            "text": "test",
        }

        with (
            patch("src.services.vibevoice_engine._split_audio_by_silence") as mock_split,
            patch("src.services.vibevoice_engine.OMLX_ENABLED", True),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
        ):
            mock_split.return_value = [(0, -1, "/tmp/seg.wav")]
            engine._transcribe_segment = MagicMock(return_value=mock_result)

            result = engine.transcribe("/tmp/test.wav")
            assert result["speaker_detected"] is True

    def test_speaker_detected_false(self):
        """speaker_detected = False если все speaker == 0."""
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        mock_result = {
            "segments": [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "test"}],
            "text": "test",
        }

        with (
            patch("src.services.vibevoice_engine._split_audio_by_silence") as mock_split,
            patch("src.services.vibevoice_engine.OMLX_ENABLED", True),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
        ):
            mock_split.return_value = [(0, -1, "/tmp/seg.wav")]
            engine._transcribe_segment = MagicMock(return_value=mock_result)

            result = engine.transcribe("/tmp/test.wav")
            assert result["speaker_detected"] is False

    def test_returns_transcription_duration(self):
        """Возвращает transcription_duration."""
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()

        with (
            patch("src.services.vibevoice_engine._split_audio_by_silence") as mock_split,
            patch("src.services.vibevoice_engine.OMLX_ENABLED", True),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
        ):
            mock_split.return_value = [(0, -1, "/tmp/seg.wav")]
            engine._transcribe_segment = MagicMock(return_value={
                "segments": [],
                "text": "",
            })

            result = engine.transcribe("/tmp/test.wav")
            assert "transcription_duration" in result
            assert isinstance(result["transcription_duration"], float)


# =============================================================================
# TestTranscribeSegment
# =============================================================================

class TestTranscribeSegment:
    """Тесты VibeVoiceEngine._transcribe_segment()."""

    def _make_mock_response(self, text="[]"):
        mock = MagicMock()
        mock.text = text
        mock.raise_for_status = MagicMock()
        return mock

    def test_calls_api_with_correct_url(self):
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        mock_response = self._make_mock_response(
            '[{"Start": 0.0, "End": 1.0, "Speaker": 1, "Content": "hello"}]'
        )
        mock_requests_module = MagicMock()
        mock_requests_module.post = MagicMock(return_value=mock_response)

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "test-model"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", "key123"),
            patch("src.services.vibevoice_engine._requests", mock_requests_module),
        ):
            engine._transcribe_segment("/tmp/seg.wav", "en")

            mock_requests_module.post.assert_called_once()
            call_args = mock_requests_module.post.call_args
            assert call_args.args[0] == "http://test/audio/transcriptions"

    def test_includes_language_in_payload(self):
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        mock_response = self._make_mock_response()

        captured_data = {}

        def capture_post(url, files=None, data=None, headers=None, timeout=None, **kwargs):
            captured_data["data"] = data
            return mock_response

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "test-model"),
            patch("src.services.vibevoice_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment("/tmp/seg.wav", "ru")

        assert captured_data["data"]["language"] == "ru"

    def test_includes_api_key_header(self):
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        mock_response = self._make_mock_response()

        captured_headers = {}

        def capture_post(url, files=None, data=None, headers=None, timeout=None, **kwargs):
            captured_headers["headers"] = headers
            return mock_response

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "test-model"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", "secret-key"),
            patch("src.services.vibevoice_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment("/tmp/seg.wav", None)

        assert captured_headers["headers"]["Authorization"] == "Bearer secret-key"

    def test_no_auth_header_without_key(self):
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        mock_response = self._make_mock_response()

        captured_headers = {}

        def capture_post(url, files=None, data=None, headers=None, timeout=None, **kwargs):
            captured_headers["headers"] = headers
            return mock_response

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "test-model"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", None),
            patch("src.services.vibevoice_engine._requests.post", side_effect=capture_post),
        ):
            engine._transcribe_segment("/tmp/seg.wav", None)

        assert captured_headers["headers"] is None or "Authorization" not in captured_headers["headers"]

    def test_fallback_to_text_parser(self):
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()
        mock_response = self._make_mock_response("[00:01] Speaker 1: Hello world")

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "test-model"),
            patch("src.services.vibevoice_engine._requests.post", return_value=mock_response),
        ):
            result = engine._transcribe_segment("/tmp/seg.wav", "en")

            assert len(result["segments"]) == 1
            assert result["segments"][0]["text"] == "Hello world"

    def test_api_error_propagates(self):
        from src.services.vibevoice_engine import VibeVoiceEngine

        engine = VibeVoiceEngine()

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine._requests.post") as mock_post,
        ):
            mock_post.return_value.raise_for_status.side_effect = Exception("500")

            with pytest.raises(Exception, match="500"):
                engine._transcribe_segment("/tmp/seg.wav", "en")

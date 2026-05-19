"""Тесты обработки 404 not_found_error от OMLX API."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.services.vibevoice_engine import VibeVoiceEngine, OMLXModelNotFoundError


class TestOMLXModelNotFoundError:
    """Проверка обработки модели не найденной в OMLX."""

    @pytest.fixture
    def engine(self):
        return VibeVoiceEngine()

    def test_raises_on_404_not_found_error(self, engine):
        """При 404 not_found_error от OMLX — raising OMLXModelNotFoundError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": {
                "message": "Model 'VibeVoice-ASR-99bit' not found. Available: VibeVoice-ASR-4bit, ...",
                "type": "not_found_error",
                "param": None,
                "code": None,
            }
        }
        mock_response.text = json.dumps(mock_response.json())

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "VibeVoice-ASR-99bit"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", None),
            patch("src.services.vibevoice_engine._requests.post", return_value=mock_response),
        ):
            with pytest.raises(OMLXModelNotFoundError, match="Модель 'VibeVoice-ASR-99bit' не найдена"):
                engine._transcribe_segment("/tmp/seg.wav", "ru")

    def test_error_message_contains_model_name(self, engine):
        """Сообщение об ошибке содержит имя модели."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": {"message": "Model 'WrongModel' not found", "type": "not_found_error"}
        }
        mock_response.text = json.dumps(mock_response.json())

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "WrongModel"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", None),
            patch("src.services.vibevoice_engine._requests.post", return_value=mock_response),
        ):
            with pytest.raises(OMLXModelNotFoundError, match="WrongModel"):
                engine._transcribe_segment("/tmp/seg.wav", None)

    def test_does_not_raise_on_404_with_different_error_type(self, engine):
        """404 с другим type — не raising OMLXModelNotFoundError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": {"message": "Bad request", "type": "invalid_request_error"}
        }
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "VibeVoice-ASR-4bit"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", None),
            patch("src.services.vibevoice_engine._requests.post", return_value=mock_response),
        ):
            # raise_for_status уже выбросил HTTPError — должно прокинуться
            with pytest.raises(requests.exceptions.HTTPError):
                engine._transcribe_segment("/tmp/seg.wav", None)

    def test_does_not_raise_on_200(self, engine):
        """Успешный ответ 200 — не raising."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({
            "text": '[{"Start":0,"End":5.0,"Speaker":0,"Content":"test"}]',
            "language": "ru",
        })

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "VibeVoice-ASR-4bit"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", None),
            patch("src.services.vibevoice_engine._requests.post", return_value=mock_response),
        ):
            result = engine._transcribe_segment("/tmp/seg.wav", "ru")
            assert result["text"] == "test"

    def test_transcribe_raises_on_all_segments_404(self, engine):
        """Если все сегменты упали с 404 — raising OMLXModelNotFoundError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": {"message": "Model 'X' not found", "type": "not_found_error"}
        }
        mock_response.text = json.dumps(mock_response.json())

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine._split_audio_by_silence", return_value=[
                [(0, -1, "/tmp/seg1.wav"), (0, -1, "/tmp/seg2.wav")], 16000
            ]),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "NonExistent"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", None),
            patch("src.services.vibevoice_engine._requests.post", return_value=mock_response),
        ):
            with pytest.raises(OMLXModelNotFoundError, match="NonExistent"):
                engine.transcribe("/tmp/test.wav")

    def test_transcribe_continues_on_other_errors(self, engine):
        """Другие ошибки сегментов — continue, не raising."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count == 1:
                mock_response.status_code = 500
                mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
            else:
                mock_response.status_code = 200
                mock_response.text = json.dumps({
                    "text": '[{"Start":0,"End":5.0,"Speaker":0,"Content":"ok"}]',
                    "language": "ru",
                })
            return mock_response

        with (
            patch("builtins.open", MagicMock(return_value=MagicMock())),
            patch("src.services.vibevoice_engine._split_audio_by_silence", return_value=[
                [(0, -1, "/tmp/seg1.wav"), (0, -1, "/tmp/seg2.wav")], 16000
            ]),
            patch("src.services.vibevoice_engine.OMLX_BASE_URL", "http://test"),
            patch("src.services.vibevoice_engine.OMLX_MODEL", "VibeVoice-ASR-4bit"),
            patch("src.services.vibevoice_engine.OMLX_API_KEY", None),
            patch("src.services.vibevoice_engine._requests.post", side_effect=mock_post),
        ):
            result = engine.transcribe("/tmp/test.wav")
            # Второй сегмент успешен — результат есть
            assert len(result["segments"]) == 1
            assert "[00:00] Спикер 0 : ok" in result["text"]

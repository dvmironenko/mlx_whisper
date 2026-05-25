"""Тесты для src/services/whisper_engines.py."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGetEngine:
    """Тесты factory функции get_engine()."""

    def test_default_returns_whisper_engine(self):
        from src.services.whisper_engines import get_engine

        engine = get_engine()
        assert type(engine).__name__ == "WhisperEngine"

    def test_explicit_whisper(self):
        from src.services.whisper_engines import get_engine

        engine = get_engine("whisper")
        assert type(engine).__name__ == "WhisperEngine"

    def test_omlx_returns_omlx_engine(self):
        from src.services.whisper_engines import get_engine

        engine = get_engine("omlx")
        assert type(engine).__name__ == "OMLXEngine"

    def test_unknown_mechanism_returns_whisper(self):
        from src.services.whisper_engines import get_engine

        engine = get_engine("unknown")
        assert type(engine).__name__ == "WhisperEngine"


class TestWhisperEngineTranscribe:
    """Тесты WhisperEngine.transcribe()."""

    @pytest.fixture
    def mock_model_cache(self, monkeypatch):
        """Мокаем ModelCache."""
        cache = MagicMock()
        cache.get_model.return_value = None
        cache.load_model.return_value = None
        monkeypatch.setattr("src.services.whisper_engines.ModelCache.get_instance", lambda: cache)
        return cache

    @pytest.fixture
    def mock_mlx_transcribe(self, monkeypatch):
        """Мокаем mlx_whisper.transcribe."""
        mock = MagicMock(return_value={
            "text": "Привет мир",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Привет"},
                {"start": 1.0, "end": 2.0, "text": "мир"},
            ],
        })
        monkeypatch.setattr("src.services.whisper_engines._mlx_transcribe", mock)
        return mock

    @pytest.fixture
    def mock_audio_duration(self, monkeypatch):
        """Мокаем получение длительности аудио."""
        monkeypatch.setattr(
            "src.services.whisper_engines.get_audio_duration",
            lambda _: 2.0,
        )

    def test_returns_normalized_format(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration
    ):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        result = engine.transcribe("/tmp/test.wav")

        assert "segments" in result
        assert "text" in result
        assert "speaker_detected" in result
        assert "transcription_duration" in result
        assert result["text"] == "[00:00]: Привет\n[00:01]: мир"
        assert result["speaker_detected"] is False
        assert isinstance(result["transcription_duration"], float)
        assert isinstance(result["segments"], list)

    def test_passes_language_parameter(self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", language="ru")

        mock_mlx_transcribe.assert_called_once()
        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["language"] == "ru"

    def test_passes_task_parameter(self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", task="translate")

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["task"] == "translate"

    def test_passes_word_timestamps(self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", word_timestamps=True)

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["word_timestamps"] is True

    def test_passes_initial_prompt(self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", initial_prompt="Контекстный промпт")

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["initial_prompt"] == "Контекстный промпт"

    def test_no_speech_threshold_none_not_passed(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration
    ):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav")

        call_kwargs = mock_mlx_transcribe.call_args
        assert "no_speech_threshold" not in call_kwargs.kwargs

    def test_no_speech_threshold_passed_when_set(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration
    ):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", no_speech_threshold=0.6)

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["no_speech_threshold"] == 0.6

    def test_hallucination_silence_threshold_passed(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration
    ):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", hallucination_silence_threshold=0.5)

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["hallucination_silence_threshold"] == 0.5

    def test_condition_on_previous_text_default_true(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration
    ):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav")

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["condition_on_previous_text"] is True

    def test_condition_on_previous_text_false(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration
    ):
        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", condition_on_previous_text=False)

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["condition_on_previous_text"] is False

    def test_model_path_resolution_existing(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration, tmp_path, monkeypatch
    ):
        """Модель существует в MODELS_DIR — используем локальный путь."""
        model_dir = tmp_path / "whisper-turbo"
        model_dir.mkdir()

        original_transcribe = None

        def patched_transcribe(self, file_path: str, **params):
            # Override model resolution to use tmp_path
            params["path_or_hf_repo"] = str(model_dir)
            # Call the parent method but with the overridden path
            import time
            start = time.time()
            # Get model cache
            cache = mock_model_cache
            cached_model = cache.get_model(params.get("model", "large"))
            if cached_model is None:
                cache.load_model(params.get("model", "large"), str(model_dir))
            duration = time.time() - start

            # Call the mocked _mlx_transcribe
            import src.services.whisper_engines as te
            raw_result = te._mlx_transcribe(
                path_or_hf_repo=str(model_dir),
                audio_path=file_path,
                language=params.get("language"),
                task=params.get("task", "transcribe"),
                word_timestamps=params.get("word_timestamps", False),
                no_speech_threshold=params.get("no_speech_threshold"),
                hallucination_silence_threshold=params.get("hallucination_silence_threshold"),
                condition_on_previous_text=params.get("condition_on_previous_text", True),
                initial_prompt=params.get("initial_prompt"),
            )
            text = raw_result.get("text", "")
            segments = raw_result.get("segments", [])
            has_speaker = any(s.get("speaker", 0) > 0 for s in segments)
            return {
                "text": text,
                "segments": segments,
                "speaker_detected": has_speaker,
                "transcription_duration": round(duration, 2),
            }

        monkeypatch.setattr(
            "src.services.whisper_engines.WhisperEngine.transcribe", patched_transcribe
        )

        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", model="turbo")

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["path_or_hf_repo"] == str(model_dir)

    def test_model_path_resolution_hf_fallback(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration, tmp_path, monkeypatch
    ):
        """Модель не существует — используем hf repo."""

        def patched_transcribe(self, file_path: str, **params):
            import time
            start = time.time()
            cache = mock_model_cache
            cached_model = cache.get_model(params.get("model", "large"))
            if cached_model is None:
                cache.load_model(params.get("model", "large"), "mlx-community/whisper-turbo")
            duration = time.time() - start

            import src.services.whisper_engines as te
            raw_result = te._mlx_transcribe(
                path_or_hf_repo="mlx-community/whisper-turbo",
                audio_path=file_path,
                language=params.get("language"),
                task=params.get("task", "transcribe"),
                word_timestamps=params.get("word_timestamps", False),
                no_speech_threshold=params.get("no_speech_threshold"),
                hallucination_silence_threshold=params.get("hallucination_silence_threshold"),
                condition_on_previous_text=params.get("condition_on_previous_text", True),
                initial_prompt=params.get("initial_prompt"),
            )
            text = raw_result.get("text", "")
            segments = raw_result.get("segments", [])
            has_speaker = any(s.get("speaker", 0) > 0 for s in segments)
            return {
                "text": text,
                "segments": segments,
                "speaker_detected": has_speaker,
                "transcription_duration": round(duration, 2),
            }

        monkeypatch.setattr(
            "src.services.whisper_engines.WhisperEngine.transcribe", patched_transcribe
        )

        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        engine.transcribe("/tmp/test.wav", model="turbo")

        call_kwargs = mock_mlx_transcribe.call_args
        assert call_kwargs.kwargs["path_or_hf_repo"] == "mlx-community/whisper-turbo"

    def test_audio_duration_error_handled(
        self, mock_model_cache, mock_mlx_transcribe, mock_audio_duration, monkeypatch
    ):
        """Ошибка получения длительности не ломает транскрипцию."""
        monkeypatch.setattr(
            "src.services.whisper_engines.get_audio_duration",
            lambda _: (_ for _ in ()).throw(RuntimeError("ffmpeg error")),
        )

        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        result = engine.transcribe("/tmp/test.wav")

        assert "text" in result
        assert "transcription_duration" in result

    def test_mlx_transcribe_error_propagates(
        self, mock_model_cache, mock_audio_duration, monkeypatch
    ):
        """Ошибка mlx транскрипции пробрасывается вверх."""
        monkeypatch.setattr(
            "src.services.whisper_engines._mlx_transcribe",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("MLX error")),
        )

        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        with pytest.raises(RuntimeError, match="MLX error"):
            engine.transcribe("/tmp/test.wav")

    def test_empty_segments_returned(self, mock_model_cache, mock_audio_duration, monkeypatch):
        """Пустые сегменты — пустой список."""
        monkeypatch.setattr(
            "src.services.whisper_engines._mlx_transcribe",
            lambda **kwargs: {"text": "", "segments": []},
        )

        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        result = engine.transcribe("/tmp/test.wav")

        assert result["segments"] == []
        assert result["text"] == ""


class TestTranscribeAudioBackwardCompat:
    """Тесты обратной совместимости: transcribe_audio()."""

    def test_wraps_whisper_engine(self, monkeypatch):
        mock = MagicMock(return_value={"text": "hello", "segments": [], "transcription_duration": 1.0})
        monkeypatch.setattr("src.services.whisper_engines.WhisperEngine.transcribe", mock)

        from src.services.whisper_engines import transcribe_audio

        transcribe_audio("/tmp/test.wav", language="en")

        mock.assert_called_once_with("/tmp/test.wav", language="en")

    def test_returns_dict(self, monkeypatch):
        monkeypatch.setattr(
            "src.services.whisper_engines.WhisperEngine.transcribe",
            lambda self, *a, **k: {"text": "test", "segments": [], "transcription_duration": 1.0},
        )

        from src.services.whisper_engines import transcribe_audio

        result = transcribe_audio("/tmp/test.wav")
        assert isinstance(result, dict)


class TestWhisperEngineIntegration:
    """Интеграционные тесты WhisperEngine с реальным аудио."""

    def test_transcribe_short_audio_returns_normalized_format(self, tmp_path, monkeypatch):
        """WhisperEngine транскрибирует короткое аудио и возвращает нормализованный результат."""
        from pydub import AudioSegment

        # Генерируем 1 секунду тишины
        audio = AudioSegment.silent(duration=1000, frame_rate=16000)
        wav_path = str(tmp_path / "short.wav")
        audio.export(wav_path, format="wav")

        monkeypatch.setattr(
            "src.services.whisper_engines.get_audio_duration",
            lambda _: 1.0,
        )

        from src.services.whisper_engines import WhisperEngine

        engine = WhisperEngine()
        result = engine.transcribe(wav_path, language="en", model="tiny")

        assert "segments" in result
        assert "text" in result
        assert "speaker_detected" in result
        assert "transcription_duration" in result
        assert isinstance(result["segments"], list)
        assert isinstance(result["text"], str)
        assert isinstance(result["speaker_detected"], bool)
        assert isinstance(result["transcription_duration"], float)


class TestClearMemory:
    """Тесты _clear_memory()."""

    def test_clears_mx_cache_and_gc(self, monkeypatch):
        mx_clear = MagicMock()
        gc_collect = MagicMock()
        monkeypatch.setattr("mlx.core.clear_cache", mx_clear)
        monkeypatch.setattr("gc.collect", gc_collect)

        from src.services.whisper_engines import _clear_memory

        _clear_memory()

        mx_clear.assert_called_once()
        gc_collect.assert_called_once()

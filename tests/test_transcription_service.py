"""Тесты для TranscriptionService."""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_test_dir: str | None = None


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch, tmp_path):
    global _test_dir
    _test_dir = str(tmp_path)
    monkeypatch.setattr("src.services.job_manager.JOB_METADATA_DIR", os.path.join(_test_dir, "jobs"))
    os.makedirs(os.path.join(_test_dir, "jobs"), exist_ok=True)
    monkeypatch.setattr("src.config.DATA_UPLOADS_DIR", os.path.join(_test_dir, "data"))
    yield
    # Cleanup
    try:
        import shutil
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_managers():
    from src.services.transcription_queue import TranscriptionQueueManager
    TranscriptionQueueManager.reset()
    yield
    TranscriptionQueueManager.reset()


def test_submit_passes_payload_to_queue_manager():
    """submit() формирует payload из параметров и делегирует queue_manager.submit()."""
    from src.services.transcription_service import TranscriptionService
    from src.services.transcription_queue import TranscriptionQueueManager

    mock_qm = MagicMock()
    mock_qm.submit.return_value = True
    service = TranscriptionService(queue_manager=mock_qm, job_manager=MagicMock())

    job_id, success = service.submit(
        wav_path="/tmp/test.wav",
        job_id="test-1",
        original_filename="audio.mp3",
        model="turbo",
        language="ru",
        task="transcribe",
        word_timestamps=True,
        condition_on_previous_text=True,
        no_speech_threshold=0.4,
        hallucination_silence_threshold=0.8,
        initial_prompt="context",
        duration=120.5,
    )

    assert success is True
    assert job_id == "test-1"
    mock_qm.submit.assert_called_once()
    called_payload = mock_qm.submit.call_args[0][0]
    assert called_payload["job_id"] == "test-1"
    assert called_payload["wav_path"] == "/tmp/test.wav"
    assert called_payload["original_filename"] == "audio.mp3"
    assert called_payload["model"] == "turbo"
    assert called_payload["params"]["language"] == "ru"
    assert called_payload["params"]["task"] == "transcribe"
    assert called_payload["params"]["word_timestamps"] is True
    assert called_payload["duration"] == 120.5


def test_get_job_returns_metadata_and_result_when_completed(tmp_path):
    """get_job() возвращает metadata + text/segments для completed job."""
    import json

    from src.services.transcription_service import TranscriptionService
    from src.services.job_manager import JobManager, JobStatus

    jm = JobManager()
    jm.create(
        job_id="get-job-1",
        source="upload",
        original_filename="test.mp3",
        model="turbo",
    )
    jm.update_status("get-job-1", JobStatus.COMPLETED, transcription_duration=5.2)

    # Создаём job directory и файлы результатов
    job_dir = os.path.join(_test_dir, "data", "get-job-1")
    os.makedirs(job_dir, exist_ok=True)
    with open(os.path.join(job_dir, "transcription.txt"), "w", encoding="utf-8") as f:
        f.write("Hello world")
    with open(os.path.join(job_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": [{"start": 0.0, "end": 1.0, "text": "Hello world"}]}, f)

    service = TranscriptionService(
        queue_manager=MagicMock(),
        job_manager=jm,
    )

    result = service.get_job("get-job-1")
    assert result is not None
    assert result["job_id"] == "get-job-1"
    assert result["status"] == "completed"
    assert result["text"] == "Hello world"
    assert result["segments"] == [{"start": 0.0, "end": 1.0, "text": "Hello world"}]
    assert "transcription.txt" in result["files"]
    assert "segments.json" in result["files"]


def test_get_job_returns_none_for_nonexistent():
    """get_job() возвращает None для несуществующего job_id."""
    from src.services.transcription_service import TranscriptionService

    mock_jm = MagicMock()
    mock_jm.load.return_value = None
    service = TranscriptionService(
        queue_manager=MagicMock(),
        job_manager=mock_jm,
    )
    assert service.get_job("does-not-exist") is None

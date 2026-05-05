"""Тесты для TranscriptionService."""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def client(monkeypatch, isolated_dirs):
    """TestClient for the FastAPI app."""
    monkeypatch.setattr("src.config.DATA_UPLOADS_DIR", os.path.join(_test_dir, "data"))
    monkeypatch.setattr("src.config.UPLOADS_DIR", os.path.join(_test_dir, "uploads"))
    os.makedirs(os.path.join(_test_dir, "uploads"), exist_ok=True)
    from src.main import app
    return TestClient(app)


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


def test_transcribe_endpoint_submits_to_queue(client, isolated_dirs):
    """POST /transcribe возвращает job_id и status queued, вместо полного результата."""
    import os
    from unittest.mock import patch

    # Создаём тестовый аудиофайл
    test_file = os.path.join(os.path.dirname(__file__), "test.wav")
    if not os.path.exists(test_file):
        pytest.skip("test.wav not available")

    with patch("src.services.transcription_queue.get_transcription_manager") as mock_mgr:
        mock_qm = mock_mgr.return_value
        mock_qm.submit.return_value = True

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/v1/transcribe",
                files={"file": ("test.wav", f, "audio/wav")},
                data={
                    "model": "turbo",
                    "task": "transcribe",
                    "word_timestamps": "false",
                    "condition_on_previous_text": "true",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    mock_qm.submit.assert_called_once()


def test_get_job_returns_metadata(client, isolated_dirs):
    """GET /jobs/{job_id} возвращает metadata через TranscriptionService."""
    from src.services.job_manager import JobManager, JobStatus
    import json

    # Создаём job напрямую через JobManager
    jm = JobManager()
    jm.create(
        job_id="int-get-job-1",
        source="upload",
        original_filename="test.mp3",
        model="turbo",
        language="ru",
    )
    jm.update_status("int-get-job-1", JobStatus.COMPLETED, transcription_duration=3.5)

    # Создаём результат в data directory
    job_dir = os.path.join(_test_dir, "data", "int-get-job-1")
    os.makedirs(job_dir, exist_ok=True)
    with open(os.path.join(job_dir, "transcription.txt"), "w", encoding="utf-8") as f:
        f.write("integrated test result")

    response = client.get("/api/v1/jobs/int-get-job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "int-get-job-1"
    assert body["status"] == "completed"
    assert body["text"] == "integrated test result"
    assert body["model"] == "turbo"
    assert body["language"] == "ru"


def test_get_job_not_found(client, isolated_dirs):
    """GET /jobs/{job_id} для несуществующего job возвращает 404."""
    response = client.get("/api/v1/jobs/does-not-exist")
    assert response.status_code == 404


def test_list_jobs_uses_job_manager(client, isolated_dirs):
    """GET /jobs возвращает список через JobManager.list_all()."""
    from src.services.job_manager import JobManager

    jm = JobManager()
    jm.create(job_id="int-list-1", source="upload", original_filename="a.mp3", model="turbo")
    jm.create(job_id="int-list-2", source="upload", original_filename="b.mp3", model="base")

    response = client.get("/api/v1/jobs")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    job_ids = {j["job_id"] for j in body}
    assert job_ids == {"int-list-1", "int-list-2"}


def test_cancel_job_uses_queue_manager(client, isolated_dirs):
    """DELETE /jobs/{job_id} отменяет job через queue manager."""
    from src.services.job_manager import JobManager, JobStatus

    # Создаём job в статусе processing
    jm = JobManager()
    jm.create(
        job_id="int-cancel-1",
        source="upload",
        original_filename="cancel.mp3",
        model="turbo",
    )
    jm.update_status("int-cancel-1", JobStatus.PROCESSING)

    # Создаём job directory — endpoint ищет его и удаляет
    job_dir = os.path.join(_test_dir, "data", "int-cancel-1")
    os.makedirs(job_dir, exist_ok=True)

    response = client.delete("/api/v1/jobs/int-cancel-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "deleted"
    assert body["job_id"] == "int-cancel-1"

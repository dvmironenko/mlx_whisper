"""Тесты для JobManager singleton."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.job_manager import JobManager, JobStatus


@pytest.fixture
def job_manager(tmp_path):
    """Временная директория для job metadata."""
    os.environ["JOB_METADATA_DIR_OVERRIDE"] = str(tmp_path)
    import src.services.job_manager as jm

    jm.JOB_METADATA_DIR = str(tmp_path)
    yield JobManager()
    jm.JOB_METADATA_DIR = os.path.join("data", "jobs")
    del os.environ["JOB_METADATA_DIR_OVERRIDE"]


class TestJobManagerCreate:
    def test_create_default(self, job_manager):
        meta = job_manager.create(source="upload")

        assert meta["source"] == "upload"
        assert meta["status"] == "queued"
        assert "job_id" in meta
        assert "created_at" in meta
        assert "updated_at" in meta
        assert meta["original_filename"] is None
        assert meta["model"] is None
        assert meta["error"] is None

    def test_create_custom_id(self, job_manager):
        meta = job_manager.create(job_id="custom-id-123", source="url")

        assert meta["job_id"] == "custom-id-123"
        assert meta["source"] == "url"

    def test_create_persists_to_disk(self, job_manager, tmp_path):
        meta = job_manager.create(job_id="disk-test")

        job_file = tmp_path / "disk-test.json"
        assert job_file.exists()

        with open(job_file, "r") as f:
            saved = json.load(f)
        assert saved["job_id"] == "disk-test"

    def test_create_with_extra_fields(self, job_manager):
        meta = job_manager.create(
            job_id="extra-test",
            original_filename="audio.wav",
            model="turbo",
            language="ru",
        )

        assert meta["original_filename"] == "audio.wav"
        assert meta["model"] == "turbo"
        assert meta["language"] == "ru"


class TestJobManagerLoad:
    def test_load_existing(self, job_manager):
        job_manager.create(job_id="load-me", original_filename="test.wav")
        meta = job_manager.load("load-me")

        assert meta is not None
        assert meta["job_id"] == "load-me"
        assert meta["original_filename"] == "test.wav"

    def test_load_nonexistent(self, job_manager):
        meta = job_manager.load("does-not-exist")
        assert meta is None


class TestJobManagerUpdateStatus:
    def test_update_to_completed(self, job_manager):
        job_manager.create(job_id="update-me")
        meta = job_manager.update_status(
            "update-me", JobStatus.COMPLETED, transcription_duration=45.2
        )

        assert meta["status"] == "completed"
        assert meta["transcription_duration"] == 45.2

    def test_update_to_failed(self, job_manager):
        job_manager.create(job_id="fail-me")
        meta = job_manager.update_status(
            "fail-me", JobStatus.FAILED, error="ffmpeg not found"
        )

        assert meta["status"] == "failed"
        assert meta["error"] == "ffmpeg not found"

    def test_update_nonexistent_returns_none(self, job_manager):
        meta = job_manager.update_status("nope", JobStatus.COMPLETED)
        assert meta is None

    def test_update_preserves_existing_fields(self, job_manager):
        job_manager.create(
            job_id="preserve-me",
            original_filename="audio.wav",
            model="turbo",
        )
        job_manager.update_status("preserve-me", JobStatus.COMPLETED)
        meta = job_manager.load("preserve-me")

        assert meta["original_filename"] == "audio.wav"
        assert meta["model"] == "turbo"


class TestJobManagerCancel:
    def test_cancel_queued_job(self, job_manager):
        job_manager.create(job_id="cancel-me")
        meta = job_manager.cancel("cancel-me")

        assert meta["status"] == "cancelled"

    def test_cancel_nonexistent(self, job_manager):
        meta = job_manager.cancel("nope")
        assert meta is None


class TestJobManagerListAll:
    def test_list_empty(self, job_manager):
        result = job_manager.list_all()
        assert result == []

    def test_list_multiple(self, job_manager):
        job_manager.create(job_id="job-a")
        job_manager.create(job_id="job-b")
        job_manager.create(job_id="job-c")

        result = job_manager.list_all()
        assert len(result) == 3
        ids = [r["job_id"] for r in result]
        assert ids == sorted(ids)

    def test_list_mixed_statuses(self, job_manager):
        job_manager.create(job_id="a")
        job_manager.update_status("a", JobStatus.COMPLETED)
        job_manager.create(job_id="b")
        job_manager.update_status("b", JobStatus.FAILED)

        result = job_manager.list_all()
        assert len(result) == 2

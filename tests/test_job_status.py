"""Тесты для JobStatus enum."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.job_manager import JobStatus


class TestJobStatus:
    def test_enum_values(self):
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_str_conversion(self):
        assert str(JobStatus.QUEUED) == "queued"
        assert str(JobStatus.PROCESSING) == "processing"
        assert str(JobStatus.COMPLETED) == "completed"
        assert str(JobStatus.FAILED) == "failed"
        assert str(JobStatus.CANCELLED) == "cancelled"

    def test_enum_membership(self):
        assert "queued" in {s.value for s in JobStatus}
        assert "processing" in {s.value for s in JobStatus}
        assert "completed" in {s.value for s in JobStatus}
        assert "failed" in {s.value for s in JobStatus}
        assert "cancelled" in {s.value for s in JobStatus}

    def test_enum_count(self):
        assert len(JobStatus) == 5

"""Unit-тесты для tracking активных генераций отчётов."""

import threading
import time

import pytest


@pytest.fixture
def report_set():
    """Изолированный set для каждого теста."""
    s: set[str] = set()
    yield s
    s.clear()


class TestGeneratingReportsSet:
    """Тесты для managing active report generations."""

    def test_empty_initially(self, report_set):
        assert len(report_set) == 0

    def test_add_job(self, report_set):
        report_set.add("job-1")
        assert "job-1" in report_set

    def test_discard_job(self, report_set):
        report_set.add("job-2")
        report_set.discard("job-2")
        assert "job-2" not in report_set

    def test_discard_nonexistent_is_safe(self, report_set):
        report_set.discard("nonexistent")
        assert len(report_set) == 0

    def test_multiple_jobs(self, report_set):
        report_set.add("job-a")
        report_set.add("job-b")
        report_set.add("job-c")
        assert len(report_set) == 3
        report_set.discard("job-b")
        assert len(report_set) == 2

    def test_status_check(self, report_set):
        report_set.add("job-status")
        assert "job-status" in report_set
        report_set.discard("job-status")
        assert "job-status" not in report_set

    def test_thread_safety(self, report_set):
        """Concurrent add/discard should not raise exceptions."""
        errors = []

        def worker_add(job_id):
            try:
                for _ in range(100):
                    report_set.add(job_id)
                    time.sleep(0.001)
                    report_set.discard(job_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker_add, args=(f"job-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"

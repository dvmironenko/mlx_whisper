"""Integration-тест для GET /api/v1/report-status/{job_id}."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from src.api.router import router, generating_reports
from src.main import app


client = TestClient(app)


class TestReportStatusEndpoint:
    """Тесты endpoint статуса генерации отчёта."""

    def setup_method(self):
        generating_reports.clear()

    def teardown_method(self):
        generating_reports.clear()

    def test_report_status_idle(self):
        """Job не генерирует — статус idle."""
        response = client.get("/api/v1/report-status/test-job-idle")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-idle"
        assert data["status"] == "idle"

    def test_report_status_generating(self):
        """Job в процессе генерации — статус generating."""
        generating_reports.add("test-job-generating")
        response = client.get("/api/v1/report-status/test-job-generating")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-generating"
        assert data["status"] == "generating"

    def test_report_status_not_found_job(self):
        """Job не существует — статус idle."""
        response = client.get("/api/v1/report-status/nonexistent-job")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"

    def test_report_status_after_discard(self):
        """После discard job снова idle."""
        generating_reports.add("test-job-then-discard")
        generating_reports.discard("test-job-then-discard")
        response = client.get("/api/v1/report-status/test-job-then-discard")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"

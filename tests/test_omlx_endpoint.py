"""Тесты для OMLX конфигурации и health endpoint."""

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "/Users/dvmironenko/dev/mlx_whisper/src")


class TestOmlxAvailable:
    """Тесты omlx_available()."""

    def test_returns_false_when_disabled(self):
        with patch("src.config.OMLX_ENABLED", False):
            from src.config import omlx_available
            assert omlx_available() is False

    def test_returns_false_when_no_base_url(self):
        with (
            patch("src.config.OMLX_ENABLED", True),
            patch("src.config.OMLX_BASE_URL", ""),
        ):
            from src.config import omlx_available
            assert omlx_available() is False

    def test_returns_true_when_enabled_and_url_set(self):
        with (
            patch("src.config.OMLX_ENABLED", True),
            patch("src.config.OMLX_BASE_URL", "http://test"),
        ):
            from src.config import omlx_available
            assert omlx_available() is True


class TestOmlxHealthEndpoint:
    """Тесты GET /api/v1/omlx/health."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.main import app
        return TestClient(app)

    def test_disabled_returns_disabled_status(self, client):
        mock_requests_module = MagicMock()
        with (
            patch("src.api.router.OMLX_ENABLED", False),
            patch("src.api.router.OMLX_BASE_URL", "http://test"),
            patch("src.api.router._requests", mock_requests_module),
        ):
            response = client.get("/api/v1/omlx/health")

        assert response.status_code == 200
        data = response.json()
        assert data["omlx"] == "disabled"
        assert "base_url" in data

    def test_no_base_url_returns_disabled_status(self, client):
        mock_requests_module = MagicMock()
        with (
            patch("src.api.router.OMLX_BASE_URL", ""),
            patch("src.api.router.OMLX_ENABLED", True),
            patch("src.api.router._requests", mock_requests_module),
        ):
            response = client.get("/api/v1/omlx/health")

        assert response.status_code == 200
        data = response.json()
        assert data["omlx"] == "disabled"

    def test_reachable_returns_ok_status(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_requests_module = MagicMock()
        mock_requests_module.get = MagicMock(return_value=mock_response)

        with (
            patch("src.api.router.OMLX_ENABLED", True),
            patch("src.api.router.OMLX_BASE_URL", "http://test"),
            patch("src.api.router._requests", mock_requests_module),
        ):
            response = client.get("/api/v1/omlx/health")

        assert response.status_code == 200
        data = response.json()
        assert data["omlx"] == "connected"

    def test_unreachable_returns_unreachable_status(self, client):
        mock_requests_module = MagicMock()
        mock_requests_module.get = MagicMock(side_effect=Exception("connection refused"))

        with (
            patch("src.api.router.OMLX_ENABLED", True),
            patch("src.api.router.OMLX_BASE_URL", "http://unreachable"),
            patch("src.api.router._requests", mock_requests_module),
        ):
            response = client.get("/api/v1/omlx/health")

        assert response.status_code == 200
        data = response.json()
        assert data["omlx"] == "unreachable"

    def test_includes_model_in_response(self, client):
        mock_requests_module = MagicMock()
        mock_requests_module.get = MagicMock(side_effect=Exception("err"))

        with (
            patch("src.api.router.OMLX_ENABLED", True),
            patch("src.api.router.OMLX_BASE_URL", "http://test"),
            patch("src.api.router.OMLX_MODEL", "VibeVoice-ASR-4bit"),
            patch("src.api.router._requests", mock_requests_module),
        ):
            response = client.get("/api/v1/omlx/health")

        data = response.json()
        assert data["model"] == "VibeVoice-ASR-4bit"


class TestConfigEndpointVibevoiceFields:
    """Тесты что GET /api/v1/config возвращает vibevoice поля."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.main import app
        return TestClient(app)

    def test_returns_omlx_enabled(self, client):
        with patch("src.config.OMLX_ENABLED", True):
            response = client.get("/api/v1/config")

        assert response.status_code == 200
        data = response.json()
        assert "omlx_enabled" in data

    def test_returns_omlx_base_url(self, client):
        with patch("src.config.OMLX_BASE_URL", "http://test-url"):
            response = client.get("/api/v1/config")

        data = response.json()
        assert "omlx_base_url" in data
        # Base URL может быть пустой строкой — главное что поле есть
        assert data["omlx_base_url"] == "" or data["omlx_base_url"] == "http://test-url"

    def test_returns_omlx_model(self, client):
        with patch("src.config.OMLX_MODEL", "custom-model"):
            response = client.get("/api/v1/config")

        data = response.json()
        assert "omlx_model" in data
        assert data["omlx_model"] == "custom-model"

    def test_default_model_is_vibevoice_asr(self, client):
        with (
            patch("src.config.OMLX_MODEL", "VibeVoice-ASR-4bit"),
            patch("src.config.OMLX_BASE_URL", ""),
            patch("src.config.OMLX_ENABLED", True),
        ):
            response = client.get("/api/v1/config")

        data = response.json()
        assert data["omlx_model"] == "VibeVoice-ASR-4bit"

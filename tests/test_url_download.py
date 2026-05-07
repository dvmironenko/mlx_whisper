"""Тесты скачивания видео по URL."""
import pytest
from src.utils.download import validate_url, get_url_format, ALLOWED_URL_DOMAINS


class TestValidateUrl:
    """Тесты валидации URL."""

    def test_valid_youtube_url(self):
        """Валидный URL YouTube."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert validate_url(url) is True

    def test_valid_youtu_be_url(self):
        """Валидный URL youtu.be."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert validate_url(url) is True

    def test_valid_vimeo_url(self):
        """Валидный URL Vimeo."""
        url = "https://vimeo.com/123456789"
        assert validate_url(url) is True

    def test_valid_direct_mp4_url(self):
        """Валидный прямой URL на mp4."""
        url = "https://example.com/video.mp4"
        assert validate_url(url) is True

    def test_valid_direct_wav_url(self):
        """Валидный прямой URL на wav."""
        url = "https://example.com/audio.wav"
        assert validate_url(url) is True

    def test_invalid_file_protocol(self):
        """Недопустимый протокол file://."""
        url = "file:///path/to/video.mp4"
        assert validate_url(url) is False

    def test_invalid_ftp_protocol(self):
        """Недопустимый протокол ftp://."""
        url = "ftp://example.com/video.mp4"
        assert validate_url(url) is False

    def test_url_with_dangerous_characters(self):
        """URL с опасными символами."""
        url = "https://example.com/video.mp4;<script>"
        assert validate_url(url) is False

    def test_non_whitelisted_domain_direct_link(self):
        """Домен не в белом списке, но прямая ссылка на файл."""
        url = "https://other.com/audio.mp3"
        assert validate_url(url) is True

    def test_non_whitelisted_domain_no_extension(self):
        """Домен не в белом списке, нет расширения файла."""
        url = "https://other.com/page"
        assert validate_url(url) is False


class TestGetUrlFormat:
    """Тесты определения типа контента по URL."""

    def test_youtube_format(self):
        """YouTube URL."""
        url = "https://www.youtube.com/watch?v=test"
        assert get_url_format(url) == "youtube"

    def test_youtu_be_format(self):
        """youtu.be URL."""
        url = "https://youtu.be/test"
        assert get_url_format(url) == "youtube"

    def test_vimeo_format(self):
        """Vimeo URL."""
        url = "https://vimeo.com/123456"
        assert get_url_format(url) == "vimeo"

    def test_direct_mp4_format(self):
        """Прямая ссылка на mp4."""
        url = "https://example.com/video.mp4"
        assert get_url_format(url) == "direct"

    def test_direct_wav_format(self):
        """Прямая ссылка на wav."""
        url = "https://example.com/audio.wav"
        assert get_url_format(url) == "direct"

    def test_direct_m4a_format(self):
        """Прямая ссылка на m4a."""
        url = "https://example.com/audio.m4a"
        assert get_url_format(url) == "direct"

    def test_direct_webm_format(self):
        """Прямая ссылка на webm."""
        url = "https://example.com/video.webm"
        assert get_url_format(url) == "direct"

    def test_direct_mp3_format(self):
        """Прямая ссылка на mp3."""
        url = "https://example.com/audio.mp3"
        assert get_url_format(url) == "direct"

    def test_direct_flac_format(self):
        """Прямая ссылка на flac."""
        url = "https://example.com/audio.flac"
        assert get_url_format(url) == "direct"

    def test_direct_aac_format(self):
        """Прямая ссылка на aac."""
        url = "https://example.com/audio.aac"
        assert get_url_format(url) == "direct"

    def test_direct_ogg_format(self):
        """Прямая ссылка на ogg."""
        url = "https://example.com/audio.ogg"
        assert get_url_format(url) == "direct"

    def test_direct_oga_format(self):
        """Прямая ссылка на oga."""
        url = "https://example.com/audio.oga"
        assert get_url_format(url) == "direct"

    def test_direct_weba_format(self):
        """Прямая ссылка на weba."""
        url = "https://example.com/audio.weba"
        assert get_url_format(url) == "direct"

    def test_unknown_format(self):
        """Неизвестный формат."""
        url = "https://example.com/page"
        assert get_url_format(url) == "unknown"

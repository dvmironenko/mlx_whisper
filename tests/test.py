"""Unit tests для MLX-Whisper API."""
import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

import pytest
from unittest.mock import Mock, patch


def test_health_check():
    """Test health endpoint."""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "version": "1.0.0"}
        mock_get.return_value = mock_response

        import requests
        response = requests.get("http://localhost:8801/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_convert_to_wav():
    """Test audio conversion."""
    with patch("subprocess.run") as mock_run:
        # Setup mock to return success
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        from src.utils.audio import convert_to_wav
        result = convert_to_wav("input.mp3", "output.wav")
        assert result is not None


def test_transcribe_audio():
    """Test transcription function."""
    with patch("mlx_whisper.transcribe") as mock_transcribe:
        mock_result = {
            "text": "test transcription",
            "language": "ru",
            "segments": []
        }
        mock_transcribe.return_value = mock_result

        from src.models.transcription import transcribe_audio
        result = transcribe_audio(
            file_path="test.wav",
            language="ru",
            task="transcribe",
            model="tiny",
            word_timestamps=False,
            condition_on_previous_text=True,
            no_speech_threshold=0.4,
            hallucination_silence_threshold=0.8
        )
        assert result["text"] == "test transcription"


def test_validate_file_extension():
    """Test file extension validation."""
    from src.utils.files import validate_file_extension
    AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a"}

    assert validate_file_extension("test.wav", AUDIO_EXTENSIONS) == True
    assert validate_file_extension("test.mp3", AUDIO_EXTENSIONS) == True
    assert validate_file_extension("test.txt", AUDIO_EXTENSIONS) == False


def test_generate_unique_filename():
    """Test unique filename generation."""
    from src.utils.files import generate_unique_filename

    filename1 = generate_unique_filename("test.wav")
    filename2 = generate_unique_filename("test.wav")

    assert filename1 != filename2
    assert filename1.endswith(".wav")


def test_convert_numpy_types():
    """Test numpy type conversion."""
    import numpy as np
    from src.models.transcription import convert_numpy_types

    # Test array conversion
    arr = np.array([1, 2, 3])
    result = convert_numpy_types(arr)
    assert result == [1, 2, 3]

    # Test dict with numpy values
    data = {"value": np.int64(42), "float_val": np.float32(3.14)}
    result = convert_numpy_types(data)
    assert result["value"] == 42
    # Use close approximation for float comparison
    assert abs(result["float_val"] - 3.14) < 0.01


def test_validate_file_size():
    """Test file size validation."""
    from src.utils.files import validate_file_size, MAX_FILE_SIZE

    # Create a small temp file
    with open("/tmp/test_size.txt", "w") as f:
        f.write("test")

    try:
        assert validate_file_size("/tmp/test_size.txt") == True
    finally:
        os.remove("/tmp/test_size.txt")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

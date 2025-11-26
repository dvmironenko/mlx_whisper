# src/test.py (обновленная версия)
import requests
import os

def test_health_check():
    """Test health endpoint"""
    response1 = requests.get("http://localhost:8801/health")
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "healthy"
    
    response2 = requests.get("http://localhost:8801/health")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "healthy"
    
    print("✓ Health check passed")
    
def test_get_models():
    """Test models endpoint"""

    response = requests.get("http://localhost:8801/models")
    assert response.status_code == 200
    data = response.json()
    assert "supported_models" in data
    assert len(data["supported_models"]) > 0
    print("✓ Models endpoint passed")
    print(f"Supported models: {data['supported_models']}")

def test_transcribe_audio():
    """Test transcription with sample file"""

    test_file = "tests/test.wav"
    
    if not os.path.exists(test_file):
        print(f"Warning: Test file {test_file} not found. Skipping transcription test.")
        # Выводим информацию о том, какие параметры поддерживаются
        print("Note: To run full transcription test, create a test.wav file")
        return
    
    # Выводим параметры вызова эндпоинта
    print("Transcription parameters:")
    print("  language: ru")
    print("  task: transcribe")
    print("  model: turbo")
    print("  word_timestamps: False")
    print("  condition_on_previous_text: True")
    print("  no_speech_threshold: 0.4")
    print("  hallucination_silence_threshold: 0.8")
    
    with open(test_file, "rb") as f:
        response = requests.post(
            "http://localhost:8801/transcribe",
            files={"file": f},
            data={
                "language": "ru",
                "task": "transcribe", 
                "model": "turbo",

                "word_timestamps": False,
                "condition_on_previous_text": True,
                "no_speech_threshold": 0.4,
                "hallucination_silence_threshold": 0.8
            }
        )
        
    assert response.status_code == 200
    data = response.json()
    
    # Validate response structure
    assert "text" in data
    assert "language" in data
    assert "model" in data
    assert "segments" in data
    assert "task" in data
    
    # Validate content
    assert len(data["text"]) > 0, "Transcription result should not be empty"
    
    print("✓ Transcription test passed")
    print(f"Transcribed text: {data['text'][:100]}...")

if __name__ == "__main__":
    print("Running MLX-Whisper API tests...")
    
    test_health_check()
    test_get_models()
    test_transcribe_audio()
    
    print("\nAll tests completed!")

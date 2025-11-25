# src/test.py (обновленная версия)
import requests
import os

def test_health_check():
    """Test health endpoint"""
    response = requests.get("http://localhost:8801/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print("✓ Health check passed")

def test_get_models():
    """Test models endpoint"""
    response = requests.get("http://localhost:8801/models")
    assert response.status_code == 200
    data = response.json()
    assert "supported_models" in data
    assert len(data["supported_models"]) > 0
    print("✓ Models endpoint passed")

def test_transcribe_audio():
    """Test transcription with sample file"""
    test_file = "Test.mp3"
    
    if not os.path.exists(test_file):
        print(f"Warning: Test file {test_file} not found. Skipping transcription test.")
        return
    
    with open(test_file, "rb") as f:
        response = requests.post(
            "http://localhost:8801/transcribe",
            files={"file": f},
            data={
                "language": "ru",
                "task": "transcribe", 
                "model": "base",
                "word_timestamps": "true"
            }
        )
        
    assert response.status_code == 200
    data = response.json()
    
    # Validate response structure
    assert "text" in data
    assert "language" in data
    assert "model" in data
    assert "segments" in data
    
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
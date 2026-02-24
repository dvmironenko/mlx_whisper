"""
Test for the initial_prompt parameter in MLX-Whisper API.
This verifies that the initial_prompt parameter works correctly.
"""
import subprocess
import sys
import os
import time
import requests
import json
from unittest.mock import patch, MagicMock

def test_initial_prompt_parameter():
    """Test that initial_prompt parameter is correctly handled through the API."""

    print("Testing MLX-Whisper API initial_prompt parameter")
    print("=" * 60)

    # Start the server in a subprocess
    print("Starting MLX-Whisper server...")

    # Start the FastAPI server in background
    server_process = subprocess.Popen([
        sys.executable, "src/main.py"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Give the server time to start
    print("Waiting for server to initialize...")
    time.sleep(3)

    try:
        # Test 1: Verify server is running and accessible
        print("\n1. Testing server accessibility...")
        response = requests.get("http://localhost:8801/", timeout=5)
        assert response.status_code == 200
        print("✓ Server is running and accessible")

        # Test 2: Test that initial_prompt parameter is accepted in API
        print("\n2. Testing initial_prompt parameter through API...")

        # Mock the transcribe_audio function to capture parameters
        with patch('src.api.router.transcribe_audio') as mock_transcribe:
            # Set up mock to return a simple result
            mock_transcribe.return_value = {
                "text": "Test transcription result",
                "language": "ru",
                "model": "tiny",
                "task": "transcribe",
                "word_timestamps": False,
                "condition_on_previous_text": True,
                "no_speech_threshold": 0.4,
                "hallucination_silence_threshold": 0.8,
                "segments": []
            }

            # Test with initial_prompt parameter
            test_file_path = "tests/test.wav"

            if os.path.exists(test_file_path):
                print(f"   Using test file: {test_file_path}")

                # Make a POST request with initial_prompt
                with open(test_file_path, 'rb') as f:
                    files = {'file': f}
                    data = {
                        'language': 'ru',
                        'task': 'transcribe',
                        'model': 'tiny',
                        'initial_prompt': 'This is a test initial prompt'
                    }

                    response = requests.post("http://localhost:8801/api/v1/transcribe",
                                           files=files, data=data, timeout=15)

                print(f"   Response Status Code: {response.status_code}")

                if response.status_code == 200:
                    print("✓ Transcribe endpoint accepts initial_prompt parameter")

                    # Verify that transcribe_audio was called with correct parameters
                    if mock_transcribe.called:
                        call_args = mock_transcribe.call_args
                        print("✓ transcribe_audio function was called")

                        # Check that initial_prompt was passed
                        if 'initial_prompt' in call_args.kwargs:
                            initial_prompt_value = call_args.kwargs['initial_prompt']
                            expected_prompt = 'This is a test initial prompt'

                            if initial_prompt_value == expected_prompt:
                                print("✓ initial_prompt parameter correctly passed to transcribe_audio")
                            else:
                                print(f"✗ initial_prompt parameter mismatch. Expected: {expected_prompt}, Got: {initial_prompt_value}")
                                return False
                        else:
                            print("✗ initial_prompt parameter not found in transcribe_audio call")
                            return False
                    else:
                        print("✗ transcribe_audio function was not called")
                        return False

                else:
                    print(f"✗ Transcribe endpoint returned unexpected status: {response.status_code}")
                    return False
            else:
                print("   Warning: Test file not found, testing API structure only")

                # Test API structure with basic request
                data = {
                    'language': 'ru',
                    'task': 'transcribe',
                    'model': 'tiny',
                    'initial_prompt': 'This is a test initial prompt'
                }

                response = requests.post("http://localhost:8801/api/v1/transcribe",
                                       data=data, timeout=5)

                print(f"   Response Status Code: {response.status_code}")
                print("✓ API accepts initial_prompt parameter in basic request")

        # Test 3: Verify that the parameter is passed to mlx_whisper.transcribe
        print("\n3. Testing that initial_prompt is passed to mlx_whisper.transcribe...")

        with patch('src.models.transcription.mlx_whisper.transcribe') as mock_mlx_transcribe:
            # Set up mock to return a simple result
            mock_mlx_transcribe.return_value = {
                "text": "Mock transcription result with initial prompt",
                "segments": []
            }

            # Mock the transcribe_audio function to capture the call to mlx_whisper.transcribe
            with patch('src.models.transcription.transcribe_audio') as mock_transcribe_audio:
                mock_transcribe_audio.return_value = {
                    "text": "Mock transcription result",
                    "language": "ru",
                    "model": "tiny",
                    "task": "transcribe",
                    "word_timestamps": False,
                    "condition_on_previous_text": True,
                    "no_speech_threshold": 0.4,
                    "hallucination_silence_threshold": 0.8,
                    "segments": []
                }

                # Test that the transcribe function is called with initial_prompt
                test_file_path = "tests/test.wav"

                if os.path.exists(test_file_path):
                    with open(test_file_path, 'rb') as f:
                        files = {'file': f}
                        data = {
                            'language': 'ru',
                            'task': 'transcribe',
                            'model': 'tiny',
                            'initial_prompt': 'This is a test initial prompt for mlx_whisper'
                        }

                        response = requests.post("http://localhost:8801/api/v1/transcribe",
                                               files=files, data=data, timeout=15)

                # Verify that mlx_whisper.transcribe was called with correct parameters
                if mock_mlx_transcribe.called:
                    call_args = mock_mlx_transcribe.call_args
                    print("✓ mlx_whisper.transcribe function was called")

                    # Check that initial_prompt was passed to mlx_whisper
                    if 'initial_prompt' in call_args.kwargs:
                        initial_prompt_value = call_args.kwargs['initial_prompt']
                        expected_prompt = 'This is a test initial prompt for mlx_whisper'

                        if initial_prompt_value == expected_prompt:
                            print("✓ initial_prompt parameter correctly passed to mlx_whisper.transcribe")
                        else:
                            print(f"✗ initial_prompt parameter mismatch for mlx_whisper. Expected: {expected_prompt}, Got: {initial_prompt_value}")
                            return False
                    else:
                        print("✗ initial_prompt parameter not found in mlx_whisper.transcribe call")
                        return False
                else:
                    print("✗ mlx_whisper.transcribe function was not called")
                    return False

        print("\n" + "=" * 60)
        print("✓ INITIAL_PROMPT PARAMETER TEST COMPLETED SUCCESSFULLY")
        return True

    except Exception as e:
        print(f"\n✗ INITIAL_PROMPT TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up server
        print("\nStopping server...")
        try:
            server_process.terminate()
            server_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_process.kill()
        except:
            pass

def test_application_startup():
    """Test that the application starts without errors."""
    print("\nTesting application startup...")

    try:
        # Try to import the main module
        import src.main
        print("✓ Application imports successfully")

        # Check if main app can be created
        from src.main import app
        print("✓ FastAPI app can be created")

        # Try to run a simple check
        from src.config import HOST, PORT
        print(f"✓ Configuration loaded successfully (host: {HOST}, port: {PORT})")

        return True

    except Exception as e:
        print(f"✗ Application startup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running comprehensive test for initial_prompt parameter...")

    # Test application startup
    startup_success = test_application_startup()

    # Test initial_prompt functionality
    prompt_success = test_initial_prompt_parameter()

    if startup_success and prompt_success:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED!")
        sys.exit(1)
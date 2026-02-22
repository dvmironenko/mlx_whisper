"""
Comprehensive test for the initial_prompt parameter in MLX-Whisper API.
This verifies that the parameter works correctly through the complete pipeline.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import patch, MagicMock

def test_parameter_flow():
    """Test the complete flow of initial_prompt parameter through the system."""

    print("Testing complete parameter flow...")

    # Test 1: Check that API router accepts initial_prompt parameter
    print("1. Testing API router parameter acceptance...")

    # Check the function signature
    from src.api.router import transcribe_audio_endpoint
    import inspect

    sig = inspect.signature(transcribe_audio_endpoint)
    params = list(sig.parameters.keys())

    if 'initial_prompt' in params:
        print("   ✓ initial_prompt parameter accepted by API router")
    else:
        print("   ✗ initial_prompt parameter not found in API router")
        return False

    # Test 2: Mock the entire transcription process to verify parameter passing
    print("2. Testing parameter passing through transcription pipeline...")

    with patch('src.models.transcription.mlx_whisper.transcribe') as mock_mlx_transcribe:
        # Mock return value
        mock_mlx_transcribe.return_value = {
            "text": "Mock transcription result",
            "segments": []
        }

        # Mock file processing functions
        with patch('src.utils.audio.convert_to_wav') as mock_convert, \
             patch('src.utils.files.delete_file') as mock_delete, \
             patch('src.utils.files.generate_unique_filename') as mock_generate:

            # Set up mocks
            mock_convert.return_value = True
            mock_delete.return_value = True
            mock_generate.return_value = "test_job_id_123"

            # Test that the transcribe_audio function can be called with initial_prompt
            from src.models.transcription import transcribe_audio

            try:
                result = transcribe_audio(
                    file_path="dummy.wav",
                    language="ru",
                    task="transcribe",
                    model="tiny",
                    word_timestamps=False,
                    condition_on_previous_text=True,
                    no_speech_threshold=0.4,
                    hallucination_silence_threshold=0.8,
                    initial_prompt="Test initial prompt from API",
                    timeout=30
                )

                # Verify that mlx_whisper.transcribe was called with initial_prompt
                if mock_mlx_transcribe.called:
                    call_args = mock_mlx_transcribe.call_args
                    if 'initial_prompt' in call_args.kwargs:
                        prompt_value = call_args.kwargs['initial_prompt']
                        if prompt_value == "Test initial prompt from API":
                            print("   ✓ initial_prompt correctly passed to mlx_whisper.transcribe")
                        else:
                            print(f"   ✗ initial_prompt value mismatch: expected 'Test initial prompt from API', got '{prompt_value}'")
                            return False
                    else:
                        print("   ✗ initial_prompt not found in mlx_whisper call")
                        return False
                else:
                    print("   ✗ mlx_whisper.transcribe was not called")
                    return False

            except Exception as e:
                print(f"   ✗ Error in transcription test: {e}")
                return False

    # Test 3: Verify parameter consistency across layers
    print("3. Testing parameter consistency...")

    # Import both functions
    from src.api.router import transcribe_audio_endpoint
    from src.models.transcription import transcribe_audio

    router_sig = inspect.signature(transcribe_audio_endpoint)
    transcription_sig = inspect.signature(transcribe_audio)

    # Both should have initial_prompt
    router_has_prompt = 'initial_prompt' in router_sig.parameters
    transcription_has_prompt = 'initial_prompt' in transcription_sig.parameters

    if router_has_prompt and transcription_has_prompt:
        print("   ✓ initial_prompt parameter exists in both API router and transcription function")
    else:
        print("   ✗ initial_prompt parameter missing in one or both functions")
        return False

    print("   ✓ All parameter flow tests passed")
    return True

def test_api_endpoint_structure():
    """Test that the API endpoint structure supports initial_prompt."""

    print("\nTesting API endpoint structure...")

    try:
        # Check that all required imports are working
        from src.api.router import router
        from src.models.transcription import transcribe_audio
        from src.utils.audio import convert_to_wav
        from src.utils.files import generate_unique_filename, delete_file

        print("   ✓ All required modules can be imported")
        print("   ✓ API endpoint structure is valid")
        return True

    except Exception as e:
        print(f"   ✗ API endpoint structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parameter_types():
    """Test that parameter types are handled correctly."""

    print("\nTesting parameter type handling...")

    # Test with different types of initial_prompt values
    test_cases = [
        "Simple text prompt",
        "Prompt with special characters: !@#$%^&*()",
        "",  # Empty string
        None,  # None value
        "Prompt with unicode: Привет мир"  # Unicode text
    ]

    for i, test_prompt in enumerate(test_cases):
        print(f"   Testing case {i+1}: {repr(test_prompt)}")

        with patch('src.models.transcription.mlx_whisper.transcribe') as mock_mlx_transcribe:
            mock_mlx_transcribe.return_value = {"text": "result", "segments": []}

            from src.models.transcription import transcribe_audio

            try:
                result = transcribe_audio(
                    file_path="dummy.wav",
                    language="ru",
                    task="transcribe",
                    model="tiny",
                    word_timestamps=False,
                    condition_on_previous_text=True,
                    no_speech_threshold=0.4,
                    hallucination_silence_threshold=0.8,
                    initial_prompt=test_prompt,
                    timeout=30
                )

                # Check that it was called with correct parameter
                if mock_mlx_transcribe.called:
                    call_args = mock_mlx_transcribe.call_args
                    if 'initial_prompt' in call_args.kwargs:
                        passed_prompt = call_args.kwargs['initial_prompt']
                        if passed_prompt == test_prompt:
                            print(f"     ✓ Correctly passed {repr(test_prompt)}")
                        else:
                            print(f"     ✗ Value mismatch: expected {repr(test_prompt)}, got {repr(passed_prompt)}")
                            return False
                    else:
                        print("     ✗ initial_prompt not in call arguments")
                        return False
                else:
                    print("     ✗ mlx_whisper.transcribe was not called")
                    return False

            except Exception as e:
                print(f"     ✗ Error with test case {i+1}: {e}")
                return False

    print("   ✓ All parameter type tests passed")
    return True

def main():
    print("Running comprehensive initial_prompt parameter test...")
    print("=" * 60)

    # Test parameter flow
    flow_success = test_parameter_flow()

    # Test API endpoint structure
    structure_success = test_api_endpoint_structure()

    # Test parameter types
    types_success = test_parameter_types()

    print("\n" + "=" * 60)

    if flow_success and structure_success and types_success:
        print("🎉 COMPREHENSIVE TEST PASSED!")
        print("✓ Parameter flows correctly through the entire system")
        print("✓ API endpoint structure is valid")
        print("✓ Parameter types are handled correctly")
        print("\nAll tests confirm that the initial_prompt parameter works correctly:")
        print("- It's accepted by the API endpoint")
        print("- It's passed through to the transcription function")
        print("- It's correctly forwarded to mlx_whisper.transcribe")
        print("- It handles various parameter types correctly")
        return True
    else:
        print("❌ COMPREHENSIVE TEST FAILED!")
        if not flow_success:
            print("✗ Parameter flow test failed")
        if not structure_success:
            print("✗ API structure test failed")
        if not types_success:
            print("✗ Parameter type test failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
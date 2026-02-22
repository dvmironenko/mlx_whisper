"""
Simple test for the initial_prompt parameter in MLX-Whisper API.
This test verifies the parameter handling logic without starting the server.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import patch, MagicMock

def test_initial_prompt_in_router():
    """Test that initial_prompt parameter is correctly defined in API router."""

    print("Testing initial_prompt parameter definition in API router...")

    try:
        # Import the router to check the function signature
        from src.api.router import transcribe_audio_endpoint
        import inspect

        # Get function signature
        sig = inspect.signature(transcribe_audio_endpoint)
        params = list(sig.parameters.keys())

        print(f"  Router function parameters: {params}")

        # Check that initial_prompt is in the parameters
        if 'initial_prompt' in params:
            print("  ✓ initial_prompt parameter found in router function")

            # Check that it's defined as a Form parameter
            param = sig.parameters['initial_prompt']
            if param.default is None:
                print("  ✓ initial_prompt parameter correctly defined as optional")
            else:
                print(f"  ⚠ initial_prompt parameter has default: {param.default}")

            return True
        else:
            print("  ✗ initial_prompt parameter not found in router function")
            return False

    except Exception as e:
        print(f"  ✗ Error in router parameter test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_initial_prompt_in_transcription_module():
    """Test that initial_prompt parameter is correctly passed to mlx_whisper.transcribe."""

    print("\nTesting initial_prompt parameter handling in transcription module...")

    # Mock mlx_whisper.transcribe to verify it's called with correct parameters
    with patch('src.models.transcription.mlx_whisper.transcribe') as mock_mlx_transcribe:
        # Set up mock to return a simple result
        mock_mlx_transcribe.return_value = {
            "text": "Mock transcription result with initial prompt",
            "segments": []
        }

        # Import the transcription function
        from src.models.transcription import transcribe_audio

        # Test with initial_prompt parameter
        print("  Testing transcribe_audio with initial_prompt...")

        try:
            # Call transcribe_audio with initial_prompt
            result = transcribe_audio(
                file_path="dummy.wav",
                language="ru",
                task="transcribe",
                model="tiny",
                word_timestamps=False,
                condition_on_previous_text=True,
                no_speech_threshold=0.4,
                hallucination_silence_threshold=0.8,
                initial_prompt="This is a test initial prompt for mlx_whisper",
                timeout=30
            )

            # Verify that mlx_whisper.transcribe was called with the correct parameters
            assert mock_mlx_transcribe.called, "mlx_whisper.transcribe should be called"

            call_args = mock_mlx_transcribe.call_args
            print("  ✓ mlx_whisper.transcribe called successfully")

            # Check that initial_prompt was passed correctly
            assert 'initial_prompt' in call_args.kwargs, "initial_prompt should be in mlx_whisper kwargs"
            assert call_args.kwargs['initial_prompt'] == "This is a test initial prompt for mlx_whisper", \
                "initial_prompt value should match"

            print("  ✓ initial_prompt parameter correctly passed to mlx_whisper.transcribe")
            return True

        except Exception as e:
            print(f"  ✗ Error in transcription module test: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_application_startup():
    """Test that the application starts without errors."""

    print("\nTesting application startup...")

    try:
        # Try to import the main module
        import src.main
        print("  ✓ Application imports successfully")

        # Check if main app can be created
        from src.main import app
        print("  ✓ FastAPI app can be created")

        # Try to run a simple check
        from src.config import HOST, PORT
        print(f"  ✓ Configuration loaded successfully (host: {HOST}, port: {PORT})")

        return True

    except Exception as e:
        print(f"  ✗ Application startup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parameter_consistency():
    """Test that parameter names and types are consistent between layers."""

    print("\nTesting parameter consistency...")

    try:
        # Check that all functions have consistent parameter names
        from src.api.router import transcribe_audio_endpoint
        from src.models.transcription import transcribe_audio

        import inspect

        router_sig = inspect.signature(transcribe_audio_endpoint)
        transcription_sig = inspect.signature(transcribe_audio)

        print("  Router function parameters:", list(router_sig.parameters.keys()))
        print("  Transcription function parameters:", list(transcription_sig.parameters.keys()))

        # Check that initial_prompt is present in both
        router_has_initial_prompt = 'initial_prompt' in router_sig.parameters
        transcription_has_initial_prompt = 'initial_prompt' in transcription_sig.parameters

        if router_has_initial_prompt and transcription_has_initial_prompt:
            print("  ✓ initial_prompt parameter exists in both router and transcription functions")
            return True
        else:
            print("  ✗ initial_prompt parameter missing in one or both functions")
            return False

    except Exception as e:
        print(f"  ✗ Error in parameter consistency test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running simple test for initial_prompt parameter...")
    print("=" * 60)

    # Test application startup
    startup_success = test_application_startup()

    # Test parameter structure
    structure_success = test_initial_prompt_in_router()

    # Test transcription module parameter handling
    transcription_success = test_initial_prompt_in_transcription_module()

    # Test parameter consistency
    consistency_success = test_parameter_consistency()

    print("\n" + "=" * 60)

    if startup_success and structure_success and transcription_success and consistency_success:
        print("🎉 ALL TESTS PASSED!")
        print("✓ Application starts without errors")
        print("✓ Parameter structure is correct")
        print("✓ initial_prompt parameter correctly defined in router")
        print("✓ initial_prompt parameter correctly passed to mlx_whisper")
        print("✓ Parameter consistency verified")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED!")
        if not startup_success:
            print("✗ Application startup failed")
        if not structure_success:
            print("✗ Router parameter structure failed")
        if not transcription_success:
            print("✗ Transcription module parameter handling failed")
        if not consistency_success:
            print("✗ Parameter consistency failed")
        sys.exit(1)
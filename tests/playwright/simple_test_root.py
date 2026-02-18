"""
Simple test for the "/" endpoint of MLX-Whisper API.
This test verifies that the web interface loads correctly via HTTP request.
"""
import requests
import sys
import os
import subprocess
import time
import threading

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_root_endpoint():
    """Test the root endpoint (/) to ensure web interface loads correctly."""
    
    # Start the FastAPI server in a separate thread
    def start_server():
        server_process = subprocess.Popen([
            sys.executable, "src/main.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return server_process
    
    # Start the server
    server_process = start_server()
    
    # Give the server time to start
    time.sleep(3)
    
    try:
        # Make HTTP request to the root endpoint
        response = requests.get("http://localhost:8801/")
        
        # Verify the response status
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        
        # Verify the response contains expected HTML elements
        html_content = response.text
        
        # Check that key elements of the web interface are present
        assert "MLX-Whisper Audio Transcription" in html_content, "Title not found in response"
        assert "<form id=\"uploadForm\"" in html_content, "Upload form not found in response"
        assert "<h1>MLX-Whisper Audio Transcription</h1>" in html_content, "Main header not found"
        assert "<input type=\"file\" id=\"audioFile\"" in html_content, "File input not found"
        assert "<select id=\"language\"" in html_content, "Language select not found"
        assert "<select id=\"task\"" in html_content, "Task select not found"
        assert "<select id=\"model\"" in html_content, "Model select not found"
        assert "<button type=\"submit\">Транскрибировать</button>" in html_content, "Submit button not found"
        
        print("SUCCESS: The root endpoint (/) returns valid HTML with all expected elements.")
        print(f"Response status code: {response.status_code}")
        print(f"Content length: {len(html_content)} characters")
        
    except Exception as e:
        print(f"FAILED: Test failed with error: {e}")
        raise
    finally:
        # Kill the server process
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
        except:
            # If it doesn't terminate gracefully, kill it
            server_process.kill()

if __name__ == "__main__":
    test_root_endpoint()
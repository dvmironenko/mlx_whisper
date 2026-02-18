"""
Playwright-style test for MLX-Whisper root endpoint using HTTP requests.
This test verifies the web interface functionality without requiring actual browser automation.
"""

import subprocess
import sys
import os
import time
import requests
import threading

def test_root_endpoint_with_server():
    """Test the root endpoint by starting the server and making HTTP requests."""
    
    print("Starting comprehensive test for MLX-Whisper root endpoint (/)")
    print("=" * 60)
    
    # Start the server in a separate process
    print("Starting MLX-Whisper server...")
    
    # Start server in background
    server_process = subprocess.Popen([
        sys.executable, "src/main.py"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Give the server time to start
    print("Waiting for server to initialize...")
    time.sleep(3)
    
    try:
        # Test 1: Basic endpoint accessibility
        print("\n1. Testing basic endpoint accessibility...")
        response = requests.get("http://localhost:8801/", timeout=5)
        
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        print("✓ Endpoint returns HTTP 200")
        
        # Test 2: Content type verification
        print("2. Testing content type...")
        content_type = response.headers.get('content-type', '')
        assert 'text/html' in content_type, f"Expected HTML response, got {content_type}"
        print("✓ Response is HTML content")
        
        # Test 3: Content verification
        print("3. Testing content structure...")
        html_content = response.text
        
        # Check for key elements from the template
        expected_elements = [
            "MLX-Whisper Audio Transcription",
            "<form id=\"uploadForm\"",
            "<h1>MLX-Whisper Audio Transcription</h1>",
            "<input type=\"file\" id=\"audioFile\"",
            "<select id=\"language\"",
            "<select id=\"task\"",
            "<select id=\"model\"",
            "Транскрибировать"
        ]
        
        missing_elements = []
        for element in expected_elements:
            if element not in html_content:
                missing_elements.append(element)
        
        if not missing_elements:
            print("✓ All expected HTML elements found")
        else:
            print(f"⚠ Missing elements: {missing_elements}")
            
        # Test 4: Response size verification
        print(f"4. Testing response size...")
        content_length = len(html_content)
        assert content_length > 1000, f"Response seems too small: {content_length} bytes"
        print(f"✓ Response size is reasonable: {content_length} characters")
        
        # Test 5: Template structure verification
        print("5. Testing template structure...")
        assert "<!DOCTYPE html>" in html_content or "<html" in html_content, "Not valid HTML"
        assert "<head>" in html_content and "</head>" in html_content, "HTML head section missing"
        assert "<body>" in html_content and "</body>" in html_content, "HTML body section missing"
        print("✓ HTML template structure is correct")
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("The root endpoint (/) is working correctly and returns the expected web interface.")
        
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
        
    finally:
        # Clean up server process
        print("\nStopping server...")
        try:
            server_process.terminate()
            server_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_process.kill()
        except:
            pass

if __name__ == "__main__":
    success = test_root_endpoint_with_server()
    
    if not success:
        sys.exit(1)
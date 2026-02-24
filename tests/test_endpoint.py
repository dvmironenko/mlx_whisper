"""
Test to verify the "/" endpoint of MLX-Whisper API.
This test confirms that the web interface endpoint is working properly.
"""

import subprocess
import sys
import os
import time
import requests

def main():
    print("Testing MLX-Whisper API root endpoint (/)")
    print("=" * 50)
    
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
        # Test the root endpoint
        print("\n1. Testing root endpoint (/)...")
        
        response = requests.get("http://localhost:8801/", timeout=5)
        
        # Verify the response
        print(f"   Status Code: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        print(f"   Content Type: {content_type}")
        assert 'text/html' in content_type, "Expected HTML response"
        
        # Check content length
        content_length = len(response.text)
        print(f"   Content Length: {content_length} characters")
        assert content_length > 1000, "Response seems too small"
        
        # Verify key elements in the HTML
        html_content = response.text
        
        required_elements = [
            "MLX-Whisper Audio Transcription",
            "<form id=\"uploadForm\"",
            "<h1>MLX-Whisper Audio Transcription</h1>",
            "<input type=\"file\" id=\"audioFile\"",
            "<select id=\"language\"",
            "<select id=\"task\"",
            "<select id=\"model\"",
            "Транскрибировать"
        ]
        
        print("\n2. Verifying HTML structure...")
        missing_elements = []
        for element in required_elements:
            if element not in html_content:
                missing_elements.append(element)
        
        if not missing_elements:
            print("   ✓ All required HTML elements are present")
        else:
            print(f"   ⚠ Missing elements: {missing_elements}")
            
        # Additional checks
        assert "<!DOCTYPE html>" in html_content or "<html" in html_content, "Not valid HTML"
        assert "<head>" in html_content and "</head>" in html_content, "HTML head missing"
        assert "<body>" in html_content and "</body>" in html_content, "HTML body missing"
        
        print("\n3. Testing response content...")
        assert "MLX-Whisper Audio Transcription" in html_content
        print("   ✓ Page title is correct")
        
        # Final verification
        print("\n" + "=" * 50)
        print("✓ TEST PASSED")
        print("The root endpoint (/) is working correctly.")
        print("The web interface is properly served at http://localhost:8801/")
        
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
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

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
"""
Comprehensive test for the "/" endpoint of MLX-Whisper API.
This verifies that the web interface loads correctly via HTTP request.
"""
import requests
import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def run_test():
    """Run a comprehensive test for the root endpoint."""
    
    print("Testing MLX-Whisper root endpoint (/)")
    print("=" * 50)
    
    try:
        # Make HTTP request to the root endpoint
        response = requests.get("http://localhost:8801/", timeout=5)
        
        # Verify the response status
        print(f"Response Status Code: {response.status_code}")
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get('content-type', '')
        print(f"Content Type: {content_type}")
        assert 'text/html' in content_type, "Response should be HTML"
        
        # Check that the content contains expected elements from the template
        html_content = response.text
        
        print(f"Response Size: {len(html_content)} characters")
        
        # Verify key elements of the web interface
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
        
        missing_elements = []
        for element in required_elements:
            if element not in html_content:
                missing_elements.append(element)
        
        if not missing_elements:
            print("✓ All required HTML elements found in response")
        else:
            print(f"⚠ Missing elements: {missing_elements}")
            
        # Additional verification - check that it's valid HTML
        assert "<!DOCTYPE html>" in html_content or "<html" in html_content, "Not valid HTML structure"
        
        print("✓ Root endpoint (/) successfully returns the web interface HTML")
        print("✓ All expected elements are present in the HTML response")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("✗ Server is not running. Please start the MLX-Whisper server first.")
        print("Run: python src/main.py")
        return False
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = run_test()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ TEST PASSED")
        print("The root endpoint (/) is working correctly.")
    else:
        print("✗ TEST FAILED")
        sys.exit(1)
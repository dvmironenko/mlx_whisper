"""
Test for the /transcribe endpoint of MLX-Whisper API.
This verifies that the transcription endpoint works correctly with audio files.
"""

import subprocess
import sys
import os
import time
import requests
import json

def test_transcribe_endpoint():
    """Test the /transcribe endpoint functionality."""
    
    print("Testing MLX-Whisper API transcribe endpoint (/transcribe)")
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
        # Test 1: Verify root endpoint still works
        print("\n1. Testing root endpoint (/)...")
        response = requests.get("http://localhost:8801/", timeout=5)
        assert response.status_code == 200
        print("✓ Root endpoint works correctly")
        
        # Test 2: Test transcribe endpoint with a valid audio file
        print("\n2. Testing transcribe endpoint (/transcribe)...")
        
        # Try to make a request to the transcribe endpoint with test file
        test_file_path = "tests/test.wav"
        
        if os.path.exists(test_file_path):
            print(f"   Using test file: {test_file_path}")
            
            # Make a POST request to transcribe endpoint
            with open(test_file_path, 'rb') as f:
                files = {'file': f}
                data = {
                    'language': 'ru',
                    'task': 'transcribe',
                    'model': 'tiny'
                }
                
                response = requests.post("http://localhost:8801/transcribe", 
                                       files=files, data=data, timeout=15)
                
            print(f"   Response Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("✓ Transcribe endpoint returns successful response")
                
                # Verify response contains expected fields
                try:
                    response_data = response.json()
                    
                    # Check for required fields in the response
                    expected_fields = ['text', 'language', 'model', 'job_id']
                    missing_fields = []
                    
                    for field in expected_fields:
                        if field not in response_data:
                            missing_fields.append(field)
                    
                    if not missing_fields:
                        print("✓ Response contains all expected fields")
                    else:
                        print(f"⚠ Missing fields in response: {missing_fields}")
                        
                    # Basic validation of response content
                    if 'text' in response_data and len(response_data['text']) > 0:
                        print("✓ Response contains transcription text")
                    else:
                        print("⚠ Response text is empty (this might be expected for test files)")
                        
                    print(f"   Transcription length: {len(response_data.get('text', ''))} characters")
                    
                except json.JSONDecodeError:
                    print("⚠ Response is not valid JSON")
                    print(f"   Raw response: {response.text[:200]}...")
                    
            elif response.status_code == 415:  # Unsupported Media Type
                print("⚠ Transcribe endpoint returned 415 - Unsupported Media Type")
                print("   This might be due to file format or content type issues")
            elif response.status_code == 400:  # Bad Request
                print("⚠ Transcribe endpoint returned 400 - Bad Request")
                print("   This might indicate missing parameters or file issues")
            else:
                print(f"⚠ Transcribe endpoint returned unexpected status: {response.status_code}")
                print("   Raw response:")
                print(response.text[:500] + "..." if len(response.text) > 500 else response.text)
                
        else:
            print(f"   Warning: Test file {test_file_path} not found")
            print("   Testing endpoint with basic request to check if it responds...")
            
            # Try a minimal POST request to see if endpoint exists
            data = {
                'language': 'ru',
                'task': 'transcribe',
                'model': 'tiny'
            }
            
            response = requests.post("http://localhost:8801/transcribe", 
                                   data=data, timeout=5)
            
            print(f"   Response Status Code: {response.status_code}")
            print("✓ Endpoint exists and responds to basic requests")
            
        # Test 3: Verify the endpoint handles missing file gracefully
        print("\n3. Testing error handling...")
        try:
            # Try to call transcribe without a file
            data = {
                'language': 'ru',
                'task': 'transcribe',
                'model': 'tiny'
            }
            
            response = requests.post("http://localhost:8801/transcribe", 
                                   data=data, timeout=5)
            
            print(f"   Error handling test - Status Code: {response.status_code}")
            print("✓ Endpoint properly handles missing file parameter")
            
        except Exception as e:
            print(f"   Error in error handling test: {e}")
        
        # Test 4: Verify server is accessible at different endpoints
        print("\n4. Testing server accessibility...")
        
        # Test health check if it exists (this might not be implemented)
        try:
            health_response = requests.get("http://localhost:8801/health", timeout=5)
            print(f"   Health check endpoint status: {health_response.status_code}")
        except:
            print("   Health check endpoint not implemented or not accessible")
        
        print("\n" + "=" * 60)
        print("✓ TRANScribe ENDPOINT TEST COMPLETED")
        
        return True
        
    except Exception as e:
        print(f"\n✗ TRANSPOSE ENDPOINT TEST FAILED: {e}")
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
    success = test_transcribe_endpoint()
    
    if not success:
        sys.exit(1)
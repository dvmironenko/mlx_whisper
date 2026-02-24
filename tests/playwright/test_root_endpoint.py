"""
Playwright test for the "/" endpoint of MLX-Whisper API.
This test verifies that the web interface loads correctly and contains expected elements.
"""
import asyncio
from playwright.async_api import async_playwright
import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

async def test_root_endpoint():
    """Test the root endpoint (/) to ensure web interface loads correctly."""
    
    # Start the FastAPI server
    import subprocess
    import time
    
    # Start the server in background
    server_process = subprocess.Popen([
        sys.executable, "src/main.py"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Give the server time to start
    time.sleep(3)
    
    try:
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Navigate to the root endpoint
            await page.goto("http://localhost:8801/")
            
            # Verify the page title
            title = await page.title()
            assert "MLX-Whisper Audio Transcription" in title
            
            # Verify the main header exists
            header = await page.query_selector("h1")
            assert header is not None
            header_text = await header.text_content()
            assert "MLX-Whisper Audio Transcription" in header_text
            
            # Verify the upload form exists
            form = await page.query_selector("#uploadForm")
            assert form is not None
            
            # Verify the file input exists
            file_input = await page.query_selector("#audioFile")
            assert file_input is not None
            
            # Verify the language select exists
            language_select = await page.query_selector("#language")
            assert language_select is not None
            
            # Verify the task select exists
            task_select = await page.query_selector("#task")
            assert task_select is not None
            
            # Verify the model select exists
            model_select = await page.query_selector("#model")
            assert model_select is not None
            
            # Verify the submit button exists
            submit_button = await page.query_selector("button[type='submit']")
            assert submit_button is not None
            
            # Verify the result section exists
            result_section = await page.query_selector(".result-section")
            assert result_section is not None
            
            # Verify the footer exists
            footer = await page.query_selector("footer")
            assert footer is not None
            
            print("All tests passed! The root endpoint (/) loads correctly with all expected elements.")
            
            await browser.close()
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        raise
    finally:
        # Kill the server process
        server_process.terminate()
        try:
            server_input = await server_process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()

if __name__ == "__main__":
    asyncio.run(test_root_endpoint())
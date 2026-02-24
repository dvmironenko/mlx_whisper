"""
Playwright test for MLX-Whisper root endpoint (/).
This test verifies the web interface using actual Playwright browser automation.
"""

import asyncio
import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

async def test_playwright_root_endpoint():
    """Test the root endpoint using Playwright browser automation."""
    
    print("Testing MLX-Whisper root endpoint (/) with Playwright")
    print("=" * 60)
    
    try:
        # Import Playwright async API
        from playwright.async_api import async_playwright
        
        print("1. Starting Playwright browser...")
        
        # Launch Playwright browser
        async with async_playwright() as p:
            # Use Chromium (or you can use firefox or webkit)
            browser = await p.chromium.launch(headless=True)
            
            print("2. Navigating to root endpoint...")
            page = await browser.new_page()
            
            # Navigate to the root endpoint
            await page.goto("http://localhost:8801/")
            
            print("3. Verifying page title...")
            title = await page.title()
            assert "MLX-Whisper Audio Transcription" in title
            print("✓ Page title is correct")
            
            print("4. Verifying page elements...")
            
            # Check for main header
            header = await page.query_selector("h1")
            assert header is not None
            header_text = await header.text_content()
            assert "MLX-Whisper Audio Transcription" in header_text
            print("✓ Main header is present")
            
            # Check for upload form
            form = await page.query_selector("#uploadForm")
            assert form is not None
            print("✓ Upload form is present")
            
            # Check for file input
            file_input = await page.query_selector("#audioFile")
            assert file_input is not None
            print("✓ File input element is present")
            
            # Check for language select
            language_select = await page.query_selector("#language")
            assert language_select is not None
            print("✓ Language selection dropdown is present")
            
            # Check for task select
            task_select = await page.query_selector("#task")
            assert task_select is not None
            print("✓ Task selection dropdown is present")
            
            # Check for model select
            model_select = await page.query_selector("#model")
            assert model_select is not None
            print("✓ Model selection dropdown is present")
            
            # Check for submit button
            submit_button = await page.query_selector("button[type='submit']")
            assert submit_button is not None
            button_text = await submit_button.text_content()
            assert "Транскрибировать" in button_text
            print("✓ Submit button is present")
            
            # Check for result section
            result_section = await page.query_selector(".result-section")
            assert result_section is not None
            print("✓ Result section is present")
            
            # Check for footer
            footer = await page.query_selector("footer")
            assert footer is not None
            print("✓ Footer is present")
            
            # Get page content for verification
            content = await page.content()
            assert "MLX-Whisper Audio Transcription" in content
            print("✓ Page contains expected content")
            
            await browser.close()
            
        print("\n" + "=" * 60)
        print("✓ PLAYWRIGHT TEST PASSED")
        print("The root endpoint (/) is working correctly with Playwright.")
        
        return True
        
    except Exception as e:
        print(f"✗ PLAYWRIGHT TEST FAILED: {e}")
        return False

if __name__ == "__main__":
    # Run the async test function
    success = asyncio.run(test_playwright_root_endpoint())
    
    if not success:
        sys.exit(1)
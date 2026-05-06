"""
Playwright test for MLX-Whisper root endpoint (/).
This test verifies the web interface using actual Playwright browser automation.
"""
import subprocess
import sys
import os
from playwright.sync_api import sync_playwright

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_playwright_root_endpoint():
    """Test the root endpoint using Playwright browser automation."""

    print("Testing MLX-Whisper root endpoint (/) with Playwright")
    print("=" * 60)

    # Start the FastAPI server
    server_process = subprocess.Popen(
        [sys.executable, "src/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Give the server time to start
    import time
    time.sleep(3)

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print("1. Navigating to root endpoint...")
            page.goto("http://localhost:8801/")

            print("2. Verifying page title...")
            title = page.title()
            # Root page may be index (jobs list) or uploads
            assert "MLX-Whisper" in title
            print("  Page title is correct")

            print("3. Verifying page elements...")

            header = page.query_selector("h1")
            assert header is not None
            header_text = header.text_content()
            assert "MLX-Whisper" in header_text
            print("  Main header is present")

            # Jobs list page elements
            jobs_section = page.query_selector("#jobsSection")
            assert jobs_section is not None
            print("  Jobs section is present")

            search = page.query_selector("#jobSearch")
            assert search is not None
            print("  Search input is present")

            container = page.query_selector("#jobsCardsContainer")
            assert container is not None
            print("  Jobs cards container is present")

            theme_toggle = page.query_selector("#themeToggle")
            assert theme_toggle is not None
            print("  Theme toggle is present")

            footer = page.query_selector("footer")
            assert footer is not None
            print("  Footer is present")

            content = page.content()
            assert "MLX-Whisper" in content
            print("  Page contains expected content")

        print("\n" + "=" * 60)
        print("  PLAYWRIGHT TEST PASSED")
        print("  The root endpoint (/) is working correctly with Playwright.")

    except Exception as e:
        print(f"  PLAYWRIGHT TEST FAILED: {e}")
        raise
    finally:
        server_process.terminate()
        try:
            server_process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()

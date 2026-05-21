"""
Playwright test for the "/" endpoint of MLX-Transcriber API.
This test verifies that the web interface loads correctly and contains expected elements.
"""
import subprocess
import sys
import os
from playwright.sync_api import sync_playwright

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_root_endpoint():
    """Test the root endpoint (/) to ensure web interface loads correctly."""

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

            page.goto("http://localhost:8801/")

            title = page.title()
            assert "MLX-Transcriber" in title

            header = page.query_selector("h1")
            assert header is not None
            header_text = header.text_content()
            assert "MLX-Transcriber" in header_text

            # Jobs list page elements
            jobs_section = page.query_selector("#jobsSection")
            assert jobs_section is not None

            search = page.query_selector("#jobSearch")
            assert search is not None

            container = page.query_selector("#jobsCardsContainer")
            assert container is not None

            # Check theme toggle exists
            theme_toggle = page.query_selector("#themeToggle")
            assert theme_toggle is not None

            # Footer
            footer = page.query_selector("footer")
            assert footer is not None

            print(
                "All tests passed! The root endpoint (/) loads correctly with all expected elements."
            )

    except Exception:
        raise
    finally:
        server_process.terminate()
        try:
            server_process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()

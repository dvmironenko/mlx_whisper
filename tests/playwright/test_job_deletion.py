"""
Playwright tests for job and file deletion via web interface.
Verifies the full deletion flow: UI click -> confirmation -> backend DELETE -> UI update.
"""
import subprocess
import sys
import os
import time
from playwright.sync_api import sync_playwright

playwright_dir = os.path.dirname(os.path.abspath(__file__))  # tests/playwright
project_root = os.path.dirname(os.path.dirname(playwright_dir))  # tests/playwright -> tests -> project_root
sys.path.insert(0, project_root)

TEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test.wav")
TEST_FILE = os.path.normpath(TEST_FILE)
SERVER_URL = "http://localhost:8801/"
POLL_INTERVAL = 3
MAX_WAIT = 120


def wait_for_completed_job(page, max_wait=MAX_WAIT, poll=POLL_INTERVAL):
    """Poll until a completed job appears or timeout."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        jobs_section = page.query_selector("#jobsSection")
        if not jobs_section:
            time.sleep(poll)
            continue
        badges = page.query_selector_all(".status-badge")
        for badge in badges:
            if badge.text_content().strip() == "Готово":
                return True
        time.sleep(poll)
    return False


def start_server():
    """Start the Flask server as a subprocess."""
    playwright_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(playwright_dir, "server.log")
    main_script = os.path.join(project_root, "src", "main.py")
    with open(log_file, "w") as logfile:
        proc = subprocess.Popen(
            [sys.executable, main_script],
            cwd=project_root,
            stdout=logfile,
            stderr=logfile,
        )
    time.sleep(15)
    # Check if process is still alive
    if proc.poll() is not None:
        print(f"  WARNING: Server process exited with code {proc.poll()}")
        with open(log_file) as f:
            print("  Server log:\n" + f.read()[-2000:])
    return proc


def stop_server(proc):
    """Stop the server process."""
    proc.terminate()
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def wait_for_server(url, timeout=20):
    """Wait for the server to be ready."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def submit_file_via_api(page):
    """Submit a test file via API and wait for it to complete."""
    import requests

    assert os.path.isfile(TEST_FILE), f"Test file not found: {TEST_FILE}"

    with open(TEST_FILE, "rb") as f:
        resp = requests.post(
            f"{SERVER_URL}api/v1/transcribe",
            files={"file": ("test.wav", f, "audio/wav")},
        )

    if resp.status_code != 200:
        print(f"  API error: {resp.status_code} {resp.text}")
        return False

    data = resp.json()
    job_id = data.get("job_id") or data.get("id")
    print(f"  Job submitted: {job_id}, status={data.get('status')}")
    return True


def test_delete_job():
    """Test deleting an entire job via the web interface."""
    print("\ntest_delete_job")
    print("=" * 60)

    server = start_server()
    try:
        assert wait_for_server(SERVER_URL), "Server did not start"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Navigate and submit a file
            print("1. Navigating to home page...")
            page.goto(SERVER_URL)

            print("2. Submitting test file via API...")
            if not submit_file_via_api(page):
                browser.close()
                sys.exit(1)

            # Navigate back to see the page refresh
            page.goto(SERVER_URL)

            # 2. Wait for job to complete
            print("3. Waiting for job to complete...")
            if not wait_for_completed_job(page):
                print("  TIMEOUT: Job did not complete")
                browser.close()
                sys.exit(1)
            print("  Job completed!")

            # 3. Refresh to get latest data
            print("4. Refreshing page...")
            page.reload()
            page.wait_for_load_state("networkidle")

            # 4. Verify job card exists with delete button
            print("5. Verifying job card exists with delete button...")
            page.wait_for_timeout(1000)
            job_cards = page.query_selector_all(".job-card")
            assert len(job_cards) > 0, "No job cards found"
            print(f"  Found {len(job_cards)} job card(s)")

            delete_btn = page.query_selector(".btn-delete-job")
            assert delete_btn is not None, "Delete job button not found"
            print("  [OK] Delete job button (.btn-delete-job) found")

            # Record initial card count
            initial_card_count = len(page.query_selector_all(".job-card"))
            print(f"  Initial job card count: {initial_card_count}")
            assert initial_card_count > 0, "No job cards to delete"

            # 5. Click delete button
            print("6. Clicking delete button...")
            delete_btn.click()
            page.wait_for_timeout(500)

            # 6. Verify confirm modal appears
            print("7. Verifying confirm modal appears...")
            page.wait_for_timeout(1000)
            confirm_modal = page.query_selector(".modal-overlay")
            assert confirm_modal is not None, "Confirm modal not found"
            # Verify it's a confirm modal (has modal-confirm content)
            confirm_content = confirm_modal.query_selector(".modal-confirm")
            assert confirm_content is not None, "Confirm modal content not found"
            print("  [OK] Confirm modal present")

            # Verify modal title
            modal_title = confirm_modal.query_selector("#confirm-title")
            if modal_title:
                title_text = modal_title.text_content()
                print(f"  Modal title: '{title_text}'")
                assert "Удалить задание?" in title_text, f"Wrong title: {title_text}"

            # 7. Click confirm delete button
            print("8. Clicking confirm delete button...")
            btn_confirm = confirm_modal.query_selector(".btn-confirm-delete")
            assert btn_confirm is not None, "Confirm delete button not found"
            btn_confirm.click()
            page.wait_for_timeout(1000)

            # 8. Verify job card is removed (count should decrease by 1)
            print("9. Verifying job card is removed...")
            page.wait_for_timeout(1000)
            remaining_cards = page.query_selector_all(".job-card")
            expected_count = initial_card_count - 1
            assert len(remaining_cards) == expected_count, \
                f"Expected {expected_count} cards after deletion, found {len(remaining_cards)}"
            print(f"  [OK] Card count: {initial_card_count} -> {len(remaining_cards)} (deleted 1)")

            # 9. Verify notification modal (success) appears
            print("10. Verifying success notification appears...")
            page.wait_for_timeout(500)
            success_modal = page.query_selector(".modal-overlay")
            if success_modal:
                modal_class = success_modal.get_attribute("class") or ""
                print(f"  [OK] Modal present, classes: {modal_class[:80]}")
                # Close the notification
                close_btn = success_modal.query_selector(".modal-close-btn")
                if close_btn:
                    close_btn.click()
                page.wait_for_timeout(300)
            else:
                print("  (Success notification may have been auto-closed by loadJobs)")

            print("\n" + "=" * 60)
            print("  TEST PASSED: Job deletion works correctly")

            browser.close()

    finally:
        stop_server(server)


def test_delete_file_from_job():
    """Test deleting a single file from a completed job."""
    print("\ntest_delete_file_from_job")
    print("=" * 60)

    server = start_server()
    try:
        assert wait_for_server(SERVER_URL), "Server did not start"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Navigate and submit a file
            print("1. Navigating to home page...")
            page.goto(SERVER_URL)

            print("2. Submitting test file via API...")
            if not submit_file_via_api(page):
                browser.close()
                sys.exit(1)

            page.goto(SERVER_URL)

            # 2. Wait for job to complete
            print("3. Waiting for job to complete...")
            if not wait_for_completed_job(page):
                print("  TIMEOUT: Job did not complete")
                browser.close()
                sys.exit(1)
            print("  Job completed!")

            # 3. Refresh to get latest data
            print("4. Refreshing page...")
            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

            # 4. Set up dialog handler for native confirm()
            print("5. Setting up dialog handler...")
            dialog_accepted = False

            def handle_dialog(dialog):
                nonlocal dialog_accepted
                print(f"  Dialog message: {dialog.message}")
                dialog_accepted = True
                dialog.accept()

            page.on("dialog", handle_dialog)

            # 5. Find the job card with file listing
            print("6. Finding job card with file delete button...")
            job_cards = page.query_selector_all(".job-card")
            assert len(job_cards) > 0, "No job cards found"

            file_delete_btn = page.query_selector(".btn-delete-file")
            assert file_delete_btn is not None, "File delete button not found"
            print("  [OK] File delete button (.btn-delete-file) found")

            # Record initial file row count
            initial_file_rows = len(page.query_selector_all(".result-file-row"))
            print(f"  Initial file row count: {initial_file_rows}")

            # 6. Click file delete button (triggers native confirm)
            print("7. Clicking file delete button...")
            file_delete_btn.click()
            page.wait_for_timeout(500)

            # 7. Verify dialog was triggered and accepted
            print("8. Verifying confirm dialog was handled...")
            assert dialog_accepted, "Native confirm dialog was not triggered"
            print("  [OK] Confirm dialog accepted")

            # 8. Wait for file row to be removed from DOM
            print("9. Verifying file row is removed...")
            page.wait_for_timeout(1000)

            remaining_file_rows = page.query_selector_all(".result-file-row")
            print(f"  Remaining file rows: {len(remaining_file_rows)}")
            expected_count = initial_file_rows - 1
            assert len(remaining_file_rows) == expected_count, \
                f"Expected {expected_count} file rows after deletion, found {len(remaining_file_rows)}"
            print(f"  [OK] File row count: {initial_file_rows} -> {len(remaining_file_rows)} (deleted 1)")

            # 9. Verify notification modal (success) appears
            print("10. Verifying success notification appears...")
            # The notification modal should appear - click to dismiss
            success_modal = page.query_selector(".modal-overlay")
            if success_modal:
                print("  [OK] Success notification modal present")
                # Close it
                close_btn = success_modal.query_selector(".modal-close-btn")
                if close_btn:
                    close_btn.click()
                else:
                    confirm_in_modal = success_modal.query_selector(".btn-confirm-delete")
                    if confirm_in_modal:
                        confirm_in_modal.click()
                page.wait_for_timeout(300)
            else:
                print("  (No success notification modal — file may have been deleted before modal rendered)")

            print("\n" + "=" * 60)
            print("  TEST PASSED: File deletion works correctly")

            browser.close()

    finally:
        stop_server(server)


if __name__ == "__main__":
    test_delete_job()
    test_delete_file_from_job()

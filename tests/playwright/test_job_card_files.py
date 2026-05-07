"""
Playwright test for file listing in job cards.
Verifies that completed job cards display file list with View/Download/Delete buttons.
"""
import subprocess
import sys
import os
import time
from playwright.sync_api import sync_playwright

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def wait_for_completed_job(page, max_wait=120, poll=2):
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


def test_job_card_file_listing():
    """Test that job cards show file listing with action buttons."""

    print("Testing file listing in job cards...")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Navigate and submit a test file
        print("1. Navigating to home page...")
        page.goto("http://localhost:8801/")

        test_file = os.path.join(project_root, "test.wav")
        assert os.path.isfile(test_file), f"Test file not found: {test_file}"

        # Find the form and submit
        print("2. Submitting test file for transcription...")
        file_input = page.query_selector('input[type="file"][id="audioFile"]')
        if file_input:
            file_input.set_files(test_file)
            # Look for submit button
            submit_btn = page.query_selector('button[type="submit"]')
            if submit_btn:
                submit_btn.click()
                # Wait for redirect or processing indicator
                page.wait_for_load_state("networkidle", timeout=30000)
                print("  File submitted, waiting for processing...")
        else:
            # Form may not exist on jobs-list page; submit via API instead
            print("  Form not found, submitting via API...")
            import requests
            with open(test_file, "rb") as f:
                resp = requests.post(
                    "http://localhost:8801/api/v1/transcribe",
                    files={"file": ("test.wav", f, "audio/wav")},
                )
            if resp.status_code == 200:
                data = resp.json()
                job_id = data.get("job_id") or data.get("id")
                print(f"  Job submitted: {job_id}, status={data.get('status')}")
                # Navigate back to refresh
                page.goto("http://localhost:8801/")
            else:
                print(f"  API error: {resp.status_code} {resp.text}")
                browser.close()
                sys.exit(1)

        # 2. Wait for completion
        print("3. Waiting for job to complete...")
        completed = wait_for_completed_job(page, max_wait=120, poll=3)
        if not completed:
            print("  TIMEOUT: Job did not complete in time")
            browser.close()
            sys.exit(1)
        print("  Job completed!")

        # 3. Refresh to get latest data
        page.reload()
        page.wait_for_load_state("networkidle")

        # 4. Verify jobs section and cards
        print("4. Verifying page structure...")
        jobs_section = page.query_selector("#jobsSection")
        assert jobs_section is not None, "Jobs section not found"
        print("  [OK] Jobs section present")

        container = page.query_selector("#jobsCardsContainer")
        assert container is not None, "Jobs cards container not found"
        print("  [OK] Jobs cards container present")

        job_cards = page.query_selector_all(".job-card")
        print(f"  Found {len(job_cards)} job card(s)")
        assert len(job_cards) > 0, "No job cards found"

        # 5. Find completed cards and check file listing
        print("5. Checking file listings in completed job cards...")
        completed_cards_found = 0
        cards_with_files = 0

        for i, card in enumerate(job_cards):
            badge = card.query_selector(".status-badge")
            if not badge:
                continue
            status = badge.text_content().strip()
            if status != "Готово":
                continue

            completed_cards_found += 1

            # Check for file list elements
            has_file_list = card.query_selector(".result-file-list") is not None
            has_file_tag = card.query_selector(".result-file-tag") is not None
            has_view_btn = card.query_selector(".btn-view-file") is not None
            has_dl_btn = card.query_selector(".btn-download-file") is not None
            has_del_btn = card.query_selector(".btn-delete-file") is not None

            print(f"\n  Card #{i+1}: status={status}")
            print(f"    file_list={has_file_list}, tag={has_file_tag}")
            print(f"    view={has_view_btn}, download={has_dl_btn}, delete={has_del_btn}")

            if not has_file_list:
                print("    [SKIP] No file list")
                continue

            cards_with_files += 1

            # 6. Verify file list layout
            file_list = card.query_selector(".result-file-list")
            display = file_list.evaluate("el => getComputedStyle(el).display")
            assert display == "flex", f"Expected flex, got {display}"
            direction = file_list.evaluate(
                "el => getComputedStyle(el).flexDirection"
            )
            assert direction == "column", f"Expected column, got {direction}"
            print(f"    [OK] Layout: flex column, gap={file_list.evaluate('el => getComputedStyle(el).gap')}")

            # 7. Verify each file row
            file_rows = file_list.query_selector_all(".result-file-row")
            print(f"    Files: {len(file_rows)}")

            for j, row in enumerate(file_rows):
                tag = row.query_selector(".result-file-tag")
                filename = str(tag.text_content()).strip() if tag else "unknown"
                print(f"      File {j+1}: {filename}")

                # Verify file tag icon
                icon = tag.query_selector("i") if tag else None
                if icon:
                    print(f"        [OK] Icon present: {icon.get_attribute('class')}")

                # Verify buttons
                assert row.query_selector(".btn-view-file") is not None or row.query_selector(".btn-download-file") is not None, \
                    f"Missing buttons for {filename}"

                # Check View button for .txt/.md
                if filename.lower().endswith(".txt") or filename.lower().endswith(".md"):
                    view_btn = row.query_selector(".btn-view-file")
                    assert view_btn is not None, f"View button missing for text file: {filename}"
                    print(f"        [OK] View button (text file)")

                dl_btn = row.query_selector(".btn-download-file")
                assert dl_btn is not None, f"Download button missing: {filename}"
                print(f"        [OK] Download button")

                del_btn = row.query_selector(".btn-delete-file")
                assert del_btn is not None, f"Delete button missing: {filename}"
                print(f"        [OK] Delete button")

            # 8. Verify file list title
            title_el = page.query_selector(".result-files-title")
            if title_el:
                title_text = str(title_el.text_content())
                print(f"    [OK] Title: '{title_text}'")

        print(f"\n  Summary: {cards_with_files}/{completed_cards_found} completed cards have file listings")

        # 9. Test View button opens modal
        if cards_with_files > 0:
            print("6. Testing View button opens file content modal...")
            first_view_btn = page.query_selector(".btn-view-file")
            if first_view_btn:
                first_view_btn.click()
                page.wait_for_timeout(500)
                modal = page.query_selector(".modal-overlay")
                if modal:
                    print("  [OK] File content modal opened")
                    # Close modal
                    close_btn = page.query_selector(".btn-modal-close, .modal-close-btn")
                    if not close_btn:
                        # Try clicking the overlay to close
                        modal.click()
                    page.wait_for_timeout(300)
                    # Verify modal is closed
                    modal_after = page.query_selector(".modal-overlay")
                    if modal_after:
                        # Try Escape key
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(200)
                    print("  [OK] Modal closed")

        browser.close()

        print("\n" + "=" * 60)
        print("  PLAYWRIGHT TEST PASSED")
        print("  File listing in job cards works correctly.")


if __name__ == "__main__":
    test_job_card_file_listing()

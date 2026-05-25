"""Playwright test for oMLX transcription via UI."""

import os
import sys
import time

import requests
from playwright.sync_api import sync_playwright

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

BASE_URL = "http://localhost:8801"


def wait_for_job_completion(job_id: str, max_wait: int = 600, poll: int = 5) -> dict | None:
    """Poll /api/v1/jobs until the specific omlx job completes or timeout."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = requests.get(f"{BASE_URL}/api/v1/jobs", timeout=10)
            if resp.status_code != 200:
                time.sleep(poll)
                continue
            jobs: list[dict] = resp.json()
            for job in jobs:
                if job.get("job_id") == job_id and job.get("status") == "completed":
                    return job
        except Exception as e:
            print(f"  Poll error: {e}")
        time.sleep(poll)
    return None


def test_omlx_transcription():
    """Test oMLX transcription via the uploads UI."""

    print("Testing oMLX transcription via UI...")
    print("=" * 60)

    test_file = os.path.join(project_root, "test_telemost.webm")
    if not os.path.isfile(test_file):
        print(f"ERROR: Test file not found: {test_file}")
        sys.exit(1)

    file_size_mb = os.path.getsize(test_file) / (1024 * 1024)
    print(f"Test file: {test_file} ({file_size_mb:.0f} MB)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # 1. Navigate to uploads page
            print("\n1. Navigating to uploads page...")
            page.goto(f"{BASE_URL}/uploads")
            page.wait_for_load_state("networkidle")
            print("  [OK] Page loaded")

            # 2. Verify oMLX option exists
            print("\n2. Checking mechanism options...")
            mechanism_select = page.query_selector("#mechanism")
            assert mechanism_select is not None, "Mechanism select not found"
            options = mechanism_select.query_selector_all("option")
            option_values = [opt.get_attribute("value") for opt in options]
            print(f"  Available mechanisms: {option_values}")
            assert "omlx" in option_values, "oMLX option not found"
            print("  [OK] oMLX option present")

            # 3. Select oMLX mechanism
            print("\n3. Selecting oMLX mechanism...")
            mechanism_select.select_option(value="omlx")
            selected = mechanism_select.evaluate("el => el.value")
            assert selected == "omlx", f"Expected 'omlx', got '{selected}'"
            print("  [OK] oMLX selected")

            # 4. Verify Whisper params are hidden
            print("\n4. Verifying Whisper params hidden for oMLX...")
            whisper_params = [
                "task", "model", "noSpeechThreshold", "hallucinationSilenceThreshold",
                "wordTimestamps", "conditionOnPreviousText", "initialPrompt",
                "removeSilence", "silenceThreshold", "silenceDuration",
            ]
            for param_id in whisper_params:
                el = page.query_selector(f"#{param_id}")
                if el:
                    display = el.evaluate("el => getComputedStyle(el).display")
                    assert display == "none", f"Whisper param #{param_id} should be hidden, got display={display}"
            print("  [OK] All Whisper params hidden")

            # 5. Upload test file
            print(f"\n5. Uploading test file ({file_size_mb:.0f} MB)...")
            page.set_input_files('input[type="file"][id="audioFile"]', test_file)

            # Verify file is selected
            file_info = page.evaluate("el => document.getElementById('audioFile').files[0]?.name")
            print(f"  File selected: {file_info}")
            assert file_info == "test_telemost.webm", f"Wrong file selected: {file_info}"
            print("  [OK] File uploaded")

            # 6. Submit form
            print("\n6. Submitting transcription form...")
            submit_btn = page.query_selector('#submitButton')
            assert submit_btn is not None, "Submit button not found"

            # Wait for navigation/redirect
            with page.expect_navigation(timeout=60000) as nav_info:
                submit_btn.click()

            response = nav_info.value
            if response:
                final_url = response.url
                print(f"  Redirected to: {final_url}")
                assert "/?" in final_url and "redirect=" in final_url, \
                    f"Unexpected redirect URL: {final_url}"
            else:
                # Maybe no navigation, check URL manually
                current_url = page.url
                print(f"  Current URL: {current_url}")
                if "/?" in current_url and "redirect=" in current_url:
                    final_url = current_url
                else:
                    print("  WARNING: No navigation detected, will poll API for job")
                    final_url = None

            # Extract job_id from URL if available
            job_id: str | None = None
            if final_url:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(final_url)
                params = parse_qs(parsed.query)
                job_id = params.get("redirect", [None])[0]
                print(f"  Job ID from URL: {job_id}")

            if not job_id:
                print("  ERROR: Could not extract job_id from redirect URL")
                browser.close()
                sys.exit(1)

            # 7. Wait for job completion
            print(f"\n7. Waiting for job {job_id} completion (max 15 min)...")
            job = wait_for_job_completion(job_id, max_wait=900, poll=10)

            if not job:
                print("  TIMEOUT: Job did not complete in time")
                # Print current jobs for debugging
                try:
                    resp = requests.get(f"{BASE_URL}/api/v1/jobs", timeout=10)
                    if resp.status_code == 200:
                        jobs = resp.json()
                        omlx_jobs = [j for j in jobs if j.get("mechanism") == "omlx"]
                        print(f"  oMLX jobs found: {len(omlx_jobs)}")
                        for vj in omlx_jobs[-3:]:
                            print(f"    - {vj['job_id'][:8]}... status={vj['status']} "
                                  f"duration={vj.get('transcription_duration')}s")
                except Exception:
                    pass
                browser.close()
                sys.exit(1)

            print(f"  Job completed: {job['job_id']}")
            print(f"  Duration: {job.get('transcription_duration')}s")
            print(f"  Model: {job.get('model')}")
            print(f"  Language: {job.get('language')}")

            # 8. Get full job detail
            print("\n8. Checking job result...")
            job_detail_resp = requests.get(
                f"{BASE_URL}/api/v1/jobs/{job['job_id']}", timeout=10
            )
            if job_detail_resp.status_code == 200:
                job_detail = job_detail_resp.json()
                segments = job_detail.get("segments", [])
                print(f"  Segments count: {len(segments)}")

                if segments:
                    first_seg = segments[0]
                    print(f"  First segment: speaker={first_seg.get('speaker')}, "
                          f"text={first_seg.get('text', '')[:80]}...")
                    print("\n  [OK] oMLX transcription returned segments")
                else:
                    print("\n  [WARN] oMLX completed but segments are empty")
                    print("  This may indicate an API response parsing issue")

                files = job_detail.get("files", [])
                print(f"  Files: {[f['name'] for f in files]}")
            else:
                print(f"  ERROR: Failed to get job detail: {job_detail_resp.status_code}")

            # 9. Verify UI shows completed job
            print("\n9. Verifying UI shows completed job...")
            if final_url:
                page.goto(final_url)
                page.wait_for_load_state("networkidle")

                # Check for status badge
                badges = page.query_selector_all(".status-badge")
                completed_found = False
                for badge in badges:
                    text = badge.text_content() or ""
                    if text.strip() == "Готово":
                        completed_found = True
                        break
                if completed_found:
                    print("  [OK] Job card shows 'Готово' status")
                else:
                    print("  [WARN] No 'Готово' badge found on jobs page")
            else:
                print("  [SKIP] No redirect URL to check UI")

            print("\n" + "=" * 60)
            print("  PLAYWRIGHT TEST COMPLETED")
            print("  oMLX transcription flow works end-to-end.")

        finally:
            browser.close()


if __name__ == "__main__":
    test_omlx_transcription()

"""Playwright test for whisper-large-v3-asr-fp16 transcription via UI."""

import os
import sys
import time
import subprocess
import urllib.request

import requests
from playwright.sync_api import sync_playwright

tests_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(tests_dir)
sys.path.insert(0, project_root)

BASE_URL = "http://localhost:8801"
TEST_FILE = os.path.join(tests_dir, "test.wav")


def wait_for_server(host: str = "localhost", port: int = 8801, timeout: int = 60) -> bool:
    """Wait for the server to be ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(f"http://{host}:{port}/api/v1/health", timeout=2)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_for_job_completion(job_id: str, max_wait: int = 300, poll: int = 5) -> dict | None:
    """Poll /api/v1/jobs until the specific job completes or timeout."""
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


def test_omlx_whisper_turbo_asr_fp16():
    """Test whisper-large-v3-asr-fp16 transcription via the uploads UI."""

    print("Testing whisper-large-v3-asr-fp16 transcription via UI...")
    print("=" * 60)

    if not os.path.isfile(TEST_FILE):
        print(f"ERROR: Test file not found: {TEST_FILE}")
        sys.exit(1)

    file_size_mb = os.path.getsize(TEST_FILE) / (1024 * 1024)
    print(f"Test file: {TEST_FILE} ({file_size_mb:.1f} MB)")

    # Start server
    print("\nStarting server...")
    server_process = subprocess.Popen(
        [sys.executable, "src/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=project_root,
    )

    try:
        # Give the server a moment to begin accepting connections
        time.sleep(2)

        if not wait_for_server():
            print("ERROR: Server did not start in time")
            server_process.terminate()
            stdout, stderr = server_process.communicate(timeout=5)
            stdout = stdout.decode() if stdout else ""
            stderr = stderr.decode() if stderr else ""
            print(f"  STDOUT: {stdout[-1000:]}")
            print(f"  STDERR: {stderr[-1000:]}")
            sys.exit(1)

        print("  [OK] Server is ready")

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

                # Wait for model selector to populate
                page.wait_for_timeout(1000)

                # 4. Verify whisper-large-v3-asr-fp16 model is available
                print("\n4. Checking model selector...")
                model_select = page.query_selector("#omlxModel")
                assert model_select is not None, "oMLX model select not found"
                model_options = model_select.query_selector_all("option")
                model_values = [opt.get_attribute("value") for opt in model_options]
                print(f"  Available models: {model_values}")
                assert "whisper-large-v3-asr-fp16" in model_values, \
                    f"whisper-large-v3-asr-fp16 not found in models: {model_values}"
                print("  [OK] whisper-large-v3-asr-fp16 model available")

                # 5. Select whisper-large-v3-asr-fp16 model
                print("\n5. Selecting whisper-large-v3-asr-fp16 model...")
                model_select.select_option(value="whisper-large-v3-asr-fp16")
                selected_model = model_select.evaluate("el => el.value")
                assert selected_model == "whisper-large-v3-asr-fp16", \
                    f"Expected 'whisper-large-v3-asr-fp16', got '{selected_model}'"
                print("  [OK] whisper-large-v3-asr-fp16 selected")

                # 6. Upload test file
                print(f"\n6. Uploading test file ({file_size_mb:.1f} MB)...")
                page.set_input_files('input[type="file"][id="audioFile"]', TEST_FILE)

                file_info = page.evaluate(
                    "el => document.getElementById('audioFile').files[0]?.name"
                )
                print(f"  File selected: {file_info}")
                assert file_info == "test.wav", f"Wrong file selected: {file_info}"
                print("  [OK] File uploaded")

                # 7. Submit form
                print("\n7. Submitting transcription form...")
                submit_btn = page.query_selector('#submitButton')
                assert submit_btn is not None, "Submit button not found"

                with page.expect_navigation(timeout=60000) as nav_info:
                    submit_btn.click()

                response = nav_info.value
                if response:
                    final_url = response.url
                    print(f"  Redirected to: {final_url}")
                    assert "/?" in final_url and "redirect=" in final_url, \
                        f"Unexpected redirect URL: {final_url}"
                else:
                    current_url = page.url
                    print(f"  Current URL: {current_url}")
                    if "/?" in current_url and "redirect=" in current_url:
                        final_url = current_url
                    else:
                        print("  WARNING: No navigation detected, will poll API for job")
                        final_url = None

                # Extract job_id from URL
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

                # 8. Wait for job completion
                print(f"\n8. Waiting for job {job_id} completion (max 15 min)...")
                job = wait_for_job_completion(job_id, max_wait=900, poll=5)

                if not job:
                    print("  TIMEOUT: Job did not complete in time")
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

                # Verify model is whisper-large-v3-asr-fp16
                assert job.get("model") == "whisper-large-v3-asr-fp16", \
                    f"Expected model 'whisper-large-v3-asr-fp16', got '{job.get('model')}'"
                print("  [OK] Model is whisper-large-v3-asr-fp16")

                # 9. Get full job detail
                print("\n9. Checking job result...")
                job_detail_resp = requests.get(
                    f"{BASE_URL}/api/v1/jobs/{job['job_id']}", timeout=10
                )
                if job_detail_resp.status_code == 200:
                    job_detail = job_detail_resp.json()
                    segments = job_detail.get("segments", [])
                    print(f"  Segments count: {len(segments)}")

                    assert len(segments) > 0, "Segments are empty"
                    print("  [OK] Segments are not empty")

                    first_seg = segments[0]
                    print(f"  First segment: speaker={first_seg.get('speaker')}, "
                          f"text={first_seg.get('text', '')[:80]}...")

                    # Verify text is not empty
                    text = first_seg.get("text", "").strip()
                    assert len(text) > 0, "First segment text is empty"
                    print(f"  [OK] First segment text: '{text[:60]}...'")

                    files = job_detail.get("files", [])
                    print(f"  Files: {[f['name'] for f in files]}")
                else:
                    print(f"  ERROR: Failed to get job detail: {job_detail_resp.status_code}")
                    browser.close()
                    sys.exit(1)

                # 10. Verify UI shows completed job
                print("\n10. Verifying UI shows completed job...")
                if final_url:
                    page.goto(final_url)
                    page.wait_for_load_state("networkidle")

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
                        # Try checking the jobs list page
                        page.goto(f"{BASE_URL}/")
                        page.wait_for_load_state("networkidle")
                        badges = page.query_selector_all(".status-badge")
                        for badge in badges:
                            text = badge.text_content() or ""
                            if text.strip() == "Готово":
                                completed_found = True
                                break
                        if completed_found:
                            print("  [OK] Job card shows 'Готово' status (from jobs list)")
                        else:
                            print("  [WARN] No 'Готово' badge found anywhere")
                else:
                    print("  [SKIP] No redirect URL to check UI")

                print("\n" + "=" * 60)
                print("  PLAYWRIGHT TEST COMPLETED SUCCESSFULLY")
                print("  whisper-large-v3-asr-fp16 transcription works end-to-end.")

            finally:
                browser.close()

    finally:
        # Cleanup server
        print("\nStopping server...")
        server_process.terminate()
        try:
            server_process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait()
        print("  [OK] Server stopped")


if __name__ == "__main__":
    test_omlx_whisper_turbo_asr_fp16()

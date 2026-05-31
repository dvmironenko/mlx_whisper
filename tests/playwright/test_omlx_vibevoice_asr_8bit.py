"""Playwright test: transcribe 134 MB WAV with oMLX + VibeVoice-ASR-8bit."""

import os
import sys
import time

import requests
from playwright.sync_api import sync_playwright

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

BASE_URL = "http://localhost:8801"
AUDIO_FILE = os.path.join(
    os.path.dirname(project_root),
    "data/d85f5c3d-4a2d-43c2-ab0f-17f6eb4c9343/Встреча в Телемосте 11.04.26 10-54-45 — запись_converted.wav",
)
POLL_INTERVAL = 5
POLL_TIMEOUT = 3600


def wait_for_job_completion(job_id: str, max_wait: int = POLL_TIMEOUT, poll: int = POLL_INTERVAL) -> dict | None:
    """Poll /api/v1/jobs until the job completes or fails."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = requests.get(f"{BASE_URL}/api/v1/jobs", timeout=10)
            if resp.status_code != 200:
                time.sleep(poll)
                continue
            jobs: list[dict] = resp.json()
            for job in jobs:
                if job.get("job_id") == job_id and job.get("status") in ("completed", "failed"):
                    return job
        except Exception as e:
            print(f"  Poll error: {e}")
        time.sleep(poll)
    return None


def test_omlx_vibevoice_asr_8bit():
    """Transcribe 134 MB WAV with oMLX + VibeVoice-ASR-8bit and verify non-empty result."""
    if not os.path.isfile(AUDIO_FILE):
        print(f"ERROR: Test file not found: {AUDIO_FILE}")
        sys.exit(1)

    file_size_mb = os.path.getsize(AUDIO_FILE) / (1024 * 1024)
    print(f"Testing oMLX VibeVoice-ASR-8bit transcription...")
    print("=" * 60)
    print(f"Test file: {AUDIO_FILE} ({file_size_mb:.0f} MB)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # 1. Navigate to uploads page
            print("\n1. Navigating to uploads page...")
            page.goto(f"{BASE_URL}/uploads")
            page.wait_for_load_state("networkidle")
            print("  [OK] Page loaded")

            # 2. Select oMLX mechanism
            print("\n2. Selecting oMLX mechanism...")
            mechanism_select = page.query_selector("#mechanism")
            assert mechanism_select is not None, "Mechanism select not found"
            mechanism_select.select_option(value="omlx")
            selected = mechanism_select.evaluate("el => el.value")
            assert selected == "omlx", f"Expected 'omlx', got '{selected}'"
            print("  [OK] oMLX selected")

            # 3. Wait for model selector and select VibeVoice-ASR-8bit
            print("\n3. Selecting VibeVoice-ASR-8bit model...")
            page.wait_for_selector("#omlxModel", state="visible", timeout=10000)
            omlx_model_select = page.query_selector("#omlxModel")
            assert omlx_model_select is not None, "oMLX model selector not found"
            omlx_model_select.select_option(value="VibeVoice-ASR-8bit")
            model_selected = omlx_model_select.evaluate("el => el.value")
            assert model_selected == "VibeVoice-ASR-8bit", \
                f"Expected 'VibeVoice-ASR-8bit', got '{model_selected}'"
            print(f"  [OK] Model selected: {model_selected}")

            # 4. Upload audio file
            print(f"\n4. Uploading test file ({file_size_mb:.0f} MB)...")
            page.set_input_files('input[type="file"][id="audioFile"]', AUDIO_FILE)
            file_info = page.evaluate("el => document.getElementById('audioFile').files[0]?.name")
            print(f"  File selected: {file_info}")
            print("  [OK] File uploaded")

            # 5. Submit form
            print("\n5. Submitting transcription form...")
            submit_btn = page.query_selector('#submitButton')
            assert submit_btn is not None, "Submit button not found"

            with page.expect_navigation(timeout=60000) as nav_info:
                submit_btn.click()

            response = nav_info.value
            if response:
                final_url = response.url
                print(f"  Redirected to: {final_url}")
            else:
                final_url = page.url
                print(f"  Current URL: {final_url}")

            # Extract job_id from URL
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(final_url)
            params = parse_qs(parsed.query)
            job_id = params.get("redirect", [None])[0]
            print(f"  Job ID: {job_id}")
            assert job_id, "Could not extract job_id from redirect URL"

            # 6. Wait for job completion
            print(f"\n6. Waiting for job {job_id} completion (max {POLL_TIMEOUT}s)...")
            job = wait_for_job_completion(job_id)

            if not job:
                print("  TIMEOUT: Job did not complete in time")
                try:
                    resp = requests.get(f"{BASE_URL}/api/v1/jobs", timeout=10)
                    if resp.status_code == 200:
                        jobs = resp.json()
                        omlx_jobs = [j for j in jobs if j.get("mechanism") == "omlx"]
                        print(f"  oMLX jobs: {len(omlx_jobs)}")
                        for vj in omlx_jobs[-3:]:
                            print(f"    - {vj['job_id'][:8]}... status={vj['status']} "
                                  f"duration={vj.get('transcription_duration')}s")
                except Exception:
                    pass
                browser.close()
                sys.exit(1)

            print(f"  Job status: {job['status']}")
            print(f"  Duration: {job.get('transcription_duration')}s")
            print(f"  Model: {job.get('model')}")

            # 7. Get full job detail
            print("\n7. Checking job result...")
            job_detail_resp = requests.get(
                f"{BASE_URL}/api/v1/jobs/{job['job_id']}", timeout=10
            )
            assert job_detail_resp.status_code == 200, \
                f"Failed to get job detail: {job_detail_resp.status_code}"

            job_detail = job_detail_resp.json()
            segments = job_detail.get("segments", [])
            print(f"  Segments count: {len(segments)}")

            assert len(segments) > 0, "Segments list is empty"

            # Verify segment structure
            for i, seg in enumerate(segments[:3]):
                assert "text" in seg, f"Segment {i} missing 'text'"
                assert "start" in seg, f"Segment {i} missing 'start'"
                assert "end" in seg, f"Segment {i} missing 'end'"
                print(f"  Seg {i}: [{seg['start']:.2f}-{seg['end']:.2f}] "
                      f"speaker={seg.get('speaker', seg.get('speaker_id', '?'))} "
                      f"text={seg['text'][:60]}...")

            full_text = job_detail.get("text", "")
            print(f"\n  Full text length: {len(full_text)} chars")
            assert len(full_text) > 0, "Full transcription text is empty"

            total_duration = sum(
                seg.get("end", 0) - seg.get("start", 0) for seg in segments
            )
            speaker_ids = set(
                seg.get("speaker", seg.get("speaker_id", 0)) for seg in segments
            )

            print("\n" + "=" * 60)
            print(f"  RESULTS: {len(segments)} segments, "
                  f"{total_duration:.1f}s speech, "
                  f"{len(speaker_ids)} speaker(s), "
                  f"{len(full_text)} chars")
            print("  [OK] oMLX VibeVoice-ASR-8bit transcription successful")

        finally:
            browser.close()


if __name__ == "__main__":
    test_omlx_vibevoice_asr_8bit()

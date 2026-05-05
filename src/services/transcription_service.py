"""Сервисный слой для очереди транскрипции."""

from typing import Any, Dict, List, Optional, Tuple

import src.config
from src.services.job_manager import JobManager, JobStatus
from src.services.transcription_queue import TranscriptionQueueManager


class TranscriptionService:
    """Обёртка над TranscriptionQueueManager + JobManager."""

    def __init__(
        self,
        queue_manager: TranscriptionQueueManager,
        job_manager: JobManager,
    ) -> None:
        self._qm = queue_manager
        self._jm = job_manager

    def submit(
        self,
        wav_path: str,
        job_id: str,
        original_filename: str,
        model: str,
        language: Optional[str],
        task: str,
        word_timestamps: bool,
        condition_on_previous_text: bool,
        no_speech_threshold: Optional[float],
        hallucination_silence_threshold: Optional[float],
        initial_prompt: Optional[str],
        duration: Optional[float],
    ) -> Tuple[str, bool]:
        """Submit a job to the queue. Returns (job_id, success)."""
        payload: Dict[str, Any] = {
            "job_id": job_id,
            "source": "upload",
            "original_filename": original_filename,
            "wav_path": wav_path,
            "model": model,
            "duration": duration,
            "params": {
                "language": language,
                "task": task,
                "word_timestamps": word_timestamps,
                "condition_on_previous_text": condition_on_previous_text,
                "no_speech_threshold": no_speech_threshold,
                "hallucination_silence_threshold": hallucination_silence_threshold,
                "initial_prompt": initial_prompt,
            },
        }
        success = self._qm.submit(payload)
        return job_id, success

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job metadata + result if completed."""
        metadata = self._jm.load(job_id)
        if metadata is None:
            return None

        result: Dict[str, Any] = dict(metadata)
        status = JobStatus(metadata["status"])

        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            import os
            job_dir = os.path.join(src.config.DATA_UPLOADS_DIR, job_id)

            if os.path.isdir(job_dir):
                # Read text file
                txt_files = [f for f in os.listdir(job_dir) if f.endswith(".txt") and "segments" not in f]
                if txt_files:
                    with open(os.path.join(job_dir, txt_files[0]), "r", encoding="utf-8") as f:
                        result["text"] = f.read()

                # Read segments JSON
                json_files = [f for f in os.listdir(job_dir) if f.endswith(".json")]
                if json_files:
                    with open(os.path.join(job_dir, json_files[0]), "r", encoding="utf-8") as f:
                        import json
                        data = json.load(f)
                        result["segments"] = data.get("segments", [])

                # List all files
                result["files"] = [f for f in os.listdir(job_dir) if os.path.isfile(os.path.join(job_dir, f))]

        return result

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs via JobManager."""
        return self._jm.list_all()

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or processing job via queue manager."""
        return self._qm.cancel_job(job_id)

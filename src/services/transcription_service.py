"""Сервисный слой для очереди транскрипции."""

import json
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
        """Get job metadata + result if completed. Falls back to orphaned directories."""
        metadata = self._jm.load(job_id)
        if metadata is not None:
            result: Dict[str, Any] = dict(metadata)
            status = JobStatus(metadata["status"])
        else:
            # Check for orphaned directory
            import os as _os
            import uuid as _uuid
            data_dir = src.config.DATA_UPLOADS_DIR
            try:
                _uuid.UUID(job_id, version=4)
            except ValueError:
                return None
            if not _os.path.isdir(_os.path.join(data_dir, job_id)):
                return None
            files = [
                f for f in _os.listdir(_os.path.join(data_dir, job_id))
                if _os.path.isfile(_os.path.join(data_dir, job_id, f))
            ]
            result = {
                "job_id": job_id,
                "status": JobStatus.COMPLETED.value,
                "source": "upload",
                "created_at": "",
                "updated_at": "",
                "original_filename": None,
                "model": None,
                "language": None,
                "task": None,
                "word_timestamps": False,
                "mechanism": None,
                "duration": None,
                "transcription_duration": None,
                "result_file": None,
                "error": None,
                "files": files,
                "_orphaned": True,
            }

        status = JobStatus(result["status"])

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
                # Whisper saves as "segments.json", VibeVoice as "{job_id}_segments.json"
                segments_path = os.path.join(job_dir, "segments.json")
                if not os.path.isfile(segments_path):
                    vibevoice_segments = f"{job_id}_segments.json"
                    segments_path = os.path.join(job_dir, vibevoice_segments)
                if os.path.isfile(segments_path):
                    with open(segments_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        result["segments"] = data.get("segments", [])
                else:
                    result["segments"] = []

                # List all files with sizes
                raw_files = [f for f in os.listdir(job_dir) if os.path.isfile(os.path.join(job_dir, f))]
                result["files"] = [
                    {"name": fn, "size": os.path.getsize(os.path.join(job_dir, fn))}
                    for fn in raw_files
                ]

        return result

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs from UUID folders (metadata or orphaned)."""
        import os as _os

        jobs = self._jm.list_all()
        terminal = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
        for job in jobs:
            status = JobStatus(job.get("status", ""))
            if status in terminal:
                job_id = job["job_id"]
                job_dir = _os.path.join(src.config.DATA_UPLOADS_DIR, job_id)
                if _os.path.isdir(job_dir):
                    current_files = job.get("files", [])
                    if current_files and isinstance(current_files[0], str):
                        # Rebuild string list with sizes
                        job["files"] = [
                            {"name": fn, "size": _os.path.getsize(_os.path.join(job_dir, fn))}
                            for fn in current_files
                        ]
                    elif not current_files:
                        job["files"] = [
                            {"name": fn, "size": _os.path.getsize(_os.path.join(job_dir, fn))}
                            for fn in _os.listdir(job_dir)
                            if _os.path.isfile(_os.path.join(job_dir, fn))
                        ]

        return jobs

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or processing job via queue manager."""
        return self._qm.cancel_job(job_id)

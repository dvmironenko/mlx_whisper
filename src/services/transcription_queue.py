"""Parallel transcription queue: ThreadPoolExecutor + bounded queue."""

import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from queue import Queue, Full
from typing import Any, Dict, Optional

from src.services.job_manager import JobManager, JobStatus
from src.config import TRANSCRIBER_WORKERS, QUEUE_MAX_SIZE
from src.utils.files import build_job_path

# Module-level references for worker methods — patchable at module level
import src.models.transcription as _transcription_module
from src.api.router import sanitize_result as _sanitize_result
from src.services.transcription_engines import get_engine

logger = logging.getLogger("mlx_whisper")


@dataclass
class JobPayload:
    job_id: str
    wav_path: str
    params: Dict[str, Any]
    cancelled: bool = field(default=False)


class TranscriptionQueueManager:
    """Singleton for parallel transcription via ThreadPoolExecutor + Queue."""

    _instance: Optional["TranscriptionQueueManager"] = None
    _lock = threading.Lock()
    _transcription_lock = threading.Lock()

    def __new__(cls, **kwargs) -> "TranscriptionQueueManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, workers: Optional[int] = None, max_size: Optional[int] = None):
        if self._initialized:
            return
        self._initialized = True
        self._workers = workers if workers is not None else TRANSCRIBER_WORKERS
        self._max_size = max_size if max_size is not None else QUEUE_MAX_SIZE
        self._queue: Queue = Queue(maxsize=self._max_size)
        self._executor = ThreadPoolExecutor(
            max_workers=self._workers, thread_name_prefix="transcriber"
        )
        self._meta = JobManager()
        self._shutdown = False
        self._worker_futures: list = []
        self._start_workers()

    def _start_workers(self) -> None:
        for i in range(self._workers):
            future = self._executor.submit(self._worker_loop, i)
            self._worker_futures.append(future)
        logger.info(
            f"TranscriptionQueueManager started: workers={self._workers}, "
            f"queue_max={self._max_size}"
        )

    def submit(self, payload: Dict[str, Any]) -> bool:
        """Submit a job to the queue. Returns False if queue is full or shutting down."""
        if self._shutdown:
            return False
        job_id = payload.get("job_id", str(uuid.uuid4()))
        wav_path = payload["wav_path"]
        params = payload.get("params", {})

        self._meta.create(
            job_id=job_id,
            source=payload.get("source", "upload"),
            original_filename=payload.get("original_filename"),
            model=params.get("model"),
            language=params.get("language"),
            task=params.get("task"),
            word_timestamps=params.get("word_timestamps", False),
            mechanism=params.get("mechanism"),
            duration=params.get("duration"),
        )

        try:
            job_payload = self._build_payload(job_id, wav_path, params)
            self._queue.put_nowait(job_payload)
            return True
        except Full:
            return False

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or processing job."""
        meta = self._meta.load(job_id)
        if meta is None:
            return False
        current = JobStatus(meta["status"])
        if current in (JobStatus.QUEUED, JobStatus.PROCESSING):
            self._meta.update_status(job_id, JobStatus.CANCELLED)
            return True
        return False

    def shutdown(self) -> None:
        """Graceful shutdown: stop workers and drain queue."""
        logger.info("TranscriptionQueueManager shutting down...")
        self._shutdown = True
        for future in self._worker_futures:
            try:
                future.result(timeout=30)
            except Exception:
                logger.warning("Worker did not complete within 30s timeout")
        self._executor.shutdown(wait=True)
        logger.info("TranscriptionQueueManager stopped")

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing). Shuts down existing instance if any."""
        instance = cls._instance
        if instance is not None:
            try:
                instance.shutdown()
            except Exception:
                pass
            instance._executor.shutdown(wait=False, cancel_futures=True)
        cls._instance = None

    def _build_payload(self, job_id: str, wav_path: str, params: Dict[str, Any]) -> JobPayload:
        return JobPayload(
            job_id=job_id,
            wav_path=wav_path,
            params=params,
            cancelled=False,
        )

    def _worker_loop(self, worker_id: int) -> None:
        """Main worker loop: get job → check cancelled → transcribe → update."""
        logger.info(f"Worker {worker_id} started")
        while not self._shutdown:
            try:
                job = self._queue.get(timeout=1.0)
            except Exception:
                continue

            # Check cancelled before processing
            meta = self._meta.load(job.job_id)
            if meta and meta["status"] == JobStatus.CANCELLED.value:
                self._queue.task_done()
                logger.info(f"Worker {worker_id}: job {job.job_id} cancelled, skipping")
                continue

            # Mark as processing
            self._meta.update_status(job.job_id, JobStatus.PROCESSING)
            logger.info(f"Worker {worker_id}: processing job {job.job_id}")

            try:
                self._worker_process(job)
                logger.info(f"Worker {worker_id}: job {job.job_id} completed")
            except Exception as e:
                logger.error(f"Worker {worker_id}: job {job.job_id} failed: {e}")
                self._meta.update_status(job.job_id, JobStatus.FAILED, error=str(e))
            finally:
                self._queue.task_done()

        logger.info(f"Worker {worker_id} stopped")

    def _worker_process(self, job: JobPayload) -> None:
        """Process one job: call engine.transcribe() with lock."""
        import time

        mechanism = job.params.get("mechanism", "whisper")
        start = time.time()
        try:
            with self._transcription_lock:
                engine = get_engine(mechanism)
                result = engine.transcribe(
                    file_path=job.wav_path,
                    language=job.params.get("language"),
                    task=job.params.get("task", "transcribe"),
                    model=job.params.get("model", "large"),
                    word_timestamps=job.params.get("word_timestamps", False),
                    condition_on_previous_text=job.params.get(
                        "condition_on_previous_text", True
                    ),
                    no_speech_threshold=job.params.get("no_speech_threshold"),
                    hallucination_silence_threshold=job.params.get(
                        "hallucination_silence_threshold"
                    ),
                    initial_prompt=job.params.get("initial_prompt"),
                )
            duration = time.time() - start
            result = _sanitize_result(result)
            result["transcription_duration"] = round(duration, 2)

            # Сохранить результат транскрипции в файлы
            job_dir = build_job_path(job.job_id)
            original_filename = job.params.get("original_filename", job.job_id)
            # Strip extension to match old naming convention (e.g. "test" not "test.wav")
            base_name = os.path.splitext(original_filename)[0]
            text_content = result.get("text", "")
            if text_content:
                txt_path = os.path.join(job_dir, f"{base_name}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text_content)

            segments = result.get("segments")
            if segments:
                segments_json_path = os.path.join(job_dir, f"{base_name}_segments.json")
                with open(segments_json_path, "w", encoding="utf-8") as f:
                    json.dump({"segments": segments}, f, ensure_ascii=False, indent=2)

            # Save raw API response
            raw_response = result.get("raw_response")
            if raw_response:
                raw_path = os.path.join(job_dir, f"{base_name}_raw.json")
                if isinstance(raw_response, dict):
                    raw_response = json.dumps(raw_response, ensure_ascii=False, indent=2)
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(raw_response)

            # Check if cancelled during processing
            status = self._meta.load(job.job_id)
            final_status = (
                JobStatus.CANCELLED
                if status and status["status"] == JobStatus.CANCELLED.value
                else JobStatus.COMPLETED
            )

            self._meta.update_status(
                job.job_id,
                final_status,
                transcription_duration=duration,
                result_file=result.get("result_file"),
            )

        except Exception as e:
            logger.error(f"Transcription failed for {job.job_id}: {e}")
            self._meta.update_status(job.job_id, JobStatus.FAILED, error=str(e))
            raise
        finally:
            if mechanism == "whisper":
                _transcription_module._clear_memory()


# Module-level singleton accessor
def get_transcription_manager() -> TranscriptionQueueManager:
    """Lazy accessor for the TranscriptionQueueManager singleton."""
    if TranscriptionQueueManager._instance is None:
        TranscriptionQueueManager()  # type: ignore[unreachable]
    return TranscriptionQueueManager._instance  # type: ignore[return-value]

"""Job status enum и менеджер job metadata для параллельной транскрипции."""

import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from src.config import JOB_METADATA_DIR

os.makedirs(JOB_METADATA_DIR, exist_ok=True)


def _job_file(job_id: str) -> str:
    return os.path.join(JOB_METADATA_DIR, f"{job_id}.json")


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value


class JobManager:
    """Singleton для управления job metadata в filesystem."""

    _instance: Optional["JobManager"] = None

    def __new__(cls) -> "JobManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create(
        self,
        job_id: Optional[str] = None,
        source: str = "upload",
        **extra,
    ) -> Dict[str, Any]:
        if job_id is None:
            job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        metadata: Dict[str, Any] = {
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "source": source,
            "created_at": now,
            "updated_at": now,
            "original_filename": None,
            "model": None,
            "language": None,
            "task": None,
            "word_timestamps": False,
            "duration": None,
            "transcription_duration": None,
            "result_file": None,
            "error": None,
        }
        metadata.update(extra)
        self._save(job_id, metadata)
        return metadata

    def update_status(
        self, job_id: str, status: JobStatus, **extra
    ) -> Optional[Dict[str, Any]]:
        metadata = self.load(job_id)
        if metadata is None:
            return None
        metadata["status"] = status.value
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata.update(extra)
        self._save(job_id, metadata)
        return metadata

    def load(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = _job_file(job_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def cancel(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.update_status(job_id, JobStatus.CANCELLED)

    def list_all(self) -> list[Dict[str, Any]]:
        result: list[Dict[str, Any]] = []
        if not os.path.exists(JOB_METADATA_DIR):
            return result
        for fname in sorted(os.listdir(JOB_METADATA_DIR)):
            if fname.endswith(".json"):
                fpath = os.path.join(JOB_METADATA_DIR, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    result.append(json.load(f))
        return sorted(result, key=lambda j: j.get("created_at", ""), reverse=True)

    def _save(self, job_id: str, metadata: Dict[str, Any]) -> None:
        path = _job_file(job_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

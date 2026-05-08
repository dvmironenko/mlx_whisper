"""Job status enum и менеджер job metadata для параллельной транскрипции."""

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from src.config import DATA_UPLOADS_DIR

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _job_file(job_id: str) -> str:
    return os.path.join(DATA_UPLOADS_DIR, job_id, f"{job_id}.json")


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
        if not os.path.exists(DATA_UPLOADS_DIR):
            return result
        for entry in sorted(os.listdir(DATA_UPLOADS_DIR)):
            if not _UUID_RE.match(entry):
                continue
            job_dir = os.path.join(DATA_UPLOADS_DIR, entry)
            if not os.path.isdir(job_dir):
                continue
            metadata_path = _job_file(entry)
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        result.append(json.load(f))
                except (json.JSONDecodeError, OSError):
                    continue
            else:
                # No metadata — folder exists, treat as orphaned
                job_dir_files = os.listdir(job_dir)
                txt_files = [f for f in job_dir_files if f.endswith(".txt") and "segments" not in f]
                result.append({
                    "job_id": entry,
                    "status": JobStatus.COMPLETED.value if txt_files else JobStatus.FAILED.value,
                    "source": "upload",
                    "created_at": "",
                    "updated_at": "",
                    "original_filename": None,
                    "model": None,
                    "language": None,
                    "task": None,
                    "word_timestamps": False,
                    "duration": None,
                    "transcription_duration": None,
                    "result_file": None,
                    "error": None,
                    "files": [
                        {"name": fn, "size": os.path.getsize(os.path.join(job_dir, fn))}
                        for fn in job_dir_files
                    ],
                    "_orphaned": True,
                })
        return sorted(result, key=lambda j: j.get("created_at", ""), reverse=True)

    def _save(self, job_id: str, metadata: Dict[str, Any]) -> None:
        path = _job_file(job_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def delete(self, job_id: str) -> bool:
        """Удалить задание целиком (всю папку с файлами)."""
        job_dir = os.path.join(DATA_UPLOADS_DIR, job_id)
        if os.path.isdir(job_dir):
            shutil.rmtree(job_dir)
            return True
        return False

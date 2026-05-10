"""Тесты для TranscriptionQueueManager."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Переопределяем JOB_METADATA_DIR на временную директорию
_test_dir: str | None = None


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch, tmp_path):
    global _test_dir
    _test_dir = str(tmp_path)
    monkeypatch.setattr("src.config.DATA_UPLOADS_DIR", _test_dir)
    os.makedirs(os.path.join(_test_dir, "jobs"), exist_ok=True)
    monkeypatch.setenv("TRANSCRIBER_WORKERS", "1")
    monkeypatch.setenv("QUEUE_MAX_SIZE", "5")
    yield
    # Cleanup
    try:
        import shutil
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_manager():
    """Сбросить синглтон TranscriptionQueueManager перед каждым тестом."""
    from src.services.transcription_queue import TranscriptionQueueManager
    TranscriptionQueueManager.reset()
    yield
    # Teardown: гарантированно сбрасываем синглтон
    # Каждая функция сама вызывает mgr.shutdown() в finally
    TranscriptionQueueManager.reset()


@pytest.fixture(autouse=True)
def no_clear_memory(monkeypatch):
    """Убрать mx.clear_cache() из воркеров — он блокирует thread notification в pytest."""
    import src.models.transcription as _mod
    monkeypatch.setattr(_mod, "_clear_memory", lambda: None)




def test_submit_and_process():
    """Job поднимается в очередь, worker обрабатывает, статус обновляется."""
    from src.services.transcription_queue import TranscriptionQueueManager
    from src.services.job_manager import JobStatus

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    try:
        # Моки применяем ДО submit, чтобы воркер поймал их при обработке
        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = {
            "text": "mock result", "segments": [], "raw_response": None
        }
        with (
            patch("src.services.transcription_queue.get_engine", return_value=mock_engine),
            patch(
                "src.services.transcription_queue._sanitize_result",
                side_effect=lambda r: r,
            ),
        ):

            result = mgr.submit({
                "job_id": "test-job-1",
                "wav_path": "/tmp/test.wav",
                "params": {"model": "turbo"},
            })
            assert result is True

            # Дождёмся обработки через опрос queue (вместо future.result,
            # который вешается из-за race condition в ThreadPoolExecutor callback)
            mgr._queue.join()

        status = mgr._meta.load("test-job-1")
        assert status is not None
        assert status["status"] == "completed"
        assert status["transcription_duration"] is not None
    finally:
        mgr.shutdown()


def test_queue_full_returns_false(monkeypatch):
    """При переполнении очереди submit возвращает False."""
    from queue import Full

    from src.services.transcription_queue import TranscriptionQueueManager

    # Патчим put_nowait на экземпляре очереди — raises Full
    # Это симулирует полное заполнение очереди без гонки с воркером
    monkeypatch.setattr("queue.Queue.put_nowait", lambda self, item: (_ for _ in ()).throw(Full()))

    mgr = TranscriptionQueueManager(workers=1, max_size=1)
    try:
        # submit создаст job metadata, попытается put_nowait — будет Full
        result = mgr.submit({
            "job_id": "job-full-1",
            "wav_path": "/tmp/test.wav",
            "params": {"model": "turbo"},
        })
        assert result is False
    finally:
        mgr.shutdown()


def test_worker_process_cancelled():
    """Cancel processing job: worker завершает и ставит cancelled."""
    from src.services.transcription_queue import TranscriptionQueueManager
    from src.services.job_manager import JobStatus

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    try:
        # Создаём job metadata вручную
        meta_mgr = mgr._meta
        meta_mgr.create(
            job_id="cancel-job-1",
            source="upload",
            original_filename="test.wav",
            model="turbo",
        )
        meta_mgr.update_status("cancel-job-1", JobStatus.PROCESSING)
        mgr.cancel_job("cancel-job-1")

        # Вызываем _worker_process напрямую (без запуска воркера)
        job_payload = mgr._build_payload(
            "cancel-job-1",
            "/tmp/test.wav",
            {"model": "turbo"},
        )

        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = {
            "text": "cancelled result", "segments": [], "raw_response": None
        }
        with (
            patch("src.services.transcription_queue.get_engine", return_value=mock_engine),
            patch(
                "src.services.transcription_queue._sanitize_result",
                side_effect=lambda r: r,
            ),
        ):
            mgr._worker_process(job_payload)

        status = meta_mgr.load("cancel-job-1")
        assert status["status"] == "cancelled"
    finally:
        mgr.shutdown()


def test_singleton():
    """TranscriptionQueueManager — singleton."""
    from src.services.transcription_queue import TranscriptionQueueManager

    # Создаём экземпляр
    TranscriptionQueueManager(workers=1, max_size=5)
    # Второй вызов должен вернуть тот же экземпляр
    mgr2 = TranscriptionQueueManager(workers=999, max_size=999)
    assert mgr2 is TranscriptionQueueManager._instance
    # Параметры не должны измениться (singleton)
    assert mgr2._workers == 1
    assert mgr2._max_size == 5
    mgr2.shutdown()


def test_submit_persists_mechanism():
    """Submit с mechanism сохраняет поле в метаданные."""
    from src.services.transcription_queue import TranscriptionQueueManager

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    try:
        result = mgr.submit({
            "job_id": "mech-job-1",
            "wav_path": "/tmp/test.wav",
            "params": {"mechanism": "vibevoice", "model": "turbo"},
        })
        assert result is True

        meta = mgr._meta.load("mech-job-1")
        assert meta is not None
        assert meta["mechanism"] == "vibevoice"
        assert meta["model"] == "turbo"
    finally:
        mgr.shutdown()


def test_submit_default_mechanism_is_none():
    """Submit без mechanism устанавливает mechanism в None."""
    from src.services.transcription_queue import TranscriptionQueueManager

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    try:
        result = mgr.submit({
            "job_id": "mech-job-2",
            "wav_path": "/tmp/test.wav",
            "params": {"model": "base"},
        })
        assert result is True

        meta = mgr._meta.load("mech-job-2")
        assert meta is not None
        assert meta["mechanism"] is None
    finally:
        mgr.shutdown()


def test_cancel_nonexistent():
    """Cancel nonexistent job returns False."""
    from src.services.transcription_queue import TranscriptionQueueManager

    mgr = TranscriptionQueueManager(workers=1, max_size=5)
    try:
        result = mgr.cancel_job("does-not-exist")
        assert result is False
    finally:
        mgr.shutdown()

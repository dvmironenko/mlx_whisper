"""OMLXEngine — механизм транскрибации через oMLX API."""

from __future__ import annotations

import json
import logging
import math
import re
import struct
from io import BytesIO

import time

import requests as _requests
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from pydub import AudioSegment  # noqa: F401

from src.config import (
    OMLX_API_KEY,
    OMLX_BASE_URL,
    OMLX_MODEL,
    OMLX_ENABLED,
)
from src.services.whisper_engines import (
    TranscriptionEngine,
    _build_formatted_text_from_segments,
)

logger = logging.getLogger("mlx_whisper")


class OMLXModelNotFoundError(Exception):
    """Модель не найдена в oMLX API."""
    pass


# Константы splitting
MAX_AUDIO_DURATION_SEC: int = 5 * 60  # 5 минут
SILENCE_THRESHOLD_DB: int = 40


# Максимальный размер аудио для одного запроса к oMLX (50 MB)
MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024


def _detect_silence_chunks(
    audio_segment: "AudioSegment",
    chunk_duration_ms: int = 100,
    silence_threshold_db: int = -40,
    gap_ms: int = 2000,
) -> List[Tuple[int, int]]:
    """Обход аудио чанками, возврат не-тихих интервалов в миллисекундах.

    Использует raw samples pydub AudioSegment — без librosa/numpy.
    """
    raw_bytes = audio_segment.raw_data
    assert raw_bytes is not None, "raw_data must not be None"
    sample_width = audio_segment.sample_width
    num_samples = len(raw_bytes) // (sample_width * audio_segment.channels)
    fmt = f"<{num_samples}{'h' if sample_width == 2 else 'i'}"
    samples = struct.unpack(fmt, raw_bytes)
    if audio_segment.channels > 1:
        samples = samples[::2]
        num_samples = len(samples)

    chunk_size = max(1, int(chunk_duration_ms * audio_segment.frame_rate / 1000))
    non_silent: List[Tuple[int, int]] = []

    for i in range(0, num_samples, chunk_size):
        chunk = samples[i : i + chunk_size]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
        if rms > 0:
            db = 20 * math.log10(rms / 32768.0)
            if db > silence_threshold_db:
                start_ms = i * 1000 // audio_segment.frame_rate
                end_ms = (i + len(chunk)) * 1000 // audio_segment.frame_rate
                non_silent.append((start_ms, end_ms))

    if not non_silent:
        return []

    merged: List[Tuple[int, int]] = [non_silent[0]]
    for start, end in non_silent[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= gap_ms:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def _split_audio_by_silence(
    file_path: str,
    max_duration_sec: int = MAX_AUDIO_DURATION_SEC,
) -> Tuple[List[Tuple[int, int, bytes]], int]:
    """
    Разбить аудио на сегменты по тишине и максимальной длительности.

    Использует только pydub — без librosa/numpy.

    Returns
    -------
    list of (start_ms, end_ms, audio_bytes)
    sample_rate: частота дискретизации из pydub AudioSegment
    """
    from pydub import AudioSegment  # noqa: F401

    try:
        audio = AudioSegment.from_file(file_path)
    except Exception as e:
        logger.error(f"Failed to load audio with pydub: {e}")
        return [(0, -1, b"")], 16000

    non_silent = _detect_silence_chunks(
        audio,
        gap_ms=int(2.0 * 1000),
    )

    if not non_silent:
        return [(0, -1, b"")], audio.frame_rate

    result: List[Tuple[int, int, bytes]] = []
    max_duration_ms = max_duration_sec * 1000

    for start_ms, end_ms in non_silent:
        duration_ms = end_ms - start_ms

        if duration_ms <= max_duration_ms:
            segment = audio[start_ms:end_ms]
            buf = BytesIO()
            segment.export(buf, format="opus")
            result.append((start_ms, end_ms, buf.getvalue()))
        else:
            for chunk_start in range(0, duration_ms, max_duration_ms):
                chunk_end = min(chunk_start + max_duration_ms, duration_ms)
                abs_start = start_ms + chunk_start
                abs_end = start_ms + chunk_end
                segment = audio[abs_start:abs_end]
                buf = BytesIO()
                segment.export(buf, format="opus")
                result.append((abs_start, -1, buf.getvalue()))

    return result, audio.frame_rate


def _normalize_segments(items: Any) -> Optional[List[Dict[str, Any]]]:
    """Нормализовать список сырых сегментов в единый формат.

    Поддерживает два формата ответа API:

    Новый формат (whisper-large-v3-*):
    {
        "text": "...",
        "language": "ru",
        "segments": [{"start":0,"end":12.67,"text":"..."}]
    }

    Старый формат (VibeVoice):
    {
        "text": "[{\"Start\":0,\"End\":12.67,\"Speaker\":0,\"Content\":\"...\"}]",
        "language": "ru"
    }
    """
    segments: List[Dict[str, Any]] = []

    # Новый формат: segments в отдельном поле
    if isinstance(items, dict):
        raw_segments = items.get("segments")
        if isinstance(raw_segments, list) and len(raw_segments) > 0:
            # Проверяем, содержат ли сегменты информацию о спикерах
            # (Whisper-формат не включает speaker, VibeVoice-формат включает)
            has_speaker = any(
                isinstance(s, dict) and ("Speaker" in s or "speaker" in s)
                for s in raw_segments
            )
            if has_speaker:
                items = raw_segments
            else:
                # Сегменты без speaker — берём данные из text поля
                text_field = items.get("text", "")
                if isinstance(text_field, str) and text_field.startswith("["):
                    try:
                        items = json.loads(text_field)
                    except (json.JSONDecodeError, ValueError):
                        items = _repair_truncated_json(text_field)
                        if items is None:
                            return None
                else:
                    items = raw_segments
        else:
            # Старый формат: извлекаем JSON-строку из поля "text"
            text_field = items.get("text", "")
            if isinstance(text_field, str) and text_field.startswith("["):
                try:
                    items = json.loads(text_field)
                except (json.JSONDecodeError, ValueError):
                    items = _repair_truncated_json(text_field)
                    if items is None:
                        return None
            else:
                return None

    if not isinstance(items, list):
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        start = float(item.get("Start", item.get("start", 0)))
        end = float(item.get("End", item.get("end", 0)))
        speaker = int(item.get("Speaker", item.get("speaker", 0)))
        content = str(item.get("Content", item.get("content", item.get("text", ""))))
        segments.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "text": content,
        })
    return segments if segments else None


def _repair_truncated_json(text_field: str) -> Optional[List[Dict[str, Any]]]:
    """Восстановить сегменты из обрезанного JSON-строки.

    API может обрезать поле "text" посередине строки для длинных сегментов.
    Восстанавливаем каждый сегмент, находя границы по паттерну {"Start":...
    и закрывая Content строку по последней кавычке.
    """
    pattern = r'\{\"Start":\d+\.?\d*,\"End":\d+\.?\d*,\"Speaker":\d+,\"Content":"'
    matches = list(re.finditer(pattern, text_field))

    if not matches:
        return None

    segments: List[Dict[str, Any]] = []

    for i, match in enumerate(matches):
        seg_start = match.start()
        # Конец сегмента — начало следующего или конец строки
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else len(text_field)
        segment_str = text_field[seg_start:seg_end]

        # Убираем trailing мусор после последней закрывающей кавычки Content
        content_start = segment_str.rfind('"Content":"')
        if content_start >= 0:
            content_start += len('"Content":"')
            content_text = segment_str[content_start:]
            last_quote = content_text.rfind('"')
            if last_quote > 0:
                # Нашли последнюю кавычку в Content — обрезаем до неё
                content_text = content_text[:last_quote]
                segment_str = segment_str[:content_start] + content_text + '"}'

        # Пробуем распарсить восстановленный сегмент
        try:
            seg_dict = json.loads(segment_str)
            if isinstance(seg_dict, dict):
                segments.append(seg_dict)
        except (json.JSONDecodeError, ValueError):
            # Не удалось восстановить — пропускаем сегмент
            continue

    return segments if segments else None


def _reconcile_speaker_ids(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Переназначить speaker IDs на глобальные.

    API возвращает локальные ID для каждого сегмента независимо.
    Эта функция маппит их в единые глобальные ID по порядку первого появления.
    """
    local_to_global: Dict[int, int] = {}
    next_global = 0

    for seg in segments:
        local_id = int(seg.get("speaker", seg.get("speaker_id", 0)))
        if local_id not in local_to_global:
            local_to_global[local_id] = next_global
            next_global += 1
        seg["speaker"] = local_to_global[local_id]

    return segments



class OMLXEngine(TranscriptionEngine):
    """Механизм транскрибации через oMLX API."""

    def transcribe(self, file_path: str, **params) -> Dict[str, Any]:
        """
        Транскрибировать аудиофайл через oMLX API.

        Параметры, специфичные для oMLX:
        - language: язык аудио
        - include_timestamps: включать ли временные метки в текст
        """
        include_timestamps = params.get("include_timestamps", True)
        omlx_model = params.get("model")
        if not OMLX_ENABLED or not OMLX_BASE_URL:
            raise RuntimeError("oMLX не настроен: проверьте OMLX_BASE_URL и OMLX_ENABLED")

        language = params.get("language")
        start_time = time.time()

        # Разбиваем аудио на сегменты
        segments_files, _ = _split_audio_by_silence(file_path)
        all_segments: List[Dict[str, Any]] = []

        for start_ms, _, audio_bytes in segments_files:
            try:
                seg_result = self._transcribe_segment(audio_bytes, language=language, model=omlx_model)
            except OMLXModelNotFoundError:
                # Модель не найдена — все сегменты упадут с той же ошибкой
                raise
            except Exception as e:
                logger.error(f"Segment transcription failed: {e}")
                continue

            # Корректировка временных меток по сдвигу сегмента
            if start_ms > 0:
                offset_sec = start_ms / 1000.0
                for seg in seg_result["segments"]:
                    seg["start"] += offset_sec
                    seg["end"] += offset_sec

            all_segments.extend(seg_result["segments"])

        # Рехилиация speaker IDs — маппинг локальных ID в глобальные
        all_segments = _reconcile_speaker_ids(all_segments)

        duration = time.time() - start_time

        formatted_text = _build_formatted_text_from_segments(
            all_segments, include_timestamps=include_timestamps
        )

        return {
            "segments": all_segments,
            "text": formatted_text,
            "speaker_detected": bool(
                all_segments and any(s.get("speaker", 0) != 0 for s in all_segments)
            ),
            "transcription_duration": round(duration, 2),
            "raw_response": None,
        }

    def _transcribe_segment(self, audio_bytes: bytes, filename: str = "segment.opus", language: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """Транскрибировать один сегмент через oMLX API."""
        url = f"{OMLX_BASE_URL}/audio/transcriptions"

        bio = BytesIO(audio_bytes)
        files = {"file": (filename, bio, "audio/opus")}
        data: Dict[str, Any] = {"model": model or OMLX_MODEL, "diarize": True}
        if language:
            data["language"] = language

        headers: Dict[str, str] = {}
        if OMLX_API_KEY:
            headers["Authorization"] = f"Bearer {OMLX_API_KEY}"

        response = _requests.post(
            url, files=files, data=data, headers=headers, timeout=(10, 3600)
        )

        # Явная обработка 404 not_found_error от OMLX — до raise_for_status()
        if response.status_code == 404:
            try:
                error_body = response.json()
                if error_body.get("error", {}).get("type") == "not_found_error":
                    raise OMLXModelNotFoundError(
                        f"Модель '{OMLX_MODEL}' не найдена в oMLX API. "
                        f"Проверьте конфигурацию OMLX_MODEL."
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

        response.raise_for_status()

        raw_text = response.text
        items = json.loads(raw_text)
        logger.info(f"oMLX raw response (first 500): {raw_text[:500]}")
        segments = _normalize_segments(items) or []
        # Debug: log speaker distribution
        if segments:
            speaker_counts: Dict[int, int] = {}
            for seg in segments:
                sid = seg.get("speaker", 0)
                speaker_counts[sid] = speaker_counts.get(sid, 0) + 1
            logger.info(f"oMLX diarization result: {dict(speaker_counts)}")
        text = "\n".join(seg["text"] for seg in segments)

        if not segments:
            logger.warning(
                f"oMLX API returned empty segments "
                f"(raw response length: {len(raw_text)}, items count: {len(items) if isinstance(items, list) else 'N/A'})"
            )

        return {
            "segments": segments,
            "text": text,
            "raw_response": raw_text,
        }

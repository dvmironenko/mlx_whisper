"""VibeVoiceEngine — механизм транскрибации через oMLX API (VibeVoice-ASR)."""

from __future__ import annotations

import json
import logging
import os
import re

import tempfile
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
MAX_AUDIO_DURATION_SEC: int = 50 * 60  # 50 минут
SILENCE_THRESHOLD_DB: int = 40


# Максимальный размер аудио для одного запроса к oMLX (100 MB)
MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024


def _split_audio_by_silence(
    file_path: str,
    max_duration_sec: int = MAX_AUDIO_DURATION_SEC,
) -> Tuple[List[Tuple[int, int, str]], int]:
    """
    Разбить аудио на сегменты по тишине и максимальной длительности.

    Returns
    -------
    list of (start_sample, end_sample, segment_path)
    """
    import librosa
    from pydub import AudioSegment  # noqa: F401

    sr = 16000
    try:
        audio, sr_float = librosa.load(file_path, sr=None, mono=False)
        sr = int(sr_float)
        # librosa.load с mono=False возвращает stereo, берём первый канал
        if audio.ndim > 1:
            audio = audio[0]
    except Exception as e:
        logger.error(f"Failed to load audio with librosa: {e}")
        return [(0, -1, file_path)], sr

    try:
        segments_raw = librosa.effects.split(audio, top_db=SILENCE_THRESHOLD_DB)
    except Exception as e:
        logger.error(f"librosa.effects.split failed: {e}")
        return [(0, -1, file_path)], sr

    if not len(segments_raw):
        return [(0, -1, file_path)], sr

    # Конвертируем numpy array в list of tuples
    intervals_raw = segments_raw.tolist()
    intervals: List[Tuple[int, int]] = [  # type: ignore[assignment]
        (int(s), int(e)) for s, e in intervals_raw
    ]
    # Группируем интервалы с паузами < 2 сек
    grouped = _group_intervals(intervals, gap_samples=int(2.0 * sr))

    result: List[Tuple[int, int, str]] = []
    pydub_audio = AudioSegment.from_file(file_path)

    for start_s, end_s in grouped:
        duration_samples = end_s - start_s
        duration_sec = duration_samples / sr

        if duration_sec <= max_duration_sec:
            # Один сегмент помещается в лимит
            t0 = start_s / sr * 1000  # ms
            t1 = end_s / sr * 1000
            segment = pydub_audio[t0:t1]
            result.append((start_s, end_s, _save_segment(segment)))
        else:
            # Разбиваем на части по max_duration_sec
            total_ms = int(duration_sec * 1000)
            t_start = start_s / sr * 1000
            offset_samples = start_s
            for chunk_start_ms in range(0, total_ms, max_duration_sec * 1000):
                chunk_end_ms = min(chunk_start_ms + max_duration_sec * 1000, total_ms)
                abs_start = t_start + chunk_start_ms
                abs_end = t_start + chunk_end_ms
                segment = pydub_audio[int(abs_start):int(abs_end)]
                seg_start_samples = offset_samples + int(chunk_start_ms / 1000 * sr)
                result.append((seg_start_samples, -1, _save_segment(segment)))

    return result, sr


def _group_intervals(
    intervals: List[Tuple[int, int]],
    gap_samples: int = int(2.0 * 16000),
) -> List[Tuple[int, int]]:
    """Сливаем интервалы, между которыми пауза < gap_samples."""
    if not intervals:
        return []

    merged: List[Tuple[int, int]] = [(intervals[0][0], intervals[0][1])]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= gap_samples:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def _save_segment(segment: AudioSegment) -> str:
    """Сохранить сегмент во временный WAV файл."""
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="vv_segment_")
    os.close(fd)
    try:
        segment.export(path, format="wav")
    except Exception as e:
        logger.error(f"Failed to export segment: {e}")
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path



def _normalize_segments(items: Any) -> Optional[List[Dict[str, Any]]]:
    """Нормализовать список сырых сегментов в единый формат.

    API возвращает dict:
    {
        "text": "[{\"Start\":0,\"End\":12.67,\"Speaker\":0,\"Content\":\"...\"}]",
        "language": "ru",
        "segments": [{"start":0,"end":12.67,"speaker_id":0,"text":"..."}]
    }

    Для длинных сегментов поле "text" может быть обрезано — в этом случае
    выполняется восстановление сегментов через regex.
    """
    segments: List[Dict[str, Any]] = []

    # API возвращает dict — извлекаем JSON-строку из поля "text"
    if isinstance(items, dict):
        text_field = items.get("text", "")
        if isinstance(text_field, str) and text_field.startswith("["):
            try:
                items = json.loads(text_field)
            except (json.JSONDecodeError, ValueError):
                # JSON обрезан — пробуем восстановить сегменты через regex
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
        content = str(item.get("Content", item.get("content", "")))
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



class VibeVoiceEngine(TranscriptionEngine):
    """Механизм транскрибации через oMLX API (VibeVoice-ASR)."""

    def transcribe(self, file_path: str, **params) -> Dict[str, Any]:
        """
        Транскрибировать аудиофайл через oMLX API.

        Параметры, специфичные для VibeVoice:
        - language: язык аудио
        """
        if not OMLX_ENABLED or not OMLX_BASE_URL:
            raise RuntimeError("oMLX не настроен: проверьте OMLX_BASE_URL и OMLX_ENABLED")

        language = params.get("language")
        start_time = time.time()

        # Разбиваем аудио на сегменты
        segments_files, sr = _split_audio_by_silence(file_path)
        all_segments: List[Dict[str, Any]] = []

        for seg_start_samples, _, seg_path in segments_files:
            try:
                seg_result = self._transcribe_segment(seg_path, language)
            except OMLXModelNotFoundError:
                # Модель не найдена — все сегменты упадут с той же ошибкой
                raise
            except Exception as e:
                logger.error(f"Segment transcription failed: {e}")
                continue

            # Корректировка временных меток по сдвигу сегмента
            if seg_start_samples > 0:
                offset_sec = seg_start_samples / sr
                for seg in seg_result["segments"]:
                    seg["start"] += offset_sec
                    seg["end"] += offset_sec

            all_segments.extend(seg_result["segments"])

        duration = time.time() - start_time

        formatted_text = _build_formatted_text_from_segments(all_segments, include_speaker=True)

        return {
            "segments": all_segments,
            "text": formatted_text,
            "speaker_detected": bool(
                all_segments and any(s.get("speaker", 0) != 0 for s in all_segments)
            ),
            "transcription_duration": round(duration, 2),
            "raw_response": None,
        }

    def _transcribe_segment(self, file_path: str, language: Optional[str]) -> Dict[str, Any]:
        """Транскрибировать один сегмент через oMLX API."""
        url = f"{OMLX_BASE_URL}/audio/transcriptions"

        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
            data: Dict[str, Any] = {"model": OMLX_MODEL}
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
        segments = _normalize_segments(items) or []
        text = "\n".join(seg["text"] for seg in segments)

        if not segments:
            fd, raw_debug_path = tempfile.mkstemp(suffix=".json", prefix="vv_debug_")
            os.close(fd)
            with open(raw_debug_path, "w") as f:
                f.write(raw_text)
            logger.warning(
                f"VibeVoice API returned empty segments for {os.path.basename(file_path)} "
                f"(raw response length: {len(raw_text)}, items count: {len(items) if isinstance(items, list) else 'N/A'}, "
                f"debug saved to {raw_debug_path})"
            )
            try:
                os.unlink(raw_debug_path)
            except OSError:
                pass

        return {
            "segments": segments,
            "text": text,
            "raw_response": raw_text,
        }

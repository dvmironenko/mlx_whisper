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
from src.services.transcription_engines import TranscriptionEngine

logger = logging.getLogger("mlx_whisper")

# Константы splitting
MAX_AUDIO_DURATION_SEC: int = 50 * 60  # 50 минут
SILENCE_THRESHOLD_DB: int = 40

# Паттерн для fallback парсинга текста
_SPEAKER_PATTERN = re.compile(
    r"\[(\d{2}):(\d{2})\]\s+Speaker\s+(\d+):\s*(.*)"
)

# Максимальный размер аудио для одного запроса к oMLX (100 MB)
MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024


def _split_audio_by_silence(
    file_path: str,
    max_duration_sec: int = MAX_AUDIO_DURATION_SEC,
) -> List[Tuple[int, int, str]]:
    """
    Разбить аудио на сегменты по тишине и максимальной длительности.

    Returns
    -------
    list of (start_sample, end_sample, segment_path)
    """
    import librosa
    from pydub import AudioSegment  # noqa: F401

    try:
        audio, sr = librosa.load(file_path, sr=None, mono=False)
        # librosa.load с mono=False возвращает stereo, берём первый канал
        if audio.ndim > 1:
            audio = audio[0]
    except Exception as e:
        logger.error(f"Failed to load audio with librosa: {e}")
        return [(0, -1, file_path)]

    try:
        segments_raw = librosa.effects.split(audio, top_db=SILENCE_THRESHOLD_DB)
    except Exception as e:
        logger.error(f"librosa.effects.split failed: {e}")
        return [(0, -1, file_path)]

    if not len(segments_raw):
        return [(0, -1, file_path)]

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

    return result


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


def _split_concatenated_json(text: str) -> List[str]:
    """Разбить строку на отдельные JSON-объекты (возможно, склеенные)."""
    decoder = json.JSONDecoder()
    text = text.strip()
    objects: List[str] = []
    idx = 0
    while idx < len(text):
        # Пропуск пробелов/переносов строк
        while idx < len(text) and text[idx] in (" ", "\t", "\n", "\r"):
            idx += 1
        if idx >= len(text):
            break
        if text[idx] != "{":
            # Не JSON-объект, ищем следующий '{'
            next_brace = text.find("{", idx + 1)
            if next_brace == -1:
                break
            idx = next_brace
            continue
        try:
            _, end_idx = decoder.raw_decode(text, idx)
            objects.append(text[idx:end_idx])
            idx = end_idx
        except (json.JSONDecodeError, ValueError):
            # Ищем следующий '{' и пробуем снова
            next_brace = text.find("{", idx + 1)
            if next_brace == -1:
                break
            idx = next_brace
    return objects


def _extract_segments_from_truncated_text(text_field: str) -> List[Dict[str, Any]]:
    """Извлечь сегменты из текстового поля, даже если оно обрезано.

    text_field содержит JSON-массив сегментов, например:
    '[{"Start":0,"End":1.22,"Speaker":0,"Content":"..."}, ...]'
    Последний сегмент может быть обрезан (без закрывающей скобки).
    """
    segments: List[Dict[str, Any]] = []
    # Ищем все объекты сегментов по паттерну {"Start":...
    seg_pattern = re.compile(
        r'\{"Start"\s*:\s*([\d.]+)'
        r'(?:\s*,\s*"End"\s*:\s*([\d.]+))?'
        r'(?:\s*,\s*"Speaker"\s*:\s*(\d+))?'
        r'(?:\s*,\s*"Content"\s*:\s*"([^"]*(?:\\"[^"]*)*)")?'
        r"\s*\}"
    )
    for m in seg_pattern.finditer(text_field):
        start = float(m.group(1))
        end = float(m.group(2)) if m.group(2) else start
        speaker = int(m.group(3)) if m.group(3) else 0
        content = m.group(4) if m.group(4) else ""
        content = content.replace('\\"', '"')
        segments.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "text": content,
        })
    return segments


def _parse_segments_from_json(raw_text: str) -> Optional[List[Dict[str, Any]]]:
    """Парсить JSON-массив сегментов или конкатенированные JSON-объекты от oMLX API.

    Поддерживаемые форматы:
    1. Прямой JSON-массив: [{\"Start\":...}]
    2. Конкатенированные объекты oMLX: {\"text\":\"[{...}]\"}{\"text\":\"[{...}]\"}
    3. JSON в code block: ```json\n...\n```
    """
    # Иногда oMLX возвращает JSON в строке с escape-символами
    for wrapper in ["```json\n", "```"]:
        if wrapper in raw_text:
            raw_text = raw_text.split(wrapper, 1)[-1].rsplit("```", 1)[0]

    raw_text = raw_text.strip()

    # 1. Пробуем напрямую распарсить как JSON-массив сегментов
    try:
        items = json.loads(raw_text)
        if isinstance(items, list):
            return _normalize_segments(items)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # 2. Пробуем распарсить как конкатенированные JSON-объекты oMLX
    json_objects = _split_concatenated_json(raw_text)
    if json_objects:
        all_segments: List[Dict[str, Any]] = []
        for obj_str in json_objects:
            try:
                obj = json.loads(obj_str)
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

            if not isinstance(obj, dict):
                continue

            # Извлекаем поле "text" — содержит JSON-массив сегментов
            text_field = obj.get("text", "")
            if not text_field:
                continue

            text_field = str(text_field)

            # Сначала пробуем стандартный парсинг
            try:
                items = json.loads(text_field)
                if isinstance(items, list):
                    norm = _normalize_segments(items)
                    if norm:
                        all_segments.extend(norm)
                    continue
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

            # Если стандартный парсинг не удался (обрезанный текст),
            # используем regex-извлечение сегментов
            segments = _extract_segments_from_truncated_text(text_field)
            if segments:
                all_segments.extend(segments)

        if all_segments:
            return all_segments

    return None


def _normalize_segments(items: List[Any]) -> Optional[List[Dict[str, Any]]]:
    """Нормализовать список сырых сегментов в единый формат."""
    segments: List[Dict[str, Any]] = []
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


def _parse_segments_from_raw_text(raw_text: str) -> List[Dict[str, Any]]:
    """Fallback парсер для формата [MM:SS] Speaker N: text."""
    segments: List[Dict[str, Any]] = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SPEAKER_PATTERN.match(line)
        if m:
            minutes, seconds, speaker, text = m.groups()
            start = int(minutes) * 60 + float(seconds)
            segments.append({
                "start": start,
                "end": start,  # без end из текстового формата
                "speaker": int(speaker),
                "text": text.strip(),
            })
    return segments


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
        segments_files = _split_audio_by_silence(file_path)
        all_segments: List[Dict[str, Any]] = []
        full_text_parts: List[str] = []
        raw_responses: List[str] = []

        for seg_start_samples, _, seg_path in segments_files:
            try:
                seg_result = self._transcribe_segment(seg_path, language)
            except Exception as e:
                logger.error(f"Segment transcription failed: {e}")
                continue

            # Корректировка временных меток по сдвигу сегмента
            if seg_start_samples > 0:
                offset_sec = seg_start_samples / 16000.0
                for seg in seg_result["segments"]:
                    seg["start"] += offset_sec
                    seg["end"] += offset_sec

            all_segments.extend(seg_result["segments"])
            full_text_parts.append(seg_result.get("text", ""))

            raw_resp = seg_result.get("raw_response")
            if raw_resp:
                raw_responses.append(raw_resp)

        duration = time.time() - start_time

        return {
            "segments": all_segments,
            "text": "\n".join(full_text_parts).strip(),
            "speaker_detected": bool(
                all_segments and any(s.get("speaker", 0) != 0 for s in all_segments)
            ),
            "transcription_duration": round(duration, 2),
            "raw_response": "\n".join(raw_responses) if raw_responses else None,
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
                url, files=files, data=data, headers=headers, timeout=(10, 300)
            )
            response.raise_for_status()

        raw_text = response.text
        segments = _parse_segments_from_json(raw_text)

        if segments is None:
            segments = _parse_segments_from_raw_text(raw_text)

        # Формируем чистый текст с метками спикеров
        speaker_labels = {0: "Клиент", 1: "Терапевт"}
        text_lines = []
        for seg in segments:
            spk = seg.get("speaker", 0)
            label = speaker_labels.get(spk, f"Speaker {spk}")
            text_lines.append(f"{label}: {seg['text']}")

        return {
            "segments": segments,
            "text": "\n".join(text_lines) if text_lines else raw_text,
            "raw_response": raw_text,
        }

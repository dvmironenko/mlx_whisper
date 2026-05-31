# oMLX Engine Simplification Design

**Date:** 2026-05-27
**Status:** approved
**Goal:** Упростить OMLXEngine — убрать лишние зависимости и операции, сохранив функциональность.

## Проблема

Текущий OMLXEngine выполняет избыточные операции:
1. Аудиофайл загружается дважды: `librosa.load()` + `AudioSegment.from_file()`
2. Каждый сегмент записывается на диск как `.opus` файл, затем читается обратно для отправки в API
3. Зависимость `librosa` + `numpy` только для детекта тишины

## Решение

Заменить librosa-пайплайн на чистый pydub, убрать temp-файлы сегментов.

## Изменения

### Убираем
- `_group_intervals` — функция группировки интервалов (логика встраивается)
- `_save_segment` — запись сегментов на диск
- Импорт `librosa`, `tempfile`

### Модифицируем
- `_split_audio_by_silence` — один `AudioSegment.from_file()`, детект тишины на raw samples
- `_transcribe_segment` — принимает `bytes` вместо `file_path`

### Добавляем
- `_detect_silence_chunks` — детект тишины на pydub raw samples

### Без изменений
- `_normalize_segments`, `_repair_truncated_json`, `_reconcile_speaker_ids` — обработка ответов API
- `OMLXEngine.transcribe` — оркестрация (минимальные правки)

## Детали: `_detect_silence_chunks`

```
Параметры: audio_segment (AudioSegment), chunk_duration_ms, silence_threshold_db, gap_ms
Возврат: list of (start_ms, end_ms) — не-тихие интервалы

Алгоритм:
1. raw_bytes = audio_segment.raw_data
2. sample_width = audio_segment.sample_width
3. sample_rate = audio_segment.frame_rate
4. num_samples = len(raw_bytes) // (sample_width * channels)
5. samples = struct.unpack(fmt, raw_bytes) — взять первый канал при стерео
6. Iterate over chunks:
   a. Calculate RMS = sqrt(mean(sample^2 for sample in chunk))
   b. Convert RMS to dB: db = 20 * log10(rms / max_possible)
   c. If db > -silence_threshold → non-silent chunk
7. Merge adjacent non-silent chunks separated by < gap_ms
```

## Verification

1. Запустить сервер: `source .venv/bin/activate && python src/main.py`
2. Отправить аудиофайл на `POST /api/v1/transcribe` с `mechanism=omlx`
3. Проверить:
   - Job завершается успешно (`status: completed`)
   - Результат содержит сегменты с корректными временными метками
   - В логах нет ошибок `librosa`/`numpy`
4. Проверить длинный файл (> 5 мин) — корректно разбивается на сегменты
5. Unit-тест: `_detect_silence_chunks` — тестовые аудио с тишиной и речью

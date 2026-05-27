# oMLX Segment Format: MP3 → OPUS

## Context

При транскрибации через oMLX механизм сегменты сохраняются во временные MP3-файлы. OPUS при том же качестве занимает ~2-3 раза меньше места и является нативным форматом oMLX API.

## Design

### Изменения в `src/services/omlx_engine.py`

**`_save_segment()` (строка 137-150):**
- `suffix=".mp3"` → `suffix=".opus"`
- `format="mp3"` → `format="opus"`
- `bitrate="64k"` → `bitrate="48k"` (OPUS 48k ≈ MP3 64k по качеству речи)
- Docstring: "MP3" → "OPUS"

**`_transcribe_segment()` (строка 342-343):**
- MIME mapping: добавить `".opus": "audio/opus"`

### Зависимости

- pydub + FFmpeg (уже установлены в проекте)
- pydub поддерживает OPUS через FFmpeg

### Success Criteria

- Временные сегменты сохраняются как `.opus`
- oMLX API корректно принимает OPUS-файлы
- Размер сегментов уменьшается без потери качества транскрибации

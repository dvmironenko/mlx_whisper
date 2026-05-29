# Устранение дублирования кода Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать дублирование кода через вынос общих функций в утилиты `src/utils/`.

**Architecture:** Вынести 4 области дублирования в отдельные модули: `params.py`, `models.py`, расширить `files.py`, перенести `url_to_filename` в `download.py`. Router.py упрощается до thin-слоя.

**Tech Stack:** Python, FastAPI, pytest

---

### Task 1: Создать `src/utils/params.py` с `resolve_transcription_params()`

**Files:**
- Create: `src/utils/params.py`

- [ ] **Step 1: Написать функцию resolve_transcription_params**

```python
# src/utils/params.py
"""Утилиты для разрешения параметров транскрипции."""

from typing import Optional

from src.config import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    DEFAULT_WORD_TIMESTAMPS,
    DEFAULT_CONDITION_ON_PREVIOUS,
    NO_SPEECH_THRESHOLD,
    HALLUCINATION_SILENCE_THRESHOLD,
    REMOVE_SILENCE,
    SILENCE_THRESHOLD,
    SILENCE_DURATION,
    OMLX_MODEL,
    OMLX_MODELS,
)


def resolve_transcription_params(
    mechanism: str,
    model: str,
    language: Optional[str],
    task: str,
    word_timestamps: str,
    condition_on_previous_text: str,
    remove_silence: Optional[str],
    silence_threshold: Optional[str],
    silence_duration: Optional[str],
    no_speech_threshold: Optional[str],
    hallucination_silence_threshold: Optional[str],
    initial_prompt: Optional[str],
    include_timestamps: Optional[str],
) -> dict:
    """Resolve form parameters to resolved values with env defaults.

    Returns a dict with all resolved parameter values ready to pass
    to the transcription queue.
    """
    # Model resolution
    if mechanism == "omlx":
        model_value = OMLX_MODEL
        if model in OMLX_MODELS:
            model_value = model
    else:
        model_value = model

    # Task resolution — use env default
    task_value = task or "transcribe"

    # Word timestamps — form "false" means use env default
    if word_timestamps == "false":
        word_timestamps_value = DEFAULT_WORD_TIMESTAMPS.lower() == "true"
    else:
        word_timestamps_value = word_timestamps.lower() == "true"

    # Condition on previous — form "true" means use env default
    if condition_on_previous_text == "true":
        condition_on_previous_text_value = DEFAULT_CONDITION_ON_PREVIOUS.lower() == "true"
    else:
        condition_on_previous_text_value = condition_on_previous_text.lower() == "true"

    # Silence removal
    remove_silence_value = REMOVE_SILENCE if remove_silence is None else remove_silence.lower() == "true"

    # Silence thresholds
    silence_threshold_value = SILENCE_THRESHOLD if silence_threshold is None else float(silence_threshold)
    silence_duration_value = SILENCE_DURATION if silence_duration is None else float(silence_duration)

    # Transcription thresholds
    no_speech_threshold_value = NO_SPEECH_THRESHOLD if no_speech_threshold is None else float(no_speech_threshold)
    hallucination_silence_threshold_value = HALLUCINATION_SILENCE_THRESHOLD if hallucination_silence_threshold is None else float(hallucination_silence_threshold)

    # Include timestamps
    include_timestamps_value = include_timestamps is not None and include_timestamps.lower() == "true"

    return {
        "model": model_value,
        "language": language,
        "task": task_value,
        "word_timestamps": word_timestamps_value,
        "condition_on_previous_text": condition_on_previous_text_value,
        "no_speech_threshold": no_speech_threshold_value,
        "hallucination_silence_threshold": hallucination_silence_threshold_value,
        "initial_prompt": initial_prompt,
        "mechanism": mechanism,
        "include_timestamps": include_timestamps_value,
        "remove_silence": remove_silence_value,
        "silence_threshold": silence_threshold_value,
        "silence_duration": silence_duration_value,
    }
```

- [ ] **Step 2: Закоммитить**

```bash
git add src/utils/params.py
git commit -m "feat: add resolve_transcription_params utility"
```

### Task 2: Создать тесты для `src/utils/params.py`

**Files:**
- Create: `tests/test_utils_params.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/test_utils_params.py
"""Тесты для resolve_transcription_params."""

import os
import pytest


def test_resolve_default_mechanism_omlx(monkeypatch):
    """Механизм omlx по умолчанию — модель из OMLX_MODELS."""
    from src.utils.params import resolve_transcription_params

    monkeypatch.setenv("OMLX_MODEL", "VibeVoice-ASR-8bit")
    monkeypatch.setenv("OMLX_MODELS", "VibeVoice-ASR-8bit:VibeVoice ASR 8-bit|custom-model:Custom")

    result = resolve_transcription_params(
        mechanism="omlx", model="tiny", language=None, task="transcribe",
        word_timestamps="true", condition_on_previous_text="false",
        remove_silence=None, silence_threshold=None, silence_duration=None,
        no_speech_threshold=None, hallucination_silence_threshold=None,
        initial_prompt=None, include_timestamps=None,
    )
    assert result["model"] == "VibeVoice-ASR-8bit"
    assert result["mechanism"] == "omlx"


def test_resolve_whisper_mechanism(monkeypatch):
    """Механизм whisper — используется переданная модель."""
    from src.utils.params import resolve_transcription_params

    monkeypatch.setenv("OMLX_MODEL", "VibeVoice-ASR-8bit")
    monkeypatch.setenv("OMLX_MODELS", "")

    result = resolve_transcription_params(
        mechanism="whisper", model="turbo", language=None, task="transcribe",
        word_timestamps="true", condition_on_previous_text="false",
        remove_silence=None, silence_threshold=None, silence_duration=None,
        no_speech_threshold=None, hallucination_silence_threshold=None,
        initial_prompt=None, include_timestamps=None,
    )
    assert result["model"] == "turbo"


def test_resolve_word_timestamps_form_true():
    """word_timestamps=true → True."""
    from src.utils.params import resolve_transcription_params

    result = resolve_transcription_params(
        mechanism="omlx", model="test", language=None, task="transcribe",
        word_timestamps="true", condition_on_previous_text="false",
        remove_silence=None, silence_threshold=None, silence_duration=None,
        no_speech_threshold=None, hallucination_silence_threshold=None,
        initial_prompt=None, include_timestamps=None,
    )
    assert result["word_timestamps"] is True


def test_resolve_word_timestamps_form_false_uses_default():
    """word_timestamps=false → значение из env."""
    from src.utils.params import resolve_transcription_params

    result = resolve_transcription_params(
        mechanism="omlx", model="test", language=None, task="transcribe",
        word_timestamps="false", condition_on_previous_text="false",
        remove_silence=None, silence_threshold=None, silence_duration=None,
        no_speech_threshold=None, hallucination_silence_threshold=None,
        initial_prompt=None, include_timestamps=None,
    )
    # По умолчанию DEFAULT_WORD_TIMESTAMPS=false в тестовой среде
    assert result["word_timestamps"] is False


def test_resolve_silence_threshold_form_override():
    """silence_threshold из формы переопределяет env."""
    from src.utils.params import resolve_transcription_params

    result = resolve_transcription_params(
        mechanism="omlx", model="test", language=None, task="transcribe",
        word_timestamps="true", condition_on_previous_text="false",
        remove_silence=None, silence_threshold="-30.0", silence_duration=None,
        no_speech_threshold=None, hallucination_silence_threshold=None,
        initial_prompt=None, include_timestamps=None,
    )
    assert result["silence_threshold"] == -30.0


def test_resolve_include_timestamps():
    """include_timestamps парсится корректно."""
    from src.utils.params import resolve_transcription_params

    result = resolve_transcription_params(
        mechanism="omlx", model="test", language=None, task="transcribe",
        word_timestamps="true", condition_on_previous_text="false",
        remove_silence=None, silence_threshold=None, silence_duration=None,
        no_speech_threshold=None, hallucination_silence_threshold=None,
        initial_prompt=None, include_timestamps="true",
    )
    assert result["include_timestamps"] is True

    result_none = resolve_transcription_params(
        mechanism="omlx", model="test", language=None, task="transcribe",
        word_timestamps="true", condition_on_previous_text="false",
        remove_silence=None, silence_threshold=None, silence_duration=None,
        no_speech_threshold=None, hallucination_silence_threshold=None,
        initial_prompt=None, include_timestamps=None,
    )
    assert result_none["include_timestamps"] is False
```

- [ ] **Step 2: Запустить тесты**

```bash
python -m pytest tests/test_utils_params.py -v
```

Ожидаемый результат: все тесты PASS

- [ ] **Step 3: Закоммитить**

```bash
git add tests/test_utils_params.py
git commit -m "test: add tests for resolve_transcription_params"
```

### Task 3: Создать `src/utils/models.py` с `get_model_path()`

**Files:**
- Create: `src/utils/models.py`

- [ ] **Step 1: Написать утилиту**

```python
# src/utils/models.py
"""Утилиты для работы с MLX Whisper моделями."""

import os

MODEL_NAMES = ("tiny", "base", "small", "medium", "turbo", "large")


def get_model_path(model: str, models_dir: str = "models") -> str:
    """Get model path — local if exists, else HF fallback.

    Parameters
    ----------
    model : str
        Model alias (e.g. 'turbo', 'large')
    models_dir : str
        Directory containing local MLX model folders

    Returns
    -------
    str
        Local path if exists, else HuggingFace repo ID
    """
    local = os.path.join(models_dir, f"whisper-{model}")
    if os.path.exists(local):
        return local
    return f"mlx-community/whisper-{model}"
```

- [ ] **Step 2: Закоммитить**

```bash
git add src/utils/models.py
git commit -m "feat: add get_model_path utility"
```

### Task 4: Создать тесты для `src/utils/models.py`

**Files:**
- Create: `tests/test_utils_models.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/test_utils_models.py
"""Тесты для get_model_path."""

import os
import pytest


def test_get_model_path_hf_fallback(tmp_path, monkeypatch):
    """Модель не существует локально — HF fallback."""
    from src.utils.models import get_model_path

    monkeypatch.setattr(os.path, "exists", lambda p: False)
    result = get_model_path("turbo", str(tmp_path))
    assert result == "mlx-community/whisper-turbo"


def test_get_model_path_local_exists(tmp_path, monkeypatch):
    """Модель существует локально — локальный путь."""
    from src.utils.models import get_model_path

    local_dir = tmp_path / "whisper-turbo"
    local_dir.mkdir()
    monkeypatch.setattr(os.path, "exists", lambda p: str(p) == str(local_dir))

    result = get_model_path("turbo", str(tmp_path))
    assert result == str(local_dir)


def test_get_model_path_unknown_model(tmp_path, monkeypatch):
    """Неизвестная модель — HF fallback."""
    from src.utils.models import get_model_path

    monkeypatch.setattr(os.path, "exists", lambda p: False)
    result = get_model_path("nonexistent", str(tmp_path))
    assert result == "mlx-community/whisper-nonexistent"
```

- [ ] **Step 2: Запустить тесты**

```bash
python -m pytest tests/test_utils_models.py -v
```

Ожидаемый результат: все тесты PASS

- [ ] **Step 3: Закоммитить**

```bash
git add tests/test_utils_models.py
git commit -m "test: add tests for get_model_path"
```

### Task 5: Расширить `src/utils/files.py` с `find_file_in_jobs()`

**Files:**
- Modify: `src/utils/files.py`

- [ ] **Step 1: Добавить функцию find_file_in_jobs**

В конец файла `src/utils/files.py` добавить:

```python
def find_file_in_jobs(filename: str, data_uploads_dir: str) -> Optional[tuple[str, str]]:
    """Find file in DATA_UPLOADS_DIR root or any job_id subdirectory.

    Parameters
    ----------
    filename : str
        Name of the file to find
    data_uploads_dir : str
        Root data directory

    Returns
    -------
    Optional[tuple[str, str]]
        (resolved_path, base_path) if found, None otherwise.
        base_path is used for path traversal validation.
    """
    # Check root first
    root_path = os.path.join(data_uploads_dir, filename)
    if os.path.exists(root_path):
        resolved = os.path.realpath(root_path)
        base = os.path.realpath(data_uploads_dir)
        return (resolved, base)

    # Search in job_id subdirectories
    try:
        for entry in os.listdir(data_uploads_dir):
            job_dir = os.path.join(data_uploads_dir, entry)
            if not os.path.isdir(job_dir):
                continue
            potential_path = os.path.join(job_dir, filename)
            if os.path.exists(potential_path):
                resolved = os.path.realpath(potential_path)
                base = os.path.realpath(data_uploads_dir)
                return (resolved, base)
    except OSError:
        pass

    return None
```

- [ ] **Step 2: Закоммитить**

```bash
git add src/utils/files.py
git commit -m "feat: add find_file_in_jobs utility"
```

### Task 6: Создать тесты для `find_file_in_jobs()`

**Files:**
- Create: `tests/test_utils_files.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/test_utils_files.py
"""Тесты для find_file_in_jobs."""

import os
import pytest


def test_find_file_in_jobs_root(tmp_path):
    """Файл найден в корневой директории."""
    from src.utils.files import find_file_in_jobs

    # Создаём файл в root
    root_dir = tmp_path / "data"
    root_dir.mkdir()
    test_file = root_dir / "test.txt"
    test_file.write_text("content")

    result = find_file_in_jobs("test.txt", str(root_dir))
    assert result is not None
    resolved, base = result
    assert os.path.basename(resolved) == "test.txt"


def test_find_file_in_jobs_job_dir(tmp_path):
    """Файл найден в поддиректории job_id."""
    from src.utils.files import find_file_in_jobs

    root_dir = tmp_path / "data"
    root_dir.mkdir()
    job_dir = root_dir / "abc-123"
    job_dir.mkdir()
    test_file = job_dir / "segments.txt"
    test_file.write_text("segments")

    result = find_file_in_jobs("segments.txt", str(root_dir))
    assert result is not None
    resolved, base = result
    assert "abc-123" in resolved


def test_find_file_in_jobs_not_found(tmp_path):
    """Файл не найден — возвращает None."""
    from src.utils.files import find_file_in_jobs

    root_dir = tmp_path / "data"
    root_dir.mkdir()

    result = find_file_in_jobs("nonexistent.txt", str(root_dir))
    assert result is None


def test_find_file_in_jobs_path_traversal(tmp_path):
    """Попытка path traversal — отклоняется вызывающим кодом."""
    from src.utils.files import find_file_in_jobs

    root_dir = tmp_path / "data"
    root_dir.mkdir()

    # Функция сама по себе не разрешает path traversal,
    # но возвращает real_path — вызывающий код проверяет startswith(base)
    result = find_file_in_jobs("../../etc/passwd", str(root_dir))
    # Вернёт None, т.к. файл не существует,
    # но если бы существовал — real_path был бы абсолютным
    assert result is None or not any(part == ".." for part in result[0].split(os.sep))
```

- [ ] **Step 2: Запустить тесты**

```bash
python -m pytest tests/test_utils_files.py -v
```

Ожидаемый результат: все тесты PASS

- [ ] **Step 3: Закоммитить**

```bash
git add tests/test_utils_files.py
git commit -m "test: add tests for find_file_in_jobs"
```

### Task 7: Перенести `url_to_filename` в `src/utils/download.py`

**Files:**
- Modify: `src/utils/download.py`
- Modify: `router.py:14-31`

- [ ] **Step 1: Добавить url_to_filename в download.py**

В конец `src/utils/download.py` добавить:

```python
def url_to_filename(url: str) -> str:
    """Извлечь осмысленное имя файла из URL.

    YouTube/Vimeo — по видео ID, остальные — basename пути.
    """
    # YouTube: watch?v=ID, youtu.be/ID, embed/ID
    m = re.search(r'(?:v=|/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    if m:
        return f"youtube_{m.group(1)}"

    # Vimeo: vimeo.com/ID или vimeo.com/channels/.../ID
    m = re.search(r'vimeo\.com/(?:channels(?:/[^/]+)*/|groups/(?:(?!/video/).)*/)?(\d+)', url)
    if m:
        return f"vimeo_{m.group(1)}"

    return os.path.basename(url) or "download"
```

- [ ] **Step 2: Удалить _url_to_filename из router.py**

Удалить строки `router.py:14-31` (функцию `_url_to_filename`).

- [ ] **Step 3: Обновить импорт в router.py**

В `router.py` добавить `url_to_filename` в импорты из `src.utils.download`:

```python
from src.utils.download import download_from_url, validate_url, url_to_filename
```

- [ ] **Step 4: Закоммитить**

```bash
git add src/utils/download.py src/api/router.py
git commit -m "refactor: move url_to_filename from router to download utils"
```

### Task 8: Обновить `router.py` — удалить дублирование resolve-кода

**Files:**
- Modify: `src/api/router.py`

- [ ] **Step 1: Упростить transcribe_audio_endpoint**

Заменить блок resolve-кода в `transcribe_audio_endpoint` (строки ~169-188) на один вызов:

```python
    # Resolve parameters
    resolved = resolve_transcription_params(
        mechanism=mechanism,
        model=model,
        language=language,
        task=task,
        word_timestamps=word_timestamps,
        condition_on_previous_text=condition_on_previous_text,
        remove_silence=remove_silence,
        silence_threshold=silence_threshold,
        silence_duration=silence_duration,
        no_speech_threshold=no_speech_threshold,
        hallucination_silence_threshold=hallucination_silence_threshold,
        initial_prompt=initial_prompt,
        include_timestamps=include_timestamps,
    )
```

Использовать `resolved["model"]`, `resolved["word_timestamps"]` и т.д. вместо локальных переменных `model_value`, `word_timestamps_value` и т.д.

- [ ] **Step 2: Упростить transcribe_url_endpoint**

Заменить блок resolve-кода в `transcribe_url_endpoint` (строки ~338-359) на аналогичный вызов `resolve_transcription_params()`.

- [ ] **Step 3: Добавить импорт**

В начало `router.py` добавить:

```python
from src.utils.params import resolve_transcription_params
```

- [ ] **Step 4: Закоммитить**

```bash
git add src/api/router.py
git commit -m "refactor: use resolve_transcription_params in both endpoints"
```

### Task 9: Упростить download_file и get_file_content

**Files:**
- Modify: `src/api/router.py`

- [ ] **Step 1: Заменить download_file**

Заменить тело `download_file` (строки ~550-581) на:

```python
@router.get("/files/{filename}/download")
async def download_file(filename: str):
    """Скачивание файла из data/uploads/."""
    from src.utils.files import find_file_in_jobs

    result = find_file_in_jobs(filename, DATA_UPLOADS_DIR)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

    resolved, base = result
    if not resolved.startswith(base):
        raise HTTPException(status_code=400, detail="Invalid path")

    return FileResponse(resolved, filename=filename)
```

- [ ] **Step 2: Заменить get_file_content**

Заменить тело `get_file_content` (строки ~584-623) на:

```python
@router.get("/files/{filename}/content")
async def get_file_content(filename: str):
    """Получить содержимое текстового файла для просмотра."""
    from src.utils.files import find_file_in_jobs

    result = find_file_in_jobs(filename, DATA_UPLOADS_DIR)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

    resolved, base = result
    if not resolved.startswith(base):
        raise HTTPException(status_code=400, detail="Invalid path")

    ext = os.path.splitext(filename)[1].lower()
    media_type = "application/json" if ext == ".json" else "text/plain; charset=utf-8"

    with open(resolved, "r", encoding="utf-8") as f:
        content = f.read()

    return PlainTextResponse(content=content, media_type=media_type)
```

- [ ] **Step 3: Удалить debug print-статements**

Удалить строки `router.py:557-558` (print(f"DEBUG: ...")).

- [ ] **Step 4: Закоммитить**

```bash
git add src/api/router.py
git commit -m "refactor: use find_file_in_jobs in download and content endpoints"
```

### Task 10: Упростить preload_model endpoint

**Files:**
- Modify: `src/api/router.py`

- [ ] **Step 1: Заменить model_mapping на get_model_path**

В `preload_model` (строки ~765-791) заменить:

```python
        models_dir = os.getenv("MODELS_DIR", "models")
        model_mapping = {
            "tiny": os.path.join(models_dir, "whisper-tiny"),
            "base": os.path.join(models_dir, "whisper-base"),
            "small": os.path.join(models_dir, "whisper-small"),
            "medium": os.path.join(models_dir, "whisper-medium"),
            "turbo": os.path.join(models_dir, "whisper-turbo"),
            "large": os.path.join(models_dir, "whisper-large"),
        }
        model_path = model_mapping.get(model, os.path.join(models_dir, "whisper-large"))

        if not os.path.exists(model_path):
            model_path = f"mlx-community/whisper-{model}"
```

на:

```python
        from src.utils.models import get_model_path

        models_dir = os.getenv("MODELS_DIR", "models")
        model_path = get_model_path(model, models_dir)
```

- [ ] **Step 2: Закоммитить**

```bash
git add src/api/router.py
git commit -m "refactor: use get_model_path in preload endpoint"
```

### Task 11: Запустить все тесты

- [ ] **Step 1: Запустить существующие тесты**

```bash
python -m pytest tests/ -v --tb=short
```

Ожидаемый результат: все тесты PASS

- [ ] **Step 2: Закоммитить если всё прошло успешно**

```bash
git add -A
git commit -m "chore: verify all tests pass after deduplication refactor"
```

### Task 12: Проверить размер router.py

- [ ] **Step 1: Проверить экономию строк**

```bash
git diff 15f04ec...HEAD --stat src/api/router.py
```

Ожидаемый результат: router.py сократился минимум на ~100 строк.

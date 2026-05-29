# Дизайн-спецификация: Устранение дублирования кода

## Контекст

В проекте MLX-Transcriber накопилось дублирование кода в `router.py` (792 строки) и между файлами. Это усложняет поддержку и увеличивает риск рассинхронизации изменений. Цель — убрать дублирование через вынос общих функций в утилиты, сохранив обратную совместимость API.

## Подход: Утилиты (минимальный риск)

Вынести общие функции в отдельные модули `src/utils/`. Router.py упрощается до thin-слоя: валидация → вызов утилиты → возврат ответа.

## Области дублирования

### 1. Resolve параметров транскрипции

**Где:** `router.py:169-188` (transcribe_audio_endpoint) и `router.py:338-359` (transcribe_url_endpoint)

**Что дублируется:** 20+ строк resolve-логики для каждого эндпоинта:
- model_value (OMLX vs Whisper)
- word_timestamps_value (default + form override)
- condition_on_previous_text_value
- remove_silence_value, silence_threshold_value, silence_duration_value
- no_speech_threshold_value, hallucination_silence_threshold_value

**Решение:** Создать `src/utils/params.py` с функцией `resolve_transcription_params(**kwargs) -> dict`.

```python
# src/utils/params.py
def resolve_transcription_params(
    mechanism: str,
    model: str,
    word_timestamps: str,
    condition_on_previous_text: str,
    remove_silence: Optional[str],
    silence_threshold: Optional[str],
    silence_duration: Optional[str],
    no_speech_threshold: Optional[str],
    hallucination_silence_threshold: Optional[str],
    include_timestamps: Optional[str],
) -> dict:
    """Resolve form parameters to resolved values with env defaults."""
    ...
```

### 2. Model mapping

**Где:** `main.py:28-35`, `router.py:771-778`, `config.py:147-154`

**Что дублируется:** `model_mapping` dict — маппинг alias → path для Whisper-моделей.

**Решение:** Создать `src/utils/models.py` с `get_model_path(model: str, models_dir: str = "models") -> str`.

```python
# src/utils/models.py
MODEL_NAMES = ("tiny", "base", "small", "medium", "turbo", "large")

def get_model_path(model: str, models_dir: str = "models") -> str:
    """Get model path — local if exists, else HF fallback."""
    local = os.path.join(models_dir, f"whisper-{model}")
    if os.path.exists(local):
        return local
    return f"mlx-community/whisper-{model}"
```

### 3. File search logic

**Где:** `router.py:565-576` (download_file) и `router.py:596-608` (get_file_content)

**Что дублируется:** Итерация по job_id директориям для поиска файла.

**Решение:** Расширить `src/utils/files.py` функцией `find_file_in_jobs(filename: str, data_uploads_dir: str) -> tuple[str, str] | None`.

```python
# src/utils/files.py
def find_file_in_jobs(filename: str, data_uploads_dir: str) -> Optional[tuple[str, str]]:
    """Find file in DATA_UPLOADS_DIR root or any job_id subdirectory.
    
    Returns (resolved_path, base_path) or None.
    """
    ...
```

### 4. _url_to_filename

**Где:** `router.py:14-31`

**Решение:** Перенести в `src/utils/download.py`.

## Новая структура файлов

```
src/utils/
├── __init__.py
├── audio.py          # существующий
├── files.py          # существующий + find_file_in_jobs()
├── download.py       # существующий + url_to_filename()
├── params.py         # новый — resolve_transcription_params()
└── models.py         # новый — get_model_path(), MODEL_NAMES
```

## Изменения в router.py

| Что | Где | Строк |
|-----|-----|-------|
| Удалить resolve-код (2 места) | :169-188, :338-359 | ~80 |
| Удалить model_mapping | :771-778 | ~20 |
| Удалить _url_to_filename | :14-31 | ~18 |
| Упростить download_file | :550-581 | ~15 |
| Упростить get_file_content | :584-623 | ~15 |
| **Итого удалено** | | **~148** |
| Добавить импорты утилит | top | ~10 |
| **Чистая экономия** | | **~138 строк** |

## Тесты

### tests/test_utils_params.py
- `test_resolve_default_mechanism_omlx` — mechanism=omlx, model из OMLX_MODELS
- `test_resolve_default_mechanism_whisper` — mechanism=whisper
- `test_resolve_word_timestamps_form_true` — word_timestamps=true
- `test_resolve_word_timestamps_form_false_uses_env` — word_timestamps=false, DEFAULT_WORD_TIMESTAMPS=true
- `test_resolve_silence_threshold_form_override` — form value overrides env
- `test_resolve_include_timestamps` — include_timestamps parsing

### tests/test_utils_models.py
- `test_get_model_path_local_exists` — local path returned
- `test_get_model_path_hf_fallback` — HF path when local missing
- `test_get_model_path_unknown_model` — HF fallback for unknown

### tests/test_utils_files.py
- `test_find_file_in_jobs_root` — file in DATA_UPLOADS_DIR root
- `test_find_file_in_jobs_job_dir` — file in job_id subdirectory
- `test_find_file_in_jobs_not_found` — returns None
- `test_find_file_in_jobs_path_traversal` — rejects ../../etc/passwd

## Порядок реализации

1. Создать `src/utils/params.py` + тесты
2. Создать `src/utils/models.py` + тесты
3. Расширить `src/utils/files.py` + тесты
4. Перенести `url_to_filename` в `src/utils/download.py` + тесты
5. Обновить `router.py` — удалить дублирование, использовать утилиты
6. Запустить существующие тесты

## Критерии успеха

- Все существующие тесты проходят
- Router.py сокращается на ~138 строк
- Нет дублированных resolve-блоков
- Новая функциональность покрыта тестами

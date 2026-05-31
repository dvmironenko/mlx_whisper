# Settings Refresh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить кнопку «Обновить параметры» на страницу настроек, которая перечитывает `.env`, сбрасывает кэш report_types и обновляет UI без перезагрузки.

**Architecture:** Новый POST-эндпоинт `/api/v1/settings/refresh` на бэкенде перечитывает `.env` через `dotenv.load_dotenv(override=True)`, сбрасывает кэш `report_types.py`, возвращает свежие config + settings. Фронтенд обновляет поля формы в-place и показывает тост.

**Tech Stack:** FastAPI, python-dotenv, vanilla JS

---

## Файлы для изменения

| Файл | Действие | Ответственность |
|------|----------|-----------------|
| `src/config.py` | Modify | Добавить `reload_dotenv()` |
| `src/services/report_types.py` | Modify | Добавить `clear_cache()` |
| `src/api/router.py` | Modify | Добавить `POST /api/v1/settings/refresh` |
| `src/templates/settings.html` | Modify | Добавить кнопку, `showToast`, JS-логику |

---

### Task 1: Добавить `reload_dotenv()` в `src/config.py`

**Файлы:**
- Modify: `src/config.py:1-163`

- [ ] **Шаг 1: Добавить функцию `reload_dotenv()`**

Добавить после строки 8 (после `load_dotenv(env_path)`):

```python
def reload_dotenv() -> None:
    """Перечитать .env файл и обновить переменные окружения."""
    load_dotenv(env_path, override=True)
```

Флаг `override=True` гарантирует перезапись существующих переменных.

- [ ] **Шаг 2: Проверить синтаксис**

```bash
python -c "from src.config import reload_dotenv; print('OK')"
```

Ожидаемый результат: `OK`

- [ ] **Шаг 3: Закоммитить**

```bash
git add src/config.py
git commit -m "feat: add reload_dotenv() to re-read .env file"
```

---

### Task 2: Добавить `clear_cache()` в `src/services/report_types.py`

**Файлы:**
- Modify: `src/services/report_types.py:1-140`

- [ ] **Шаг 1: Добавить метод `clear_cache()`**

Добавить после строки 76 (после `load_report_types()`), перед `save_report_prompt()`:

```python
def clear_cache() -> None:
    """Сбросить модульный кэш — следующий вызов load_report_types() перечитает файл."""
    global _report_types_cache
    _report_types_cache = None
```

- [ ] **Шаг 2: Проверить синтаксис**

```bash
python -c "from src.services.report_types import clear_cache; print('OK')"
```

Ожидаемый результат: `OK`

- [ ] **Шаг 3: Закоммитить**

```bash
git add src/services/report_types.py
git commit -m "feat: add clear_cache() to reset report types module cache"
```

---

### Task 3: Добавить эндпоинт `POST /api/v1/settings/refresh` в `src/api/router.py`

**Файлы:**
- Modify: `src/api/router.py`
  - Импорт: добавить `reload_dotenv` из `src.config`
  - Импорт: добавить `clear_cache` из `src.services.report_types`
  - Новый эндпоинт: после строки 649 (после `save_settings`)

- [ ] **Шаг 1: Обновить импорты**

В блоке импорта `src.config` (строки 22-29) добавить `reload_dotenv`:

```python
from src.config import (
    AUDIO_EXTENSIONS, SUPPORTED_MODELS, CHUNK_SIZE, DEFAULT_LANGUAGE,
    NO_SPEECH_THRESHOLD, HALLUCINATION_SILENCE_THRESHOLD, REMOVE_SILENCE,
    SILENCE_THRESHOLD, SILENCE_DURATION, UPLOADS_DIR, DATA_UPLOADS_DIR,
    MAX_FILE_SIZE, ALLOWED_URL_DOMAINS, MAX_DOWNLOAD_SIZE, DOWNLOAD_TIMEOUT,
    logger, log_transcription_result, OMLX_ENABLED, OMLX_BASE_URL,
    OMLX_MODEL, DEFAULT_MODEL, reload_dotenv,
)
```

В блоке импорта `src.services.report_types` (строка 32) добавить `clear_cache`:

```python
from src.services.report_types import load_report_types, get_prompt_for_report_type, save_report_prompt, clear_cache
```

- [ ] **Шаг 2: Добавить эндпоинт**

Добавить после строки 649 (после `return {"status": "ok"}` в `save_settings`):

```python
@router.post("/settings/refresh")
async def refresh_settings():
    """
    Перечитать .env, сбросить кэш report_types, вернуть свежие данные.

    Возвращает {success: true, config: {...}, settings: [...]}
    """
    try:
        reload_dotenv()
        clear_cache()

        # Собрать свежие config
        from src.config import (
            INITIAL_PROMPT, REMOVE_SILENCE, SILENCE_THRESHOLD, SILENCE_DURATION,
            DEFAULT_LANGUAGE, NO_SPEECH_THRESHOLD, HALLUCINATION_SILENCE_THRESHOLD,
            OMLX_ENABLED, OMLX_BASE_URL, OMLX_MODEL,
        )
        config = {
            "initial_prompt": INITIAL_PROMPT,
            "remove_silence": REMOVE_SILENCE,
            "silence_threshold": SILENCE_THRESHOLD,
            "silence_duration": SILENCE_DURATION,
            "default_language": DEFAULT_LANGUAGE,
            "no_speech_threshold": NO_SPEECH_THRESHOLD,
            "hallucination_silence_threshold": HALLUCINATION_SILENCE_THRESHOLD,
            "allowed_url_domains": ALLOWED_URL_DOMAINS,
            "max_download_size_mb": MAX_DOWNLOAD_SIZE // (1024 * 1024),
            "download_timeout": DOWNLOAD_TIMEOUT,
            "omlx_enabled": OMLX_ENABLED,
            "omlx_base_url": OMLX_BASE_URL,
            "omlx_model": OMLX_MODEL,
        }

        # Собрать свежие settings
        types = load_report_types()
        settings = [{"id": t["id"], "name": t["name"], "prompt": t.get("prompt", "")} for t in types]

        return {"success": True, "config": config, "settings": settings}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {e}")
```

- [ ] **Шаг 3: Проверить что импорты работают**

```bash
python -c "from src.api.router import router; print('OK')"
```

Ожидаемый результат: `OK`

- [ ] **Шаг 4: Закоммитить**

```bash
git add src/api/router.py
git commit -m "feat: add POST /api/v1/settings/refresh endpoint"
```

---

### Task 4: Добавить кнопку и JS-логику в `src/templates/settings.html`

**Файлы:**
- Modify: `src/templates/settings.html`
  - Кнопка: добавить в `form-buttons` (строка 69-74)
  - `showToast`: добавить в IIFE (строка 107-217)
  - Логика refresh: добавить обработчик и функцию

- [ ] **Шаг 1: Добавить кнопку «Обновить параметры»**

Внутри `<div class="form-buttons">` (строки 69-74), после кнопки Save:

```html
<div class="form-buttons">
    <button id="saveButton" class="submit-button" disabled>
        <i class="fas fa-save"></i>
        <span>Сохранить</span>
    </button>
    <button type="button" id="refreshButton" class="btn-secondary">
        <i class="fas fa-sync-alt"></i>
        <span>Обновить параметры</span>
    </button>
</div>
```

- [ ] **Шаг 2: Добавить `showToast` и логику refresh в JS IIFE**

Внутри IIFE (после строки 113 `const notif = ...`, но до `let originalPrompts`), и после `checkChanged`/`saveBtn` логики:

```javascript
        const refreshBtn = document.getElementById('refreshButton');

        function showToast(msg, type) {
            notif.textContent = msg;
            notif.style.display = 'block';
            notif.style.color = type === 'success' ? 'var(--success-color)' : 'var(--error-color)';
            notif.style.marginTop = '16px';
            notif.style.padding = '8px 12px';
            notif.style.borderRadius = '6px';
            notif.style.border = `1px solid ${type === 'success' ? 'var(--success-color)' : 'var(--error-color)'}`;
            setTimeout(function() { notif.style.display = 'none'; }, 3000);
        }

        refreshBtn.addEventListener('click', async function() {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Обновление...</span>';

            try {
                const resp = await fetch('/api/v1/settings/refresh', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                });
                const data = await resp.json();
                if (!resp.ok) {
                    throw new Error(data.detail || 'Ошибка обновления');
                }

                // Обновить select report types
                select.innerHTML = '';
                data.settings.forEach(function(t) {
                    const opt = document.createElement('option');
                    opt.value = t.id;
                    opt.textContent = t.name;
                    originalPrompts[t.id] = t.prompt || '';
                    originalNames[t.id] = t.name || '';
                    select.appendChild(opt);
                });

                // Обновить config поля (initial_prompt, language и т.д.)
                // Примечание: на текущей странице настроек config-поля не отображаются,
                // но они доступны в data.config для будущих расширений страницы.

                // Сбросить выбранный отчет на первый
                const firstId = data.settings[0]?.id;
                if (firstId) {
                    select.value = firstId;
                    select.dispatchEvent(new Event('change'));
                }

                reportTypesData = {types: data.settings};
                showToast('Параметры обновлены', 'success');
            } catch (e) {
                showToast(e.message, 'error');
            } finally {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> <span>Обновить параметры</span>';
            }
        });
```

- [ ] **Шаг 3: Проверить что HTML валиден**

Открыть `src/templates/settings.html` в браузере и убедиться что:
  - Кнопка «Обновить параметры» отображается рядом с «Сохранить»
  - При нажатии — спиннер появляется, затем тост «Параметры обновлены»

- [ ] **Шаг 4: Закоммитить**

```bash
git add src/templates/settings.html
git commit -m "feat: add refresh button to settings page with toast notification"
```

---

## Верификация

1. **Ручное тестирование:**
   - Изменить значение в `.env` (например, `INITIAL_PROMPT=новый текст`)
   - Открыть `/settings`, нажать «Обновить параметры»
   - Убедиться что тост «Параметры обновлены» появился
   - Изменить промпт в `config/reports.json`
   - Нажать «Обновить параметры» — промпт в UI обновился

2. **Проверка что сервер работает:**
   ```bash
   curl -s -X POST http://localhost:8801/api/v1/settings/refresh | python -m json.tool
   ```
   Ожидаемый результат: JSON с `success: true`, `config: {...}`, `settings: [...]`

3. **Проверка что кэш сбрасывается:**
   - Изменить `config/reports.json` (добавить новый тип)
   - Нажать «Обновить параметры»
   - Новый тип должен появиться в select

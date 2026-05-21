# Страница «Настройки» — Редактирование промптов отчетов

> **Для агентов:** Используйте superpowers:subagent-driven-development для выполнения плана по задачам. Шаги используют checkbox (`- [ ]`) синтаксис для трекинга.

**Цель:** Добавить страницу настроек для просмотра и редактирования промптов отчетов, хранящихся в `config/reports.json`.

**Архитектура:** Отдельная страница `/settings` с двумя API endpoints (`GET /api/v1/settings` — чтение с промптами, `POST /api/v1/settings` — сохранение). Навигация — кнопка "Настройки" в хедере каждой страницы.

**Технологии:** FastAPI, Jinja2, ванильный JS, `config/reports.json` как источник истины.

---

## Файлы для изменения

### Новые файлы
- `src/templates/settings.html` — шаблон страницы настроек

### Измененные файлы
- `src/main.py:79-88` — добавить маршрут `GET /settings`
- `src/api/router.py` — добавить endpoints `GET /api/v1/settings` и `POST /api/v1/settings`
- `src/templates/index.html:12-20` — добавить кнопку "Настройки" в хедер
- `src/templates/uploads.html:12-30` — добавить кнопку "Настройки" в хедер

---

## Task 1: Добавить API GET `/api/v1/settings` — список отчетов с промптами

**Файлы:**
- Modify: `src/api/router.py:597-606`

- [ ] **Шаг 1: Добавить endpoint GET `/api/v1/settings`**

После существующего `GET /report-types` (строки 597-606 в router.py), добавить новый endpoint. Он возвращает то же, что и `/report-types`, но **включает** поле `prompt` для каждого отчета.

```python
@router.get("/settings")
async def get_settings():
    """
    Вернуть список типов отчетов с их промптами.

    Возвращает {types: [{id, name, prompt}, ...]}.
    """
    types = load_report_types()
    result = [{"id": t["id"], "name": t["name"], "prompt": t.get("prompt", "")} for t in types]
    return {"types": result}
```

**Важно:** Этот endpoint идёт ПЕРЕД `POST /settings` (FastAPI обрабатывает маршруты в порядке объявления).

- [ ] **Шаг 2: Проверить синтаксис**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -c "import ast; ast.parse(open('src/api/router.py').read())"
```

---

## Task 2: Добавить API POST `/api/v1/settings` — сохранение промпта

**Файлы:**
- Modify: `src/api/router.py`

- [ ] **Шаг 1: Добавить endpoint POST `/api/v1/settings`**

После `GET /settings`, добавить:

```python
@router.post("/settings")
async def save_settings(body: dict):
    """
    Сохранить изменённый промпт для типа отчета.

    Тело запроса: {"report_type": "summary", "prompt": "новый промпт"}
    Записывает изменения в config/reports.json.
    """
    import json

    report_type = body.get("report_type")
    prompt = body.get("prompt")

    if not report_type or prompt is None:
        raise HTTPException(status_code=400, detail="report_type и prompt обязательны")

    # Найти файл config/reports.json
    path = _find_reports_json()
    if path is None:
        raise HTTPException(status_code=500, detail="config/reports.json не найден")

    # Загрузить текущие данные
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка JSON: {e}")

    # Найти и обновить отчет
    found = False
    for item in data:
        if isinstance(item, dict) and item.get("id") == report_type:
            item["prompt"] = prompt
            found = True
            break

    if not found:
        raise HTTPException(status_code=400, detail=f"Тип отчета '{report_type}' не найден")

    # Записать обратно
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка записи: {e}")

    return {"status": "ok"}
```

- [ ] **Шаг 2: Проверить синтаксис**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && python -c "import ast; ast.parse(open('src/api/router.py').read())"
```

---

## Task 3: Добавить маршрут `GET /settings` в main.py

**Файлы:**
- Modify: `src/main.py:85-88`

- [ ] **Шаг 1: Добавить маршрут после `/uploads`**

После строки 88 (`return templates.TemplateResponse("uploads.html", ...)`), добавить:

```python
@app.get("/settings", include_in_schema=False)
async def settings_page(request: Request):
    """Settings endpoint with settings interface."""
    return templates.TemplateResponse("settings.html", {"request": request})
```

---

## Task 4: Создать шаблон `settings.html`

**Файлы:**
- Create: `src/templates/settings.html`

- [ ] **Шаг 1: Создать шаблон**

Создать `src/templates/settings.html` по аналогии с `index.html` и `uploads.html`:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MLX-Transcriber Настройки</title>
    <link rel="stylesheet" href="/static/new_style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>

    <div class="container">
        <header class="app-header">
            <div class="header-content">
                <h1 class="app-title">
                    <i class="fas fa-microphone-alt"></i> MLX-Transcriber
                </h1>
                <p class="app-subtitle">Настройки отчетов</p>
            </div>
        </header>

        <!-- Theme Switcher -->
        <div class="app-controls">
            <div class="theme-switch-container" id="themeSwitchContainer" aria-label="Переключить тему">
                <label class="theme-switch-label" id="themeLabel" for="themeToggle">Светлая</label>
                <div class="theme-switch-wrapper">
                <input type="checkbox" id="themeToggle" class="theme-toggle">
                    <span class="theme-switch-track">
                        <span class="theme-switch-thumb"></span>
                    </span>
                </div>
            </div>
        </div>

        <main class="app-main">
            <div class="upload-section" id="settingsSection">
                <div class="section-header">
                    <h2><i class="fas fa-cog"></i> Настройки</h2>
                </div>
                <div class="section-description">
                    <p>Редактирование промптов для типов отчетов</p>
                </div>
                <div class="section-actions">
                    <a href="/" class="btn-new-job">
                        <i class="fas fa-home"></i>
                        <span>Список заданий</span>
                    </a>
                </div>

                <!-- Settings form -->
                <div class="settings-form">
                    <div class="form-group">
                        <label for="reportTypeSelect" class="form-label">Тип отчета</label>
                        <select id="reportTypeSelect" class="form-select">
                            <option value="" disabled selected>Загрузка...</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="reportNameLabel" class="form-label">Название</label>
                        <span id="reportNameLabel" class="report-name">—</span>
                    </div>

                    <div class="form-group">
                        <label for="promptTextarea" class="form-label">Промпт</label>
                        <textarea id="promptTextarea" class="form-input" rows="12" placeholder="Промпт будет подставлен при выборе отчета..."></textarea>
                    </div>

                    <div class="form-buttons">
                        <button id="saveButton" class="submit-button" disabled>
                            <i class="fas fa-save"></i>
                            <span>Сохранить</span>
                        </button>
                    </div>

                    <!-- Notification zone -->
                    <div id="notificationZone" class="notification-zone" style="display: none;"></div>
                </div>
            </div>
        </main>
    </div>

    <script>
    // Theme switcher
    (function() {
        const toggle = document.getElementById('themeToggle');
        const label = document.getElementById('themeLabel');
        const saved = localStorage.getItem('theme');
        if (saved === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            toggle.checked = true;
            label.textContent = 'Тёмная';
        }
        toggle.addEventListener('change', function() {
            if (this.checked) {
                document.documentElement.setAttribute('data-theme', 'dark');
                label.textContent = 'Тёмная';
                localStorage.setItem('theme', 'dark');
            } else {
                document.documentElement.removeAttribute('data-theme');
                label.textContent = 'Светлая';
                localStorage.setItem('theme', 'light');
            }
        });
    })();

    // Settings logic
    (async function() {
        const select = document.getElementById('reportTypeSelect');
        const nameLabel = document.getElementById('reportNameLabel');
        const textarea = document.getElementById('promptTextarea');
        const saveBtn = document.getElementById('saveButton');
        const notif = document.getElementById('notificationZone');

        let originalPrompts = {}; // {id: prompt} — для сравнения
        let selectedOriginal = null; // оригинальный промпт выбранного отчета

        // Загрузить отчеты
        try {
            const resp = await fetch('/api/v1/settings');
            const data = await resp.json();
            if (!data.types || data.types.length === 0) {
                select.innerHTML = '<option value="" disabled selected>Нет типов отчетов</option>';
                return;
            }
            select.innerHTML = '';
            data.types.forEach(function(t) {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = t.name;
                originalPrompts[t.id] = t.prompt || '';
                select.appendChild(opt);
            });
        } catch (e) {
            select.innerHTML = '<option value="" disabled selected>Ошибка загрузки</option>';
            return;
        }

        // При смене отчета
        select.addEventListener('change', function() {
            const id = this.value;
            if (!id) return;
            const type = data.types.find(t => t.id === id);
            if (type) {
                nameLabel.textContent = type.name;
            }
            textarea.value = originalPrompts[id] || '';
            selectedOriginal = originalPrompts[id] || '';
            checkChanged();
        });

        // При ручном редактировании промпта
        textarea.addEventListener('input', checkChanged);

        function checkChanged() {
            saveBtn.disabled = (textarea.value === selectedOriginal);
        }

        // Сохранить
        saveBtn.addEventListener('click', async function() {
            const id = select.value;
            if (!id) return;
            const prompt = textarea.value;

            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Сохранение...</span>';

            try {
                const resp = await fetch('/api/v1/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({report_type: id, prompt: prompt})
                });
                const result = await resp.json();
                if (!resp.ok) {
                    throw new Error(result.detail || 'Ошибка сохранения');
                }
                // Обновить кэш оригиналов
                originalPrompts[id] = prompt;
                selectedOriginal = prompt;
                checkChanged();
                showNotification('Промпт сохранён', 'success');
            } catch (e) {
                showNotification(e.message, 'error');
                checkChanged();
            } finally {
                saveBtn.disabled = (textarea.value === selectedOriginal);
                saveBtn.innerHTML = '<i class="fas fa-save"></i> <span>Сохранить</span>';
            }
        });

        function showNotification(msg, type) {
            notif.textContent = msg;
            notif.style.display = 'block';
            notif.style.color = type === 'success' ? 'var(--success-color)' : 'var(--error-color)';
            notif.style.marginTop = '16px';
            notif.style.padding = '8px 12px';
            notif.style.borderRadius = '6px';
            notif.style.border = `1px solid ${type === 'success' ? 'var(--success-color)' : 'var(--error-color)'}`;
            setTimeout(function() { notif.style.display = 'none'; }, 3000);
        }
    })();
    </script>
</body>
</html>
```

---

## Task 5: Добавить кнопку "Настройки" в навигацию

**Файлы:**
- Modify: `src/templates/index.html:43-47`
- Modify: `src/templates/uploads.html:41-45`

- [ ] **Шаг 1: Добавить в index.html**

В `div.section-actions` на странице заданий (после кнопки "Новое задание"), добавить:

```html
<a href="/settings" class="btn-new-job">
    <i class="fas fa-cog"></i>
    <span>Настройки</span>
</a>
```

- [ ] **Шаг 2: Добавить в uploads.html**

В `div.section-actions` на странице загрузки (после кнопки "Список заданий"), добавить:

```html
<a href="/settings" class="btn-new-job">
    <i class="fas fa-cog"></i>
    <span>Настройки</span>
</a>
```

---

## Task 6: Тестирование

- [ ] **Шаг 1: Проверить загрузку страницы**

Запустить сервер:
```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python src/main.py
```

Открыть `http://localhost:8801/settings`. Проверить:
- Страница загружается без ошибок
- Выпадающий список содержит "Сжатый пересказ" и "Протокол терапевтической сессии"
- При выборе отчета — промпт подставляется в текстовое поле
- Кнопка "Сохранить" неактивна (без изменений)

- [ ] **Шаг 2: Проверить сохранение**

1. Изменить текст промпта в textarea
2. Кнопка "Сохранить" становится активной
3. Нажать "Сохранить"
4. Проверить `config/reports.json` — промпт обновлён
5. Перезагрузить страницу — изменённый промпт загружен

- [ ] **Шаг 3: Проверить навигацию**

1. На странице `/` и `/uploads` есть кнопка "Настройки"
2. Кнопка переключает тему на новой странице
3. Ссылка "Список заданий" на странице настроек работает

---

## Self-Review

**Spec coverage:**
- [x] GET `/settings` маршрут → Task 3
- [x] GET `/api/v1/settings` API → Task 1
- [x] POST `/api/v1/settings` API → Task 2
- [x] Шаблон `settings.html` → Task 4
- [x] Кнопка в навигации → Task 5
- [x] Выпадающий список отчетов → Task 4 (JS: `fetch('/api/v1/settings')`, populate `<select>`)
- [x] Текстовое поле промпта → Task 4 (JS: подстановка при `change` селекта, редактирование)
- [x] Кнопка "Сохранить" активна только при изменениях → Task 4 (JS: `checkChanged()` сравнивает с оригиналом)
- [x] Перезапись `config/reports.json` → Task 2 (POST endpoint)
- [x] Обработка ошибок → Task 2 (HTTPException), Task 4 (try/catch, showNotification)

**Placeholder scan:** Нет placeholder'ов. Все шаги содержат конкретный код.

**Type consistency:** Все имена переменных, CSS-классов, API путей согласованы между задачами.

**Scope:** Фocused — одна страница, один use case.

# URL Upload UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить поле ввода URL на страницу uploads для транскрипции видео/аудио по ссылке (бэкенд уже реализован).

**Architecture:** Единая форма с автовыбором endpoint: если URL заполнен → `POST /api/v1/transcribe-url`, если файл → `POST /api/v1/transcribe`. Поле ввода URL размещается над существующей drag&drop зоной.

**Tech Stack:** HTML, CSS (existing `new_style.css`), vanilla JS (embedded in `uploads.html`)

---

### Task 1: Добавить URL input в HTML

**Files:**
- Modify: `src/templates/uploads.html:55-62`

Вставить новый блок `<div class="url-input-section">` перед `<div class="upload-area">` (строка 55):

```html
<div class="url-input-section">
    <input type="url" id="urlInput" name="url" class="form-input url-input"
           placeholder="Вставьте URL видео или аудио">
</div>
```

- [ ] **Шаг 1: Вставить URL input section перед upload-area**

В [uploads.html:55](src/templates/uploads.html#L55) (строка `<div class="upload-area" id="dropArea">`) вставить перед ней:

```html
<div class="url-input-section">
    <input type="url" id="urlInput" name="url" class="form-input url-input"
           placeholder="Вставьте URL видео или аудио">
</div>
```

- [ ] **Шаг 2: Проверить результат**

Открыть `http://localhost:8000/uploads`, убедиться что поле ввода URL отображается над drag&drop зоной.

- [ ] **Шаг 3: Commit**

```bash
git add src/templates/uploads.html
git commit -m "feat: add URL input field to upload page"
```

---

### Task 2: Добавить CSS для URL input

**Files:**
- Modify: `src/static/new_style.css`

- [ ] **Шаг 1: Добавить стили URL input**

В [new_style.css](src/static/new_style.css) после блока `.file-input` (строка 250-252), перед `/* Input elements */` (строка 254) вставить:

```css
/* URL input section */
.url-input-section {
    width: 100%;
    margin-bottom: 12px;
}

.url-input {
    width: 100%;
}
```

Стили `.form-input url-input` автоматически наследуют оформление из существующего `.form-input` (строка 255+), включая тёмную тему.

- [ ] **Шаг 2: Проверить результат**

Открыть `http://localhost:8000/uploads`, переключить тему (светлая/тёмная) — URL поле должно корректно отображаться в обеих темах.

- [ ] **Шаг 3: Commit**

```bash
git add src/static/new_style.css
git commit -m "style: add CSS for URL input section on upload page"
```

---

### Task 3: Модифицировать submit handler для поддержки URL

**Files:**
- Modify: `src/templates/uploads.html:366-418`

Текущий submit handler (строки 366-418) жёстко закодирован на `POST /api/v1/transcribe` и требует файл. Нужно сделать его универсальным.

- [ ] **Шаг 1: Заменить submit handler**

В [uploads.html:366-418](src/templates/uploads.html#L366-L418) заменить весь блок `document.getElementById('uploadForm').addEventListener('submit', ...)` на:

```javascript
        // Обработка формы (файл или URL)
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();

            const urlValue = document.getElementById('urlInput').value.trim();
            const fileInput = document.getElementById('audioFile');
            const files = fileInput.files;

            // Валидация: нужен либо URL, либо файл
            if (!urlValue && files.length === 0) {
                showError('Введите URL или выберите файл для загрузки');
                return;
            }

            // Валидация URL
            if (urlValue && !urlValue.match(/^https?:\/\//)) {
                showError('URL должен начинаться с http:// или https://');
                return;
            }

            // Валидация файла (если не URL)
            if (!urlValue && files.length > 0) {
                if (!validateFile(files[0].name)) {
                    showError('Неподдерживаемый формат файла. Используйте: WAV, MP3, M4A, FLAC, AAC, OGG, WMA, WEBM, MP4, MKV');
                    return;
                }
            }
            clearError();

            // Выбор endpoint
            const endpoint = urlValue ? '/api/v1/transcribe-url' : '/api/v1/transcribe';

            const formData = new FormData(this);
            if (urlValue) {
                formData.set('url', urlValue);
            }

            const submitButton = document.getElementById('submitButton');
            const originalText = submitButton.innerHTML;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Обработка...';
            submitButton.disabled = true;

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok && (data.status === "queued" || data.status === "processing")) {
                    window.location.href = '/?redirect=' + data.job_id;
                    return;
                }

                if (response.ok && data.status === "completed" && data.text) {
                    window.location.href = '/?redirect=' + data.job_id;
                    return;
                }

                if (!response.ok) {
                    showError(data.error || data.detail || 'Ошибка обработки');
                }
            } catch (error) {
                showError('Ошибка соединения: ' + error.message);
            } finally {
                submitButton.innerHTML = originalText;
                submitButton.disabled = false;
            }
        });
```

Ключевые изменения:
- Проверка `urlValue` — если заполнен, используем `/api/v1/transcribe-url`
- Валидация URL: не пустой + начинается с `http://` или `https://`
- Если URL не заполнен — валидация файла как раньше
- `formData.set('url', urlValue)` — добавляем URL в форму
- `fetch(endpoint, ...)` — динамический endpoint
- `data.detail` в ошибке — backend FastAPI возвращает `detail` для ошибок валидации

- [ ] **Шаг 2: Проверить результат**

Запустить приложение (`source .venv/bin/activate && python src/main.py`), открыть uploads:
1. Ввести URL (например `https://www.youtube.com/watch?v=test`) — нажать «Транскрибировать» — запрос должен уйти на `/api/v1/transcribe-url`
2. Выбрать файл — нажать «Транскрибировать» — запрос должен уйти на `/api/v1/transcribe` (файловая загрузка не сломана)
3. Ввести невалидный URL без `http://` — показать ошибку валидации

- [ ] **Шаг 3: Commit**

```bash
git add src/templates/uploads.html
git commit -m "feat: support URL transcription in unified form submit handler"
```

---

### Task 4: Обновить TODO.md

**Files:**
- Modify: `docs/TODO.md:123`

- [ ] **Шаг 1: Отметить задачу как выполненную**

В [TODO.md:123](docs/TODO.md#L123) заменить:

```markdown
- [ ] Добавить загрузку видео и аудио по URL
```

На:

```markdown
- [x] Добавить загрузку видео и аудио по URL — UI: поле URL на uploads.html, unified form submit
```

- [ ] **Шаг 2: Commit**

```bash
git add docs/TODO.md
git commit -m "docs: mark URL upload as completed in TODO"
```

---

## Верификация

1. Запустить: `source .venv/bin/activate && python src/main.py`
2. Открыть `http://localhost:8000/uploads`
3. URL поле отображается над drag&drop зоной
4. URL поле корректно в тёмной теме
5. Валидный URL + submit → запрос на `/api/v1/transcribe-url`
6. Файл + submit → запрос на `/api/v1/transcribe`
7. Невалидный URL → ошибка валидации
8. URL отображается в loading state (обрезка не требуется — backend обрабатывает)
9. Успех → редирект на `/?redirect=<job_id>`
10. Ошибка → toast с `data.detail`

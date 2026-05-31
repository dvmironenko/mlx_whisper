# Документация фронтенда MLX-Transcriber

## Общая архитектура

Фронтенд приложения MLX-Transcriber — это сервер-рендеренное SPA-подобное приложение на базе FastAPI. HTML-шаблоны рендерятся сервером, а интерактивность обеспечивается встроенным JavaScript с использованием Fetch API для AJAX-запросов.

### Структура файлов

```
src/
├── templates/
│   ├── uploads.html      # Страница загрузки аудио
│   ├── index.html        # Список заданий транскрипции
│   └── settings.html     # Настройки типов отчетов
├── static/
│   ├── new_style.css     # Основные стили (~1750 строк)
│   └── style.css         # Legacy (не используется)
```

### Общие элементы

Все страницы имеют единую структуру:
- **`app-header`** — шапка с логотипом (иконка микрофона + название) и подзаголовком
- **`app-controls`** — панель управления: переключатель темы (светлая/тёмная) + кнопки навигации
- **`app-main`** — основной контент (flex column)
- **`app-footer`** — подвал (только на uploads.html)

Переключатель темы сохраняет выбор в `localStorage('theme')` и устанавливает `data-theme` атрибут на `<html>`.

---

## Страницы

### 1. Загрузка (`/uploads`)

**Template:** `src/templates/uploads.html`
**Route:** `GET /uploads`

#### Блоки страницы

| Блок | Описание |
|------|----------|
| `upload-area` | Drag & Drop зона для файлов. Поддерживает перетаскивание и клик для выбора |
| `mechanism` | Select: выбор механизма — Whisper MLX или oMLX |
| `language` | Select: язык транскрипции (автоопределение, русский, английский и др.) |
| `transcription-parameters` | Аккордеон с расширенными параметрами (свёрнут по умолчанию) |

#### Параметры транскрипции (аккордеон)

| Параметр | Тип | Описание |
|----------|-----|----------|
| `task` | Select | Задача: транскрибация или перевод |
| `model` | Select | Модель Whisper (tiny, base, small, medium, large) |
| `wordTimestamps` | Checkbox | Временные метки слов |
| `conditionOnPreviousText` | Checkbox | Использовать предыдущий текст для контекста |
| `noSpeechThreshold` | Range | Порог отсутствия речи (0–1) |
| `hallucinationSilenceThreshold` | Range | Порог тишины для подавления галлюцинаций |
| `removeSilence` | Select | Удалять тишину до транскрипции |
| `silenceThreshold` | Range | Порог тишины в dB |
| `silenceDuration` | Range | Длительность тишины для разделения |
| `initialPrompt` | Text | Начальный текст для контекстной транскрипции |

#### JavaScript-логика

- **Drag & Drop**: обработчики `dragenter`, `dragover`, `dragleave`, `drop` на `dropArea`. При drop — файлы передаются в `fileInput.files`.
- **Отправка формы**: `POST /api/v1/transcribe` с `FormData`. При успехе — редирект на `/` с параметром `?redirect={job_id}`.
- **Загрузка конфигурации**: `GET /api/v1/config` — заполняет параметры транскрипции значениями по умолчанию из `.env`.
- **Аккордеон**: клик по `parametersHeader` переключает `data-expanded` и `maxHeight` у `.parameters-content`.
- **Переключение механизмов**: при выборе oMLX скрываются Whisper-специфичные параметры (модель, task, пороги и т.д.).

---

### 2. Список заданий (`/`)

**Template:** `src/templates/index.html`
**Route:** `GET /`

#### Блоки страницы

| Блок | Описание |
|------|----------|
| `jobs-filters` | Поиск по ID задания + фильтр по периоду (все / 7 дней / 30 дней) |
| `jobsCardsContainer` | Динамический контейнер карточек заданий |
| `emptyJobsState` | Состояние «нет заданий» (показывается когда список пуст) |

#### Карточка задания

Каждая карточка содержит:
- **Header**: название файла + статус-бейдж (`status-badge status-{queued|processing|completed|failed|cancelled}`)
- **Meta**: модель, язык, длительность, дата создания
- **Files**: список файлов задания с кнопками просмотра, скачивания, удаления
- **Actions**: кнопки «Отменить» (для queued/processing), «Отчет» (для completed), «Удалить»

#### JavaScript-логика

- **`loadJobs()`**: `GET /api/v1/jobs` — загружает список, фильтрует, рендерит карточки через `createJobCard()`.
- **Polling**: `startPolling()` — если есть активные задания (queued/processing), запускает `setInterval(loadJobs, 5000)` (обновление каждые 5 сек). `stopPolling()` — останавливает при отсутствии активных.
- **`createJobCard(job)`**: создаёт DOM-элемент карточки со всеми кнопками и обработчиками.
- **`openResultModal(jobId)`**: `GET /api/v1/jobs/{job_id}` — открывает модальное окно с текстом транскрипции. Передаёт `fileType='text'` в `showTextView`.
- **`generateReport(jobId, reportType)`**: `POST /api/v1/report/{job_id}` — запускает генерацию отчёта. Добавляет job_id в `reportingJobs` Set и запускает `startReportPolling()`.
- **`pollReportStatuses()`**: `GET /api/v1/report-status/{job_id}` для каждого job из `reportingJobs` — обновляет бейджи статуса генерации.
- **`viewFileContent(jobId, filename)`**: `GET /api/v1/files/{filename}/content` — открывает содержимое текстового файла в модалке. Определяет тип файла по расширению и передаёт `fileType` в `showTextView`.
- **`filterJobs()`**: фильтрует `jobsList` по поиску (по ID) и периоду (по `created_at`).
- **Удаление**: `DELETE /api/v1/jobs/{job_id}` — с подтверждением через модальное окно.
- **Удаление файла**: `DELETE /api/v1/jobs/{job_id}/files/{filename}` — без дополнительного подтверждения.

---

### 3. Настройки (`/settings`)

**Template:** `src/templates/settings.html`
**Route:** `GET /settings`

#### Блоки страницы

| Блок | Описание |
|------|----------|
| `reportTypeSelect` | Select: выбор типа отчета (summary, protocol, eot) |
| `reportNameTextarea` | Textarea (1 row): название отчета |
| `promptTextarea` | Textarea (12 rows): текст промпта для LLM |
| `saveButton` | Кнопка «Сохранить» (disabled пока нет изменений) |
| `refreshButton` | Кнопка «Обновить настройки» (перечитывает конфиг) |
| `notificationZone` | Зона уведомлений об успехе/ошибке |

#### JavaScript-логика

- **Загрузка типов**: `GET /api/v1/settings` — заполняет select, кэширует `originalPrompts` и `originalNames` для сравнения.
- **Автовыбор**: при загрузке автоматически выбирается первый тип отчета.
- **`checkChanged()`**: сравнивает текущие значения с оригинальными (`selectedOriginal`, `selectedOriginalName`), разблокирует кнопку «Сохранить» при различиях.
- **Сохранение**: `POST /api/v1/settings` с JSON `{report_type, name, prompt}`. При успехе обновляет кэш оригиналов.
- **Обновление**: `POST /api/v1/settings/refresh` — перечитывает `.env` и сбрасывает кэш report_types на сервере. Перезаполняет select и обновляет текущий выбор.
- **`showNotification(msg, type)`**: показывает уведомление с цветовой индикацией (зелёный — success, красный — error), скрывается через 3 секунды.

---

## API-эндпоинты фронтенда

### Transcription

| Метод | Endpoint | Описание | Request | Response |
|-------|----------|----------|---------|----------|
| POST | `/api/v1/transcribe` | Загрузка аудиофайла | FormData (file + параметры) | `{job_id, status: "queued"}` |
| POST | `/api/v1/transcribe-url` | Транскрибация по URL | FormData (url + параметры) | `{job_id, status: "queued"}` |

### Health & Config

| Метод | Endpoint | Описание | Response |
|-------|----------|----------|----------|
| GET | `/api/v1/health` | Проверка состояния | `{status: "healthy", version: "1.0.0"}` |
| GET | `/api/v1/config` | Конфигурация из `.env` | `{initial_prompt, remove_silence, silence_threshold, ...}` |
| GET | `/api/v1/omlx/health` | Проверка oMLX API | `{omlx: "connected\|unreachable\|disabled"}` |
| GET | `/api/v1/models` | Список моделей | `{supported_models: ["tiny", "base", ...]}` |

### Jobs

| Метод | Endpoint | Описание | Response |
|-------|----------|----------|----------|
| GET | `/api/v1/jobs` | Список всех заданий | `[{job_id, status, original_filename, ...}]` |
| GET | `/api/v1/jobs/{job_id}` | Детали задания | `{job_id, status, text, error, files: [...]}` |
| DELETE | `/api/v1/jobs/{job_id}` | Удалить задание | `{status: "deleted", job_id: "..."}` |

### Files

| Метод | Endpoint | Описание | Response |
|-------|----------|----------|----------|
| GET | `/api/v1/files/{filename}/download` | Скачать файл | FileResponse |
| GET | `/api/v1/jobs/{job_id}/files/{filename}/download` | Скачать файл задания | FileResponse |
| GET | `/api/v1/jobs/{job_id}/files/{filename}/content` | Содержимое текстового файла | PlainTextResponse |
| DELETE | `/api/v1/jobs/{job_id}/files/{filename}` | Удалить файл задания | `{status: "deleted"}` |

### Reports

| Метод | Endpoint | Описание | Request | Response |
|-------|----------|----------|---------|----------|
| POST | `/api/v1/report/{job_id}` | Запустить генерацию отчёта | JSON `{report_type}` (опц.) | `{status: "started", ...}` |
| GET | `/api/v1/report-status/{job_id}` | Статус генерации | — | `{job_id, status: "generating\|idle"}` |
| GET | `/api/v1/report-types` | Типы отчетов (без промптов) | — | `{types: [{id, name}]}` |

### Settings

| Метод | Endpoint | Описание | Request | Response |
|-------|----------|----------|---------|----------|
| GET | `/api/v1/settings` | Типы отчетов с промптами | — | `{types: [{id, name, prompt}]}` |
| POST | `/api/v1/settings` | Сохранить промпт | JSON `{report_type, name, prompt}` | `{status: "ok"}` |
| POST | `/api/v1/settings/refresh` | Перечитать конфиг | — | `{types: [...]}` |

### Cache

| Метод | Endpoint | Описание | Request | Response |
|-------|----------|----------|---------|----------|
| GET | `/api/v1/cache/models` | Статистика кэша | — | `{models: {...}}` |
| POST | `/api/v1/cache/clear` | Очистить кэш | — | `{status: "success"}` |
| POST | `/api/v1/cache/preload` | Предзагрузить модель | JSON `{model}` | `{status: "success", model: "..."}` |

---

## CSS-стилизация

### CSS Custom Properties

**Light theme (по умолчанию):**

| Переменная | Значение | Применение |
|------------|----------|------------|
| `--primary-color` | `#2d3748` | Заголовки, основной текст |
| `--secondary-color` | `#718096` | Вторичный текст |
| `--accent-color` | `#4299e1` | Акценты, ссылки |
| `--background-dark` | `#f7fafc` | Фон страницы |
| `--background-light` | `#ffffff` | Фон карточек |
| `--card-bg` | `#ffffff` | Фон карточек |
| `--text-primary` | `#2d3748` | Основной текст |
| `--text-secondary` | `#718096` | Вторичный текст |
| `--border-color` | `#e2e8f0` | Границы |
| `--success-color` | `#48bb78` | Успех |
| `--error-color` | `#e53e3e` | Ошибки |
| `--warning-color` | `#ecc94b` | Предупреждения |
| `--shadow` | `0 1px 3px rgba(0,0,0,0.1)` | Тени |
| `--transition` | `all 0.2s ease` | Анимации переходов |
| `--switch-thumb` | `#2d3748` | Ползунок переключателя темы |
| `--switch-track` | `#a0aec0` | Трек переключателя темы |

**Dark theme (`[data-theme="dark"]`):**

| Переменная | Значение |
|------------|----------|
| `--primary-color` | `#a0aec0` |
| `--secondary-color` | `#718096` |
| `--accent-color` | `#63b3ed` |
| `--background-dark` | `#1a202c` |
| `--background-light` | `#2d3748` |
| `--card-bg` | `#2d3748` |
| `--text-primary` | `#f7fafc` |
| `--text-secondary` | `#a0aec0` |
| `--border-color` | `#4a5568` |
| `--shadow` | `0 1px 3px rgba(0,0,0,0.3)` |
| `--switch-thumb` | `#f7fafc` |
| `--switch-track` | `#4a5568` |

### Основные классы

| Класс | Описание |
|-------|----------|
| `.container` | Основной контейнер (max-width: 960px, margin: 0 auto) |
| `.app-header` | Шапка приложения (синий фон, белый текст) |
| `.app-title` | Название приложения |
| `.app-subtitle` | Подзаголовок страницы |
| `.app-controls` | Панель управления (flex, space-between) |
| `.theme-switch-container` | Контейнер переключателя темы |
| `.theme-toggle` | Скрытый checkbox для переключателя |
| `.theme-switch-track` | Визуальный трек переключателя |
| `.theme-switch-thumb` | Ползунок переключателя |
| `.app-controls-actions` | Контейнер кнопок навигации |
| `.btn-new-job` | Кнопка навигации («Новое задание», «Настройки») |
| `.app-main` | Основной контент (flex: 1, padding) |
| `.upload-section` | Секция контента (фон, border-radius, padding, shadow) |
| `.section-header` | Заголовок секции |
| `.section-description` | Описание секции |
| `.settings-form` | Форма настроек (flex column, gap) |
| `.form-group` | Группа формы (label + input/select) |
| `.form-label` | Метка формы |
| `.form-select` | Стилизация select |
| `.form-input` | Стилизация input/textarea |
| `.range-container` | Контейнер range slider (label + input + value) |
| `.range-value` | Отображаемое значение range |
| `.checkbox-group` | Группа чекбокса (label + input) |
| `.transcription-parameters` | Аккордеон параметров |
| `.parameters-header` | Заголовок аккордеона (cursor: pointer) |
| `.parameters-content` | Контент аккордеона (max-height transition) |
| `.submit-button` | Кнопка отправки (primary color, full width) |
| `.submit-button.secondary` | Вторичная кнопка (opacity: 0.75) |
| `.jobs-filters` | Фильтры списка (search + period) |
| `.jobs-cards-container` | Контейнер карточек |
| `.job-card` | Карточка задания (border-radius, shadow, padding) |
| `.job-card-header` | Заголовок карточки |
| `.job-card-header-with-status` | Flex-контейнер заголовка + статус-бейдж |
| `.job-card-meta` | Мета-информация (model, language, duration, date) |
| `.job-card-files` | Список файлов задания |
| `.file-row` | Строка файла (filename + buttons) |
| `.job-card-actions` | Кнопки действий (report, delete, cancel) |
| `.status-badge` | Бейдж статуса (padding, border-radius, color) |
| `.status-queued` | Стиль для статуса «В очереди» |
| `.status-processing` | Стиль для статуса «Обработка» (с пульсацией) |
| `.status-completed` | Стиль для статуса «Готово» |
| `.status-failed` | Стиль для статуса «Ошибка» |
| `.status-cancelled` | Стиль для статуса «Отменён» |
| `.report-status-badge` | Бейдж статуса генерации отчёта |
| `.empty-jobs-state` | Состояние пустого списка |
| `.upload-area` | Зона drag & drop (border, dashed) |
| `.upload-area.dragover` | Состояние при перетаскивании |
| `.upload-area.has-file` | Состояние с выбранным файлом |
| `.result-modal` | Модальное окно просмотра результата |
| `.modal-overlay` | Overlay модального окна |
| `.app-footer` | Подвал приложения |

### Адаптивность

| Breakpoint | Изменения |
|------------|-----------|
| `max-width: 768px` | `padding: 20px 15px`, `app-title: 2rem`, `section-header h2: 1.5rem`, фильтры в колонку, кнопки на всю ширину |
| `max-width: 480px` | `container padding: 10px`, `app-title: 1.8rem`, `app-subtitle: 1rem`, `section-header h2: 1.3rem` |

### Анимации

```css
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.8); }
}
```

- **Spin**: используется для спиннеров загрузки (`fa-spin` из Font Awesome)
- **Pulse**: пульсация точки статуса «processing» (эффект активности)
- **Hover кнопок**: `opacity: 0.9` + `translateY(-1px)`
- **Аккордеон**: `max-height` transition 0.3s ease-out

---

## JavaScript-логика

### Pattern: Theme Switcher

Сохранение темы в `localStorage`. При загрузке страницы проверяет сохранённое значение и устанавливает `data-theme` атрибут.

```javascript
const saved = localStorage.getItem('theme');
if (saved === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
}
toggle.addEventListener('change', function() {
    document.documentElement.setAttribute('data-theme', this.checked ? 'dark' : 'light');
    localStorage.setItem('theme', this.checked ? 'dark' : 'light');
});
```

### Pattern: Drag & Drop

```javascript
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false);
});
dropArea.addEventListener('drop', handleDrop, false);

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    fileInput.files = files;
    updateFileDisplay(files[0]);
}
```

### Pattern: Polling активных заданий

```javascript
function startPolling() {
    const activeJobs = jobsList.filter(j =>
        j.status === 'queued' || j.status === 'processing');
    if (activeJobs.length === 0) { stopPolling(); return; }
    pollingJobs = new Set(activeJobs.map(j => j.job_id));
    refreshInterval = setInterval(loadJobs, 5000);
}

function stopPolling() {
    if (refreshInterval) { clearInterval(refreshInterval); refreshInterval = null; }
}
```

### Pattern: Модальные окна

```javascript
function openModal(content) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content">
            <button class="modal-close">&times;</button>
            ${content}
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}
```

### Pattern: Уведомления

```javascript
function showNotification(msg, type) {
    notif.textContent = msg;
    notif.style.display = 'block';
    notif.style.color = type === 'success' ? 'var(--success-color)' : 'var(--error-color)';
    notif.style.padding = '8px 12px';
    notif.style.borderRadius = '6px';
    notif.style.border = `1px solid ${type === 'success' ? 'var(--success-color)' : 'var(--error-color)'}`;
    setTimeout(() => { notif.style.display = 'none'; }, 3000);
}
```

### Pattern: Сравнение изменений (dirty check)

```javascript
let selectedOriginal = null; // оригинальное значение для сравнения

function checkChanged() {
    saveBtn.disabled = (textarea.value === selectedOriginal &&
                        nameTextarea.value === selectedOriginalName);
}
```

### Pattern: Отправка формы с состоянием загрузки

```javascript
form.addEventListener('submit', async function(e) {
    e.preventDefault();
    submitButton.disabled = true;
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Обработка...';

    try {
        const response = await fetch('/api/v1/transcribe', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (response.ok && data.status === 'queued') {
            window.location.href = '/?redirect=' + data.job_id;
        }
    } catch (error) {
        showError('Ошибка соединения: ' + error.message);
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = originalText;
    }
});
```

---

## Зависимости

| Зависимость | Назначение |
|-------------|------------|
| Font Awesome 6.4.0 | Иконки (CDN: `cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css`) |
| Google Fonts — Source Sans 3 | Основной шрифт |

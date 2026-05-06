# UI Update для Async Queue Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Обновить HTML/CSS/JS страниц uploads.html и index.html для корректной работы с асинхронным queue-based API.

**Architecture:** uploads.html переключается с inline-display результата на redirect к jobs list. index.html получает систему статусных бейджей, auto-refresh polling, и result modal.

**Tech Stack:** HTML, CSS (new_style.css), vanilla JavaScript.

---

## Обзор проблем

После интеграции очереди API изменил формы ответов:

| Endpoint | Было | Стало |
|----------|------|-------|
| POST /transcribe | `{text, segments, ...}` полный результат | `{job_id, status: "queued"}` |
| GET /jobs | массив с `files: [{name, size}]` | массив метаданных без `files` |
| GET /jobs/{id} | `{job_id, status: "pending"}` | полный metadata + text/segments/files при completed |

UI всё ещё ожидает старые ответы → показывает пустой текст и крашится на `job.files.reduce()`.

## Изменяемые файлы

- `src/templates/uploads.html` — поток submit → redirect
- `src/templates/index.html` — статусы, polling, modal
- `src/static/new_style.css` — новые CSS классы

## Компоновка страницы index.html

```
┌──────────────────────────────────────────────────┐
│  Задания на транскрипцию        [auto-refresh]   │
├──────────────────────────────────────────────────┤
│  Podcast Episode 42          [● queued]          │
│  model: turbo │ language: ru │ duration: 120s    │
│  [Open] [Delete]                                    │
├──────────────────────────────────────────────────┤
│  Interview Recording     [● processing]          │
│  model: base │ language: en │ duration: 3600s    │
│  [Open] [Cancel] [Delete]                         │
├──────────────────────────────────────────────────┤
│  Meeting Notes             [● completed]         │
│  model: turbo │ language: ru │ duration: 180s    │
│  [View Result] [Report] [Delete]                  │
├──────────────────────────────────────────────────┤
│  Corrupted Audio           [● failed]            │
│  model: turbo │ language: ru                     │
│  [Delete]                                         │
└──────────────────────────────────────────────────┘
```

## Details

### uploads.html — submit flow

1. При `status: "queued"` → `window.location.href = 'index.html?redirect=' + jobId`
2. Форма очищается, показывается toast "Задание отправлено"
3. При `status: "completed"` (edge case fast job) → показать результат на странице (сохранить backward compat)

### index.html — createJobCard(job)

Новая структура карточки:
- **Header:** filename (left), status-badge (right)
- **Meta line:** model, language, duration, job_id, transcription_duration (если completed)
- **Actions:** View Result (completed, primary), Report (all), Cancel (queued/processing), Delete (all)
- **Error line:** для failed — показать короткое сообщение

### index.html — auto-refresh polling

```javascript
let refreshInterval = null;
let pollingJobs = new Set();

function startPolling() {
  // Определяем, есть ли активные задания
  const activeJobs = jobs.filter(j => j.status === 'queued' || j.status === 'processing');
  if (activeJobs.length === 0) {
    stopPolling();
    return;
  }
  pollingJobs = new Set(activeJobs.map(j => j.job_id));
  refreshInterval = setInterval(fetchJobs, 3000);
}

function stopPolling() {
  clearInterval(refreshInterval);
  refreshInterval = null;
  pollingJobs.clear();
}

function fetchJobs() {
  // GET /api/v1/jobs и обновление карточек
  // Для active jobs — отдельный GET /api/v1/jobs/{id} для точного статуса
}
```

### index.html — result modal

- Открывается по клику "View Result" для completed jobs
- Показывает: заголовок (filename), текст транскрипции (pre-wrap, scrollable), список файлов, кнопку копирования
- Закрытие: клик на оверлей, кнопка, Escape
- Данные загружаются через `GET /api/v1/jobs/{job_id}` (отдельный fetch, не из list)

### new_style.css — новые CSS классы

```css
/* Status badges */
.status-badge — badge container с точкой-индикатором
.status-queued, .status-processing, .status-completed, .status-failed, .status-cancelled
.status-dot — пульсация для processing

/* Result modal */
.result-modal — full-screen overlay
.result-modal-content — content container
.result-text — scrollable text area
.file-list — tag-style file list

/* Buttons */
.btn-view-result — primary кнопка
```

Dark theme: все статусные цвета имеют dark-варианты через `[data-theme="dark"]`.

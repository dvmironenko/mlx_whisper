# Report Generation Status Badge Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** При запуске генерации отчета status-badge на карточке задания меняется на "Генерация отчета", по завершении — на "Готово".

**Architecture:** Новый бэкенд-эндпоинт `GET /api/v1/report-status/{job_id}` отслеживает статус генерации отчета. Фронтенд хранит Set активных генераций и опрашивает эндпоинт каждые 3 секунды. При завершении — бейдж сменяется на "Готово", карточка перерисовывается.

**Tech Stack:** Python, FastAPI, vanilla JavaScript, CSS animations

---

## Архитектура

Система состоит из двух частей:

1. **Бэкенд:** Эндпоинт `GET /api/v1/report-status/{job_id}` возвращает статус генерации отчета для задания.
2. **Фронтенд:** Set `reportingJobs` отслеживает активные генерации. Функция `pollReportStatuses()` опрашивает эндпоинт каждые 3 секунды. `createJobCard()` отображает бейдж "Генерация отчета" для активных генераций.

### Диаграмма потока

```
User clicks "Отчет"
    → generateReport(jobId, reportType)
        → POST /api/v1/report/{jobId}
            → бэкенд: adds jobId to generating_reports Set
            → бэкенд: returns 200 OK
        → reportingJobs.add(jobId)
        → pollReportStatuses()
            → GET /api/v1/report-status/{jobId} (every 3s)
                → status: "generating" → wait
                → status: "done" → reportingJobs.delete(jobId), reload jobs
                → status: "error" → reportingJobs.delete(jobId), show error
```

---

## Бэкенд API

### Эндпоинт

```
GET /api/v1/report-status/{job_id}
```

**Response (200 OK):**
```json
{
  "job_id": "abc-123",
  "status": "generating" | "done" | "not_started" | "error"
}
```

**Response (404):**
```json
{
  "detail": "Job not found"
}
```

### Статусы

| Статус | Условие | Описание |
|--------|---------|----------|
| `generating` | `job_id` в `generating_reports` | Генерация запущена, файл еще не записан |
| `done` | Файл отчета найден в `uploads/{job_id}/` и `job_id` не в `generating_reports` | Генерация завершена, файл записан |
| `not_started` | Ничего не найдено | Генерация не запускалась |
| `error` | Задание не найдено в `uploads/` | Job ID не существует |

### Изменение существующего кода

В `_start_report_generation()` (router.py):

1. При старте генерации: добавить `job_id` в `generating_reports` Set
2. При завершении (finally блок): убрать `job_id` из `generating_reports` Set

```python
# В _start_report_generation() — router.py, функция run():
def run():
    generating_reports.add(job_id)  # Добавляем при старте
    try:
        # существующая логика: load_segments_file, generate_report_via_openai_sync, save_report
        # (router.py:~46-91)
    finally:
        generating_reports.discard(job_id)  # Убираем при завершении
```

### Файлы отчета

Бэкенд ищет файлы, начинающиеся с `report_` в директории задания:
```
uploads/{job_id}/report_*.txt
```

Если такой файл найден и job_id не в `generating_reports` → статус `done`.

---

## Фронтенд

### Новые переменные

```javascript
let reportingJobs = new Set(); // job_id активных генераций
```

### Изменение `generateReport(jobId, reportType)`

При успешном ответе (response.ok):
```javascript
reportingJobs.add(jobId);
pollReportStatuses();
```

### Новая функция `pollReportStatuses()`

```javascript
let reportStatusInterval = null;

async function pollReportStatuses() {
    if (reportingJobs.size === 0) {
        // Остановить интервал если нет активных генераций
        if (reportStatusInterval) {
            clearInterval(reportStatusInterval);
            reportStatusInterval = null;
        }
        return;
    }

    // Запустить интервал если ещё не запущен
    if (!reportStatusInterval) {
        reportStatusInterval = setInterval(pollReportStatuses, 3000);
    }

    const promises = Array.from(reportingJobs).map(async (jobId) => {
        try {
            const resp = await fetch(`/api/v1/report-status/${jobId}`);
            if (!resp.ok) {
                reportingJobs.delete(jobId);
                return;
            }
            const data = await resp.json();
            if (data.status === 'done') {
                reportingJobs.delete(jobId);
                showNotification('Отчет готов', 'success');
                loadJobs(); // Перерисовать карточку
            } else if (data.status === 'error') {
                reportingJobs.delete(jobId);
                showNotification('Ошибка генерации отчета', 'error');
            }
            // 'generating' — ждём следующего цикла
        } catch (e) {
            // Сетевая ошибка — пропускаем, ждём следующего цикла
        }
    });

    await Promise.all(promises);
}
```

Интервал опроса: 3 секунды. Интервал запускается автоматически при первой генерации и останавливается когда все отчеты сгенерированы.

### Изменение `createJobCard(job)`

В блоке создания status-badge:

```javascript
const STATUS_LABELS = {
    'queued': 'В очереди',
    'processing': 'Обработка',
    'completed': 'Готово',
    'failed': 'Ошибка',
    'cancelled': 'Отменён',
    'report_generating': 'Генерация отчета'
};

let statusClass = `status-${job.status}`;
let statusText = STATUS_LABELS[job.status] || job.status;

// Проверяем активную генерацию отчета
if (reportingJobs.has(job.job_id)) {
    statusClass = 'status-report-generating';
    statusText = 'Генерация отчета';
}

statusBadge.className = statusClass;
statusBadge.innerHTML = `<span class="status-dot"></span> ${statusText}`;
```

### CSS — новые стили

```css
/* Бейдж "Генерация отчета" */
.status-report-generating {
    background-color: var(--warning-color);
    color: #000;
    animation: status-pulse 2s infinite;
}

@keyframes status-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.status-report-generating .status-dot {
    background-color: #000;
}
```

---

## Обработка ошибок и крайние случаи

| Сценарий | Поведение |
|----------|-----------|
| Бэкенд вернул `not_started` | job_id не в `reportingJobs` — ничего не делаем |
| Бэкенд вернул `error` (job не найден) | Убираем из Set, показываем уведомление об ошибке |
| Сетевая ошибка при опросе статуса | Пропускаем, ждём следующего цикла (3 сек) |
| Пользователь закрыл страницу | Состояние теряется (Set в памяти) — нормально |
| Пользователь перезагрузил страницу | Состояние теряется — polling не запущен — нормально |
| Несколько отчетов параллельно | Каждый job_id отдельно в Set, каждый опрашивается отдельно |
| Отчет уже создан до начала | Эндпоинт вернёт `done` — бейдж сменится на "Готово" |

---

## Тестирование

### Е2Е (Playwright)

1. Загрузить файл → дождаться статуса "Готово"
2. Нажать "Отчет" → проверить что бейдж стал "Генерация отчета"
3. Подождать завершения генерации → проверить что бейдж стал "Готово"
4. Проверить что уведомление "Отчет готов" появилось
5. Проверить что файл отчета появился в списке файлов

### Unit-тесты (если применимо)

- Тест функции `pollReportStatuses()` с моковыми ответами
- Тест `createJobCard()` с job_id в `reportingJobs` и без

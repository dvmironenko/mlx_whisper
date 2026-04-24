# Спецификация: Страница со списком заданий

**Дата:** 2026-04-24  
**Цель:** Добавить веб-интерфейс для просмотра истории транскрипций

---

## 1. Архитектура

### 1.1 Обзор

Добавить на главную страницу (`new_index.html`) вторую вкладку "Задания", которая отображает список всех сохранённых транскрипций в таблице с возможностью фильтрации и действий (скачивание, удаление).

### 1.2 Структура страницы

```
┌─────────────────────────────────────────────────┐
│  Загрузка                Задания  (вкладки)    │
├─────────────────────────────────────────────────┤
│  Фильтры: [Поиск] [Период ▼] [Обновить]       │
├─────────────────────────────────────────────────┤
│  Таблица заданий:                               │
│  ┌────┬──────┬──────┬──────┬─────────────┐    │
│  │ ID │Файлы│Размер│Дата│ Действия   │    │
│  └────┴──────┴──────┴──────┴─────────────┘    │
└─────────────────────────────────────────────────┘
```

---

## 2. Компоненты

### 2.1 Навигация (вкладки)

| Элемент | Текущее состояние | Изменение |
|---------|-------------------|-----------|
| `#uploadSection` | Отображается | Скрыть при выборе вкладки "Задания" |
| `#jobsSection` | Не существует | Создать новую секцию |

### 2.2 Панель фильтрации

```html
<div class="jobs-filters">
  <input type="text" id="jobSearch" placeholder="Поиск по ID...">
  <select id="jobPeriodFilter">
    <option value="all">Все задания</option>
    <option value="7">Последние 7 дней</option>
    <option value="30">Последние 30 дней</option>
  </select>
  <button id="refreshJobsBtn" class="btn-primary">Обновить</button>
</div>
```

### 2.3 Таблица заданий

```html
<table id="jobsTable">
  <thead>
    <tr>
      <th>ID Задания</th>
      <th>Файлы</th>
      <th>Размер</th>
      <th>Дата создания</th>
      <th>Действия</th>
    </tr>
  </thead>
  <tbody id="jobsTableBody">
    <!-- Заполняется динамически -->
  </tbody>
</table>
```

---

## 3. API

### 3.1 Существующие endpoints

- `GET /api/v1/jobs` — получить список заданий (уже реализован)
- `GET /api/v1/files/{filename}/download` — скачивание файла (уже реализован)

### 3.2 Новые endpoints

**DELETE /api/v1/jobs/{job_id}** — удаление задания

```python
@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Удалить задание и все связанные файлы."""
    job_dir = os.path.join(DATA_UPLOADS_DIR, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Job not found")
    
    shutil.rmtree(job_dir)
    return {"status": "deleted", "job_id": job_id}
```

---

## 4. Логика JavaScript

### 4.1 Состояние

```javascript
let jobsList = [];  // Хранит текущий список заданий
let refreshInterval = null;  // Интервал автообновления
```

### 4.2 Функции

| Функция | Назначение |
|---------|-----------|
| `loadJobs()` | Загрузить список заданий с сервера |
| `renderJobs(jobs)` | Отобразить список в таблице |
| `filterJobs()` | Применить фильтры к отображению |
| `formatFileSize(bytes)` | Форматировать размер в MB/KB |
| `formatDate(dateStr)` | Форматировать дату |
| `deleteJob(job_id)` | Удалить задание |

### 4.3 Автообновление

- Интервал: 30 секунд
- Запуск: при переключении на вкладку "Задания"
- Остановка: при переключении на другую вкладку

---

## 5. Стили

Добавить в `src/static/new_style.css`:

```css
/* Jobs section */
#jobsSection { display: none; }
#jobsSection.active { display: block; }

/* Jobs table */
#jobsTable { width: 100%; border-collapse: collapse; margin-top: 20px; }
#jobsTable th, #jobsTable td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
#jobsTable th { background: #f9fafb; font-weight: 600; }
#jobsTable tr:hover { background: #f9fafb; }

/* Job ID */
.job-id { font-family: monospace; font-size: 12px; color: #6b7280; word-break: break-all; }

/* Files list */
.files-list { display: flex; flex-wrap: wrap; gap: 5px; }
.file-badge { padding: 4px 8px; background: #e0e7ff; color: #3730a3; border-radius: 4px; font-size: 12px; }

/* Actions */
.action-buttons { display: flex; gap: 8px; }
.btn-danger { background: #ef4444; color: white; }
```

---

## 6. Порядок реализации

1. **API** — добавить `DELETE /api/v1/jobs/{job_id}` в `router.py`
2. **Стили** — добавить CSS для таблицы в `new_style.css`
3. **HTML** — добавить секцию `#jobsSection` в `new_index.html`
4. **JavaScript** — реализовать логику загрузки, отображения, фильтрации

---

## 7. Критерии успеха

- [ ] Вкладка "Задания" переключает видимость секций
- [ ] Список заданий загружается при открытии вкладки
- [ ] Список обновляется каждые 30 секунд
- [ ] Фильтрация по ID работает
- [ ] Фильтрация по периоду работает
- [ ] Кнопка "Удалить" удаляет задание
- [ ] Кнопка "Скачать" скачивает все файлы задания

---

## 8. Возможные расширения

- Пагинация (если заданий много)
- Экспорт списка в CSV
- Сортировка по дате/размеру
- Индикаторы прогресса для длинных заданий

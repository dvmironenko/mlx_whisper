# File Size in Job Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Отображать размер каждого файла рядом с именем в карточках заданий на веб-интерфейсе.

**Architecture:** Бэкенд возвращает массив объектов `{name, size}` вместо строк. Фронтенд парсит объект, извлекает имя и размер, рендерит размер через существующую функцию `formatFileSize()` и CSS-класс `.file-size`. Фронтенд сохраняет обратную совместимость через `typeof f === 'string'`.

**Tech Stack:** Python 3, FastAPI, vanilla JS (no framework), Jinja2 templates

---

## Структура файлов

| Файл | Действие | Описание |
|------|----------|----------|
| `src/services/transcription_service.py:118-119` | Modify | `get_job()`: возвращать `{name, size}` вместо строк |
| `src/services/transcription_service.py:134-138` | Modify | `list_jobs()`: аналогично |
| `src/services/job_manager.py:114-133` | Modify | `list_all()` orphaned: строить объекты `{name, size}` |
| `src/templates/index.html:807-868` | Modify | `createJobCard()`: парсить объект, рендерить размер |

**Повторное использование:**
- `formatFileSize(bytes)` — [index.html:615](src/templates/index.html#L615)
- `.file-size` CSS — [new_style.css:1271](src/static/new_style.css#L1271)

---

### Task 1: Обновить `get_job()` в `transcription_service.py`

**Files:**
- Modify: `src/services/transcription_service.py:118-119`

- [ ] **Шаг 1: Заменить `os.listdir()` на список объектов `{name, size}`**

Заменить строку 119:

```python
# Было:
result["files"] = [f for f in os.listdir(job_dir) if os.path.isfile(os.path.join(job_dir, f))]

# Стало:
raw_files = [f for f in os.listdir(job_dir) if os.path.isfile(os.path.join(job_dir, f))]
result["files"] = [
    {"name": fn, "size": os.path.getsize(os.path.join(job_dir, fn))}
    for fn in raw_files
]
```

- [ ] **Шаг 2: Закоммитить**

```bash
git add src/services/transcription_service.py
git commit -m "feat: return {name, size} objects for job files in get_job()"
```

---

### Task 2: Обновить `list_jobs()` в `transcription_service.py`

**Files:**
- Modify: `src/services/transcription_service.py:134-138`

- [ ] **Шаг 1: Заменить список строк на объекты `{name, size}`**

Заменить строки 134-138:

```python
# Было:
if _os.path.isdir(job_dir) and "files" not in job:
    job["files"] = [
        f for f in _os.listdir(job_dir)
        if _os.path.isfile(_os.path.join(job_dir, f))
    ]

# Стало:
if _os.path.isdir(job_dir):
    current_files = job.get("files", [])
    if current_files and isinstance(current_files[0], str):
        # Rebuild string list with sizes
        job["files"] = [
            {"name": fn, "size": _os.path.getsize(_os.path.join(job_dir, fn))}
            for fn in current_files
        ]
    elif not current_files:
        job["files"] = [
            {"name": fn, "size": _os.path.getsize(_os.path.join(job_dir, fn))}
            for fn in _os.listdir(job_dir)
            if _os.path.isfile(_os.path.join(job_dir, fn))
        ]
```

Обработка двух случаев:
- `current_files` — строки (старый формат из orphaned): пересобираем с размерами
- `current_files` пуст: собираем с нуля из директории

- [ ] **Шаг 2: Закоммитить**

```bash
git add src/services/transcription_service.py
git commit -m "feat: return {name, size} objects for job files in list_jobs()"
```

---

### Task 3: Обновить `list_all()` в `job_manager.py`

**Files:**
- Modify: `src/services/job_manager.py:114-133`

- [ ] **Шаг 1: Заменить `job_dir_files` на объекты `{name, size}` для orphaned директорий**

Заменить строку 132:

```python
# Было:
"files": job_dir_files,

# Стало:
"files": [
    {"name": fn, "size": os.path.getsize(os.path.join(job_dir, fn))}
    for fn in job_dir_files
],
```

- [ ] **Шаг 2: Закоммитить**

```bash
git add src/services/job_manager.py
git commit -m "feat: return {name, size} objects for orphaned job files"
```

---

### Task 4: Обновить `createJobCard()` в `index.html` — парсинг и рендер

**Files:**
- Modify: `src/templates/index.html:807-868`

- [ ] **Шаг 1: Извлечь `fileName` и `fileSize` из объекта/строки, рендерить размер**

Заменить строки 807-819:

```javascript
// Было (строка 807):
job.files.forEach(f => {
    const wrapper = document.createElement('div');
    wrapper.className = 'result-file-row';

    const tag = document.createElement('span');
    tag.className = 'result-file-tag';
    const ext = f.split('.').pop().toLowerCase();
    let icon = 'fa-file';
    if (ext === 'txt') icon = 'fa-file-alt';
    else if (ext === 'json') icon = 'fa-file-code';
    else if (['wav','mp3','flac','m4a','aac','ogg'].includes(ext)) icon = 'fa-file-audio';
    tag.innerHTML = `<i class="fas ${icon}"></i> ${escapeHtml(f)}`;
    wrapper.appendChild(tag);

// Стало:
job.files.forEach(f => {
    const wrapper = document.createElement('div');
    wrapper.className = 'result-file-row';

    const tag = document.createElement('span');
    tag.className = 'result-file-tag';
    const fileName = typeof f === 'string' ? f : f.name;
    const fileSize = typeof f === 'object' && f.size !== undefined ? f.size : 0;
    const ext = fileName.split('.').pop().toLowerCase();
    let icon = 'fa-file';
    if (ext === 'txt') icon = 'fa-file-alt';
    else if (ext === 'json') icon = 'fa-file-code';
    else if (['wav','mp3','flac','m4a','aac','ogg'].includes(ext)) icon = 'fa-file-audio';
    tag.innerHTML = `<i class="fas ${icon}"></i> ${escapeHtml(fileName)} <span class="file-size">${formatFileSize(fileSize)}</span>`;
    wrapper.appendChild(tag);
```

Ключевые изменения:
- `fileName` — извлекаем имя из строки или объекта
- `fileSize` — извлекаем размер из объекта (0 по умолчанию для обратной совместимости)
- Размер рендерится через `<span class="file-size">formatFileSize(fileSize)</span>`
- Дальнейшие `f` заменяем на `fileName`

- [ ] **Шаг 2: Заменить все ссылки на `f` на `fileName` в кнопках**

Заменить строку 831:
```javascript
// Было:
viewBtn.onclick = () => viewFileContent(job.job_id, f);
// Стало:
viewBtn.onclick = () => viewFileContent(job.job_id, fileName);
```

Заменить строку 840:
```javascript
// Было:
window.open(`/api/v1/jobs/${encodeURIComponent(job.job_id)}/files/${encodeURIComponent(f)}/download`, '_blank');
// Стало:
window.open(`/api/v1/jobs/${encodeURIComponent(job.job_id)}/files/${encodeURIComponent(fileName)}/download`, '_blank');
```

Заменить строку 849:
```javascript
// Было:
const m = createConfirmModal('Удалить файл?', 'Вы уверены, что хотите удалить файл "' + f + '"?', async () => {
    try {
        await fetch(`/api/v1/jobs/${encodeURIComponent(job.job_id)}/files/${encodeURIComponent(f)}`, { method: 'DELETE' });
// Стало:
const m = createConfirmModal('Удалить файл?', 'Вы уверены, что хотите удалить файл "' + fileName + '"?', async () => {
    try {
        await fetch(`/api/v1/jobs/${encodeURIComponent(job.job_id)}/files/${encodeURIComponent(fileName)}`, { method: 'DELETE' });
```

- [ ] **Шаг 3: Закоммитить**

```bash
git add src/templates/index.html
git commit -m "feat: display file size next to file name in job cards"
```

---

## Верификация

1. Запустить приложение: `source .venv/bin/activate && python src/main.py`
2. Открыть веб-интерфейс, перейти к завершенным заданиям
3. В карточке задания рядом с каждым файлом должен отображаться размер:
   ```
   📄 transcription.txt 1.23 КБ    [👁️] [⬇️] [🗑️]
   📄 segments.json 4.56 КБ        [👁️] [⬇️] [🗑️]
   ```
4. Проверить кнопки (просмотр, скачивание, удаление) — все должны работать
5. Проверить разные форматы: маленький файл (Б), средний (КБ), большой (МБ)

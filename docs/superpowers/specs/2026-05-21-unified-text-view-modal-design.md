# Дизайн: Унифицированное модальное окно просмотра текста

## Контекст

На странице заданий ([src/templates/index.html](src/templates/index.html)) используются два модальных окна для просмотра текстовых данных:

1. **Reports View Modal** — [index.html:96-119](src/templates/index.html#L96-L119), [index.html:122-203](src/templates/index.html#L122-L203). Открывается по клику на бейдж отчёта. Загружает содержимое файла через `GET /api/v1/files/{filename}/content`, отображает в `<pre><code>`.
2. **Result Modal** — [index.html:1141-1213](src/templates/index.html#L1141-L1213). Открывается по клику на кнопку «Результат». Загружает результат транскрипции через `GET /api/v1/jobs/{jobId}`, отображает текст с таймкодами.

Оба окна решают одну задачу — показать текст пользователю, но реализованы раздельно с разными CSS-классами и логикой.

**Решение:** объединить в одну функцию `showTextView(title, content)`.

## Архитектура

```
Вызывающий код (index.html)
  ├── fetch('/api/v1/files/.../content') → text → showTextView('Отчёт', text)
  └── fetch('/api/v1/jobs/{id}') → job.text → showTextView('Результат', text)

showTextView(title, content)
  ├── Закрывает текущее окно (если открыто)
  ├── Создаёт: modal-overlay > modal-content > header + body + footer
  ├── Заголовок → modal-header (title)
  ├── Контент → modal-body (pre > code, textContent)
  ├── Footer → кнопки «Копировать» и «Закрыть»
  └── Закрытие: overlay click, close button, ESC
```

## Функция `showTextView`

**Файл:** `src/templates/index.html`

```javascript
function showTextView(title, content) {
    // 1. Закрыть текущее окно, если открыто
    closeModal();

    // 2. Создать DOM-структуру (createElement, без innerHTML)
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'modal-title');

    const contentDiv = document.createElement('div');
    contentDiv.className = 'modal-content';

    // Header
    const header = document.createElement('div');
    header.className = 'modal-header';
    const titleWrapper = document.createElement('div');
    titleWrapper.className = 'modal-title-wrapper';
    const titleIcon = document.createElement('i');
    titleIcon.className = 'fas fa-file-alt';
    titleWrapper.appendChild(titleIcon);
    const titleText = document.createElement('h3');
    titleText.id = 'modal-title';
    titleText.className = 'modal-title';
    titleText.textContent = title;
    titleWrapper.appendChild(titleText);
    header.appendChild(titleWrapper);
    const closeBtn = document.createElement('button');
    closeBtn.className = 'modal-close-btn';
    closeBtn.setAttribute('aria-label', 'Закрыть');
    closeBtn.innerHTML = '<i class="fas fa-times"></i>';
    closeBtn.onclick = closeModal;
    header.appendChild(closeBtn);
    contentDiv.appendChild(header);

    // Body
    const body = document.createElement('div');
    body.className = 'modal-body';
    const pre = document.createElement('pre');
    const code = document.createElement('code');
    code.textContent = content;
    pre.appendChild(code);
    body.appendChild(pre);
    contentDiv.appendChild(body);

    // Footer
    const footer = document.createElement('div');
    footer.className = 'modal-footer';
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn-modal-copy';
    copyBtn.type = 'button';
    copyBtn.textContent = 'Копировать';
    copyBtn.onclick = (e) => { e.stopPropagation(); copyToClipboard(content); };
    footer.appendChild(copyBtn);
    const closeFooterBtn = document.createElement('button');
    closeFooterBtn.className = 'btn-modal-close';
    closeFooterBtn.textContent = 'Закрыть';
    closeFooterBtn.onclick = closeModal;
    footer.appendChild(closeFooterBtn);
    contentDiv.appendChild(footer);

    modal.appendChild(contentDiv);
    document.body.appendChild(modal);
    currentModal = modal;

    // Закрытие по клику на overlay
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    // ESC
    document.addEventListener('keydown', handleModalEscape);
}
```

## Точки вызова

### Кнопка «Результат» (было: `openResultModal`)

**Было:** [index.html:957-958](src/templates/index.html#L957-L958) → `openResultModal(job.job_id)` → fetch → `renderResultModal(data)`

**Стало:**
```javascript
v.onclick = async () => {
    try {
        const r = await fetch(`/api/v1/jobs/${encodeURIComponent(job.job_id)}`);
        const jobData = await r.json();
        showTextView(jobData.original_filename || job.job_id, jobData.text || 'Нет данных');
    } catch (e) {
        showToast('Ошибка загрузки результата');
    }
};
```

### Бейдж отчёта (было: `viewFileContent`)

**Было:** [index.html:96-119](src/templates/index.html#L96-L119) `viewFileContent(jobId, filename)` → fetch → `createModal(filename, content)`

**Стало:**
```javascript
onclick = async () => {
    try {
        const r = await fetch('/api/v1/files/' + encodeURIComponent(filename) + '/content');
        const text = await r.text();
        showTextView(filename, text);
    } catch (e) {
        alert('Ошибка загрузки: ' + e.message);
    }
};
```

## Удаление мёртвого кода

### Функции удалить

- `viewFileContent` — [index.html:96-119](src/templates/index.html#L96-L119)
- `createModal` — [index.html:122-203](src/templates/index.html#L122-L203)
- `openResultModal` — [index.html:1141-1152](src/templates/index.html#L1141-L1152)
- `renderResultModal` — [index.html:1154-1210](src/templates/index.html#L1154-L1210)
- `closeResultModal` — [index.html:1212-1214](src/templates/index.html#L1212-L1214)

### Переменные удалить

- `currentModal` — заменить на `currentResultModal` (убрать `currentModal`)
- `currentResultModal` — удалить полностью, `currentModal` — единственная переменная состояния

### CSS удалить

[src/static/new_style.css:1725-1741](src/static/new_style.css#L1725-L1741) — весь блок `/* ===== Result Modal ===== */`:
- `.result-modal`
- `.result-modal-content`
- `.result-modal-header`
- `.result-modal-header h3`
- `.result-modal-close`
- `.result-modal-body`
- `.result-text`
- `.result-files-title`
- `.result-file-list`
- `.result-file-tag`
- `.result-file-row`
- `.result-modal-footer`
- `.result-error`

### CSS оставить без изменений

- `.modal-overlay`, `.modal-content`, `.modal-header`, `.modal-body`, `.modal-footer` — общие стили
- `.btn-modal-copy`, `.btn-modal-close` — кнопки
- `.modal-confirm` — модал подтверждения удаления (не затрагивается)

## Обработка ошибок

- Сетевая ошибка при fetch — показ тоста с сообщением об ошибке (использовать существующий `showToast`)
- Пустой текст — показ «Нет данных» вместо пустого блока
- `closeModal` при `null` — уже защищена проверкой `if (currentModal)`

## Тестирование

1. Задание завершено → нажать «Результат» → окно с текстом транскрипции, кнопка «Копировать» работает
2. Сгенерировать отчёт → нажать на бейдж → окно с текстом отчёта
3. Нажать ESC → окно закрывается
4. Кликнуть на overlay → окно закрывается
5. Нажать «Копировать» → текст в буфере, кнопка показывает «Скопировано!»
6. Повторно открыть окно при уже открытом — старое закрывается, новое открывается
7. Пустой результат транскрипции — показать «Нет данных»

## Файлы для изменения

- `src/templates/index.html` — новая функция `showTextView`, обновление точек вызова, удаление мёртвого кода
- `src/static/new_style.css` — удаление CSS-блока Result Modal (строки 1725-1741)

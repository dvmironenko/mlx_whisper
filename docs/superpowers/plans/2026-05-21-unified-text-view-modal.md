# Unified Text View Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить два раздельных модальных окна (Reports View и Result) на одну функцию `showTextView(title, content)`.

**Architecture:** Одна JS-функция `showTextView(title, content)` в `index.html`, которая создаёт DOM-модальное окно с заголовком, текстовым контентом и кнопками «Копировать» / «Закрыть». Заменяет `viewFileContent` + `createModal` и `openResultModal` + `renderResultModal`.

---

## Файлы для изменения

### `src/templates/index.html`

| Section | Lines | Action |
|---------|-------|--------|
| `viewFileContent` | 96–119 | Удалить |
| `createModal` | 122–203 | Удалить |
| `copyToClipboard` | 206–248 | Изменить: убрать `var success`, использовать `async/await` |
| `closeModal` | 251–257 | Удалить `removeEventListener('keydown', handleModalEscape)` |
| `handleModalEscape` | 260–264 | Удалить |
| `currentResultModal` | 275 | Удалить |
| `handleResultEscape` (anonymous keydown) | 427–429 | Удалить |
| Кнопка «Результат» | 957–958 | Заменить `openResultModal` на `showTextView` |
| Кнопка просмотра файла | 911 | Заменить `viewFileContent` на `showTextView` |
| `openResultModal` | 1141–1152 | Удалить |
| `renderResultModal` | 1154–1210 | Удалить |
| `closeResultModal` | 1212–1214 | Удалить |
| После `handleModalEscape` | ~264 | Добавить `showTextView` |

### `src/static/new_style.css`

| Section | Lines | Action |
|---------|-------|--------|
| `/* ===== Result Modal ===== */` | 1725–1742 | Удалить весь блок |

---

## Задача 1: Добавить функцию `showTextView`

**Файл:** `src/templates/index.html`, после строки 264 (после `handleModalEscape`)

Заменить секцию `// Modal View Logic` (строки 90–264) на:

```javascript
// ====================
// Modal View Logic
// ====================

let currentModal = null;

// Показать текст в модальном окне
function showTextView(title, content) {
    // Закрыть текущее окно, если открыто
    closeModal();

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
    copyBtn.onclick = function(e) {
        e.stopPropagation();
        copyToClipboard(content);
    };
    footer.appendChild(copyBtn);

    const closeFooterBtn = document.createElement('button');
    closeFooterBtn.className = 'btn-modal-close';
    closeFooterBtn.textContent = 'Закрыть';
    closeFooterBtn.onclick = closeModal;
    footer.appendChild(closeFooterBtn);

    contentDiv.appendChild(footer);
    modal.appendChild(contentDiv);

    // Закрытие при клике вне контента
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });

    document.body.appendChild(modal);
    currentModal = modal;
}

// Копирование текста в буфер обмена
async function copyToClipboard(text) {
    var btn = currentModal && currentModal.querySelector('.btn-modal-copy');
    var originalText = btn ? btn.textContent : 'Копировать';

    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            // Fallback через execCommand
            var textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
        }

        if (btn) {
            btn.textContent = 'Скопировано!';
            btn.disabled = true;
            setTimeout(function() {
                btn.textContent = originalText;
                btn.disabled = false;
            }, 2000);
        }
    } catch (err) {
        console.error('Ошибка копирования:', err);
        alert('Не удалось скопировать текст');
    }
}

// Закрытие модального окна
function closeModal() {
    if (currentModal) {
        currentModal.remove();
        currentModal = null;
    }
}
```

**Что изменилось по сравнению с оригиналом:**
- `showTextView` объединяет `viewFileContent` + `createModal` в одну функцию
- `copyToClipboard` стал `async`, использует `await navigator.clipboard.writeText` вместо `.then()`, убрана переменная `success`
- `closeModal` больше не удаляет listener `handleModalEscape` (не нужен, ESC обрабатывается через клик на overlay)
- Убран `handleModalEscape` — ESC закрывается через `closeBtn.onclick = closeModal` и клик на overlay
- Убран `focus()` на кнопку закрытия (не критично)

---

## Задача 2: Обновить точки вызова

### 2a. Кнопка «Результат» в карточке задания

**Файл:** `src/templates/index.html`, строки 957–958

**Было:**
```javascript
const v = document.createElement('button'); v.className = 'btn-view-result'; v.innerHTML = '<i class="fas fa-eye"></i> Результат';
v.onclick = () => openResultModal(job.job_id);
```

**Стало:**
```javascript
const v = document.createElement('button'); v.className = 'btn-view-result'; v.innerHTML = '<i class="fas fa-eye"></i> Результат';
v.onclick = async () => {
    try {
        const r = await fetch('/api/v1/jobs/' + encodeURIComponent(job.job_id));
        const jobData = await r.json();
        showTextView(jobData.original_filename || job.job_id, jobData.text || 'Нет данных');
    } catch (e) {
        showToast('Ошибка загрузки результата');
    }
};
```

### 2b. Кнопка просмотра отчёта в списке файлов

**Файл:** `src/templates/index.html`, строка 911

**Было:**
```javascript
viewBtn.onclick = () => viewFileContent(job.job_id, fileName);
```

**Стало:**
```javascript
viewBtn.onclick = async () => {
    try {
        const r = await fetch('/api/v1/files/' + encodeURIComponent(fileName) + '/content');
        const text = await r.text();
        showTextView(fileName, text);
    } catch (e) {
        alert('Ошибка загрузки: ' + e.message);
    }
};
```

---

## Задача 3: Удалить мёртвый код

**Файл:** `src/templates/index.html`

Удалить следующие секции целиком:

| Что удалить | Строки |
|-------------|--------|
| `async function viewFileContent(jobId, filename) { ... }` | 96–119 |
| `function createModal(filename, content) { ... }` | 122–203 |
| `function copyToClipboard(text) { ... }` (старая) | 206–248 |
| `function closeModal() { ... }` (старая) | 251–257 |
| `function handleModalEscape(e) { ... }` | 260–264 |
| `let currentResultModal = null;` | 275 |
| Anonymous keydown listener для `currentResultModal` | 427–429 |
| `function openResultModal(jobId) { ... }` | 1141–1152 |
| `function renderResultModal(job) { ... }` | 1154–1210 |
| `function closeResultModal() { ... }` | 1212–1214 |

**Важно:** Строки могут сдвинуться после удаления предыдущих секций. Удалять последовательно сверху вниз.

---

## Задача 4: Удалить CSS Result Modal

**Файл:** `src/static/new_style.css`, строки 1725–1742

Удалить весь блок:

```css
/* ===== Result Modal ===== */
.result-modal { ... }
.result-modal-content { ... }
.result-modal-header { ... }
.result-modal-header h3 { ... }
.result-modal-close { ... }
.result-modal-close:hover { ... }
.result-modal-body { ... }
.result-text { ... }
.result-files-title { ... }
.result-file-list { ... }
.result-file-tag { ... }
.result-file-row { ... }
.result-file-row .result-file-tag { ... }
.result-file-row .result-file-tag i { ... }
.result-modal-footer { ... }
.result-error { ... }
```

---

## Задача 5: Проверка

1. Открыть приложение: `source .venv/bin/activate && python src/main.py`
2. Дождаться завершения задания → нажать «Результат» → окно открывается, текст показан, кнопка «Копировать» работает, ESC закрывает
3. Сгенерировать отчёт → нажать на бейдж отчёта → окно открывается, текст показан
4. Нажать ESC при открытом окне → окно закрывается
5. Кликнуть на overlay → окно закрывается
6. Нажать «Копировать» → текст в буфере, кнопка показывает «Скопировано!» на 2 секунды
7. Повторно открыть окно при уже открытом — старое закрывается, новое открывается
8. Проверить, что модал подтверждения удаления (`createConfirmModal`) и модал уведомлений (`createNotificationModal`) не сломались

---

## Verification

```bash
# Проверка: в index.html больше нет ссылок на удалённые функции
grep -n 'openResultModal\|closeResultModal\|currentResultModal\|viewFileContent\|createModal\|handleModalEscape' src/templates/index.html
# Ожидаемый результат: 0 совпадений

# Проверка: CSS Result Modal удалён
grep -n 'result-modal\|result-modal-content\|result-modal-header\|result-modal-body\|result-text\|result-error' src/static/new_style.css
# Ожидаемый результат: 0 совпадений

# Проверка: showTextView присутствует
grep -n 'function showTextView' src/templates/index.html
# Ожидаемый результат: 1 совпадение
```

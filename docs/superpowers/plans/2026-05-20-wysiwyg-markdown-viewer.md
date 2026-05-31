# WYSIWYG Markdown Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Автоматический рендеринг Markdown → HTML в модальном окне просмотра файлов `.md` и `.txt` через `marked.js`.

**Architecture:** Добавляем `marked.js` как статический файл. Модифицируем `viewFileContent()` и `createModal()` в `index.html` для детектирования markdown-файлов и рендеринга через `marked.parse()`. Добавляем CSS-стили для `.rendered-md` в `new_style.css`. API без изменений.

**Tech Stack:** marked.js v14.x (UMD), vanilla JS, CSS custom properties

---

## Файлы для изменений

| Файл | Действие | Описание |
|------|----------|----------|
| `src/static/marked.min.js` | **Создать** | Библиотека marked.js UMD v14.1.3 |
| `src/templates/index.html:88` | **Модифицировать** | Добавить `<script src="/static/marked.min.js">` |
| `src/templates/index.html:96-119` | **Модифицировать** | `viewFileContent()` — детектирование markdown, рендеринг |
| `src/templates/index.html:122-203` | **Модифицировать** | `createModal()` — поддержка `isMarkdown` флага |
| `src/static/new_style.css` | **Модифицировать** | Добавить стили `.rendered-md` и дочерних элементов |

---

### Task 1: Добавить marked.js как статический файл

**Files:**
- Create: `src/static/marked.min.js`

- [ ] **Step 1: Скачать marked.js UMD**

Скачать последнюю стабильную версию marked.js (v14.1.3 на момент написания плана) с CDN:

```bash
curl -sL https://cdn.jsdelivr.net/npm/marked/marked.min.js -o src/static/marked.min.js
```

Проверить размер файла (должен быть ~70-80 КБ):

```bash
wc -c src/static/marked.min.js
```

Ожидаемый вывод: `~75000` (75 КБ).

- [ ] **Step 2: Коммит**

```bash
git add src/static/marked.min.js
git commit -m "feat: add marked.js for markdown rendering in file viewer"
```

---

### Task 2: Подключить marked.js в index.html

**Files:**
- Modify: `src/templates/index.html:88`

- [ ] **Step 1: Добавить скрипт marked.js перед Inline Script**

В `src/templates/index.html` найти строку 87 (`</script>` закрывающий тег inline script) и перед строкой 88 (`// ====================`) добавить:

```html
    <script src="/static/marked.min.js"></script>
```

Контекст (строки 82-90):
```html
    <script>
        // ====================
        // Jobs List Logic
        // ====================

        let jobsList = [];

        // ====================
        // Modal View Logic
        // ====================
```

Должно стать:
```html
    <script>
        // ====================
        // Jobs List Logic
        // ====================

        let jobsList = [];

        // ====================
        // Modal View Logic
        // ====================

    </script>

    <script src="/static/marked.min.js"></script>

    <script>
        // ... (продолжение inline-скриптов)
```

Подождите — это неэффективно. Лучше добавить скрипт в `<head>` или перед закрывающим `</body>`. Проверим структуру файла.

Файл `index.html` имеет структуру:
- Строки 1-9: `<head>` с `<link>` стилями
- Строки 10-80: HTML body
- Строки 82-86: первый `<script>` (Jobs List Logic)
- Строки 88-264: второй `<script>` (Modal View Logic)
- Строки 266+: третий `<script>` (Delete Confirmation, polling, и т.д.)

Вместо добавления в `<head>`, добавим marked.js в начало второго скрипта (Modal View Logic), так как `viewFileContent` находится именно там.

**Реальное изменение:** В `src/templates/index.html` найти строку 88 (`// ====================`) и перед ней добавить:

```html
    <script src="/static/marked.min.js"></script>
```

То есть между закрывающим `</script>` строки 86 и комментарием строки 88.

Контекст (строки 84-92):
```html
        // Jobs List Logic
        // ====================

        let jobsList = [];

        // ====================
        // Modal View Logic
        // ====================
```

Должно стать:
```html
        // Jobs List Logic
        // ====================

        let jobsList = [];

    </script>

    <script src="/static/marked.min.js"></script>

    <script>
        // ====================
        // Modal View Logic
        // ====================
```

- [ ] **Step 2: Проверка**

Убедиться, что файл содержит `<script src="/static/marked.min.js"></script>` между двумя `<script>` тегами.

- [ ] **Step 3: Коммит**

```bash
git add src/templates/index.html
git commit -m "chore: wire marked.js into index.html"
```

---

### Task 3: Модифицировать viewFileContent для рендеринга Markdown

**Files:**
- Modify: `src/templates/index.html:96-119`

- [ ] **Step 1: Добавить детектирование и рендеринг в viewFileContent**

Заменить функцию `viewFileContent` (строки 96-119) на:

```javascript
        // Загрузка и отображение содержимого файла
        async function viewFileContent(jobId, filename) {
            try {
                const response = await fetch('/api/v1/files/' + encodeURIComponent(filename) + '/content');
                if (!response.ok) {
                    throw new Error('Failed to load file content');
                }
                const content = await response.text();

                const ext = '.' + filename.split('.').pop().toLowerCase();
                const isMarkdown = (ext === '.md' || ext === '.txt');

                // Создаем и показываем модальное окно
                currentModal = createModal(filename, content, isMarkdown);
                document.body.appendChild(currentModal);

                // Добавляем обработчик ESC
                document.addEventListener('keydown', handleModalEscape);

                // Фокус на кнопку закрытия для доступности
                const closeBtn = currentModal.querySelector('.modal-close-btn');
                if (closeBtn) closeBtn.focus();

            } catch (error) {
                console.error('Error loading file content:', error);
                alert('Ошибка загрузки содержимого файла: ' + error.message);
            }
        }
```

Ключевые изменения:
1. Извлекаем расширение файла: `const ext = '.' + filename.split('.').pop().toLowerCase()`
2. Проверяем, является ли файл markdown: `const isMarkdown = (ext === '.md' || ext === '.txt')`
3. Передаём `isMarkdown` в `createModal()`

- [ ] **Step 2: Коммит**

```bash
git add src/templates/index.html
git commit -m "feat: detect markdown files in viewFileContent"
```

---

### Task 4: Модифицировать createModal для поддержки Markdown

**Files:**
- Modify: `src/templates/index.html:122-203`

- [ ] **Step 1: Добавить параметр isMarkdown в createModal**

Заменить функцию `createModal` (строки 122-203) на:

```javascript
        // Создание HTML модального окна (без innerHTML для безопасности)
        function createModal(filename, content, isMarkdown) {
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.setAttribute('role', 'dialog');
            modal.setAttribute('aria-modal', 'true');
            modal.setAttribute('aria-labelledby', 'modal-title');

            const contentDiv = document.createElement('div');
            contentDiv.className = 'modal-content';

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
            titleText.textContent = filename;
            titleWrapper.appendChild(titleText);

            header.appendChild(titleWrapper);

            const closeBtn = document.createElement('button');
            closeBtn.className = 'modal-close-btn';
            closeBtn.setAttribute('aria-label', 'Закрыть');
            closeBtn.innerHTML = '<i class="fas fa-times"></i>';
            closeBtn.addEventListener('click', closeModal);
            header.appendChild(closeBtn);

            contentDiv.appendChild(header);

            const body = document.createElement('div');
            body.className = 'modal-body';

            if (isMarkdown && typeof marked !== 'undefined') {
                // Рендерим Markdown в HTML
                const renderedDiv = document.createElement('div');
                renderedDiv.className = 'rendered-md';
                renderedDiv.setAttribute('role', 'region');
                renderedDiv.setAttribute('aria-label', 'Отформатированное содержимое файла ' + filename);
                renderedDiv.innerHTML = marked.parse(content);
                body.appendChild(renderedDiv);
            } else {
                // Raw text display (existing behavior)
                const pre = document.createElement('pre');
                pre.setAttribute('role', 'region');
                pre.setAttribute('aria-label', 'Содержимое файла ' + filename);

                const code = document.createElement('code');
                code.textContent = content;
                pre.appendChild(code);
                body.appendChild(pre);
            }

            contentDiv.appendChild(body);

            const footer = document.createElement('div');
            footer.className = 'modal-footer';

            const copyBtn = document.createElement('button');
            copyBtn.className = 'btn-modal-copy';
            copyBtn.type = 'button';
            copyBtn.textContent = 'Копировать';
            copyBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                copyToClipboard(content);
            });
            footer.appendChild(copyBtn);

            const closeFooterBtn = document.createElement('button');
            closeFooterBtn.className = 'btn-modal-close';
            closeFooterBtn.textContent = 'Закрыть';
            closeFooterBtn.addEventListener('click', closeModal);
            footer.appendChild(closeFooterBtn);

            contentDiv.appendChild(footer);
            modal.appendChild(contentDiv);

            // Закрытие при клике вне контента
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    closeModal();
                }
            });

            return modal;
        }
```

Ключевые изменения:
1. Добавлен параметр `isMarkdown` (default `undefined` = false)
2. `if (isMarkdown && typeof marked !== 'undefined')` — рендерим markdown через `marked.parse(content)`
3. `else` — сохраняем старое поведение с `<pre><code>`
4. Копирование всегда копирует исходный `content` (markdown), а не HTML-вывод

- [ ] **Step 2: Коммит**

```bash
git add src/templates/index.html
git commit -m "feat: add markdown rendering to createModal"
```

---

### Task 5: Добавить CSS-стили для rendered-md

**Files:**
- Modify: `src/static/new_style.css`

- [ ] **Step 1: Добавить стили .rendered-md в конец CSS**

В конец файла `src/static/new_style.css` добавить:

```css
/* =============================================
   Rendered Markdown Viewer Styles
   ============================================= */

.rendered-md {
    color: var(--text-primary);
    line-height: 1.7;
    font-size: 0.95rem;
    word-wrap: break-word;
    overflow-wrap: break-word;
}

.rendered-md h1,
.rendered-md h2,
.rendered-md h3,
.rendered-md h4,
.rendered-md h5,
.rendered-md h6 {
    margin-top: 24px;
    margin-bottom: 12px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.3;
}

.rendered-md h1 { font-size: 1.75rem; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; }
.rendered-md h2 { font-size: 1.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 6px; }
.rendered-md h3 { font-size: 1.25rem; }
.rendered-md h4 { font-size: 1.1rem; }
.rendered-md h5 { font-size: 1rem; }
.rendered-md h6 { font-size: 0.9rem; color: var(--text-secondary); }

.rendered-md p {
    margin: 0 0 16px;
    color: var(--text-primary);
}

.rendered-md p:last-child {
    margin-bottom: 0;
}

.rendered-md ul,
.rendered-md ol {
    margin: 0 0 16px;
    padding-left: 28px;
}

.rendered-md li {
    margin-bottom: 6px;
}

.rendered-md li > ul,
.rendered-md li > ol {
    margin-top: 6px;
    margin-bottom: 0;
}

.rendered-md strong {
    font-weight: 600;
    color: var(--text-primary);
}

.rendered-md em {
    font-style: italic;
}

.rendered-md del {
    text-decoration: line-through;
    color: var(--text-secondary);
}

.rendered-md code {
    background-color: var(--background-dark);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Source Sans 3', 'Consolas', monospace;
    font-size: 0.88em;
    color: var(--error-color);
}

.rendered-md pre {
    margin: 0 0 16px;
    padding: 14px;
    background-color: var(--background-dark);
    border-radius: 8px;
    overflow-x: auto;
    border: 1px solid var(--border-color);
}

.rendered-md pre code {
    background: none;
    padding: 0;
    color: var(--text-primary);
    font-size: 0.88rem;
}

.rendered-md blockquote {
    margin: 0 0 16px;
    padding: 8px 16px;
    border-left: 4px solid var(--accent-color);
    background-color: var(--background-light);
    color: var(--text-secondary);
    border-radius: 0 6px 6px 0;
}

.rendered-md hr {
    border: none;
    border-top: 1px solid var(--border-color);
    margin: 24px 0;
}

.rendered-md a {
    color: var(--accent-color);
    text-decoration: none;
}

.rendered-md a:hover {
    text-decoration: underline;
}

.rendered-md table {
    width: 100%;
    margin: 0 0 16px;
    border-collapse: collapse;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
}

.rendered-md th,
.rendered-md td {
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.rendered-md th {
    background-color: var(--background-dark);
    font-weight: 600;
}

.rendered-md img {
    max-width: 100%;
    height: auto;
    border-radius: 6px;
    margin: 8px 0;
}
```

Все стили используют CSS-переменные из тем (light/dark), поэтому автоматически адаптируются.

- [ ] **Step 2: Проверка**

Убедиться, что:
- Все селекторы используют `var(--text-primary)`, `var(--background-dark)`, `var(--accent-color)`, `var(--border-color)`, `var(--text-secondary)`, `var(--error-color)`, `var(--background-light)`
- Нет hardcoded цветов (кроме специфичных для элементов)
- Стили идут после всех существующих правил

- [ ] **Step 3: Коммит**

```bash
git add src/static/new_style.css
git commit -m "feat: add CSS styles for rendered markdown viewer"
```

---

### Task 6: Финальная проверка

**Files:**
- All modified files

- [ ] **Step 1: Проверить все изменения**

```bash
git diff --stat
```

Ожидаемый вывод:
```
 src/static/marked.min.js          | 1 +
 src/static/new_style.css          | X added
 src/templates/index.html          | Y changed
```

- [ ] **Step 2: Проверить, что marked.js загружается**

Открыть `http://localhost:8000/` в браузере, открыть DevTools → Network, убедиться что `/static/marked.min.js` загружается с кодом 200.

- [ ] **Step 3: Проверить рендеринг**

1. Найти задание с `.md` или `.txt` файлом
2. Нажать кнопку просмотра (глаз)
3. Убедиться, что markdown отрендерен: заголовки крупные, списки с маркерами, жирный текст жирный
4. Переключить тему (светлая/тёмная) — стили должны адаптироваться
5. Нажать «Копировать» — в буфере исходный markdown

- [ ] **Step 4: Проверить `.json` файлы**

1. Найти `.json` файл
2. Нажать просмотр — должен отображаться как raw text (без изменений)

- [ ] **Step 5: Финальный коммит**

```bash
git add -A
git commit -m "feat: add WYSIWYG markdown viewer to file content modal"
```

---

## Self-Review

### 1. Spec coverage
- [x] `marked.js` UMD — Task 1
- [x] Подключение скрипта — Task 2
- [x] Детектирование `.md` и `.txt` — Task 3
- [x] `marked.parse()` рендеринг — Task 4
- [x] CSS-стили `.rendered-md` — Task 5
- [x] Копирование исходного markdown — Task 4 (copyToClipboard(content))
- [x] Dark/light тема — CSS использует CSS-переменные

### 2. Placeholder scan
- Нет "TBD", "TODO", "implement later"
- Все строки кода конкретные
- Все команды с expected output
- Нет "Similar to Task N" — каждый task самодостаточен

### 3. Type consistency
- Функция `createModal(filename, content, isMarkdown)` — сигнатура определена в Task 4, используется в Task 3
- CSS-переменные: `var(--text-primary)`, `var(--background-dark)`, `var(--accent-color)`, `var(--border-color)`, `var(--text-secondary)`, `var(--error-color)`, `var(--background-light)` — все определены в `new_style.css`
- `marked.parse()` — стандартный API marked.js

### 4. Scope
- Изменения только в `index.html`, `new_style.css`, новый `marked.min.js`
- API без изменений
- Остальные страницы без изменений

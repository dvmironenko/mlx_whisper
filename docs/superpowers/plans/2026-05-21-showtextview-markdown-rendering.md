# showTextView: Markdown-рендеринг Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить plain-text рендеринг на Markdown-рендеринг в `showTextView` — весь контент (результаты транскрипции, `.md`/`.txt` файлы) будет отображаться как форматированный HTML.

**Architecture:** Встроить `marked.min.js` в `src/static/`, подключить через `<script>` в `<head>`, заменить `textContent` на `marked.parse()` в `showTextView`, добавить CSS-стили для HTML-элементов markdown внутри `.modal-body`.

**Tech Stack:** Vanilla JS, marked.js 14.1.2, CSS custom properties (theme variables)

---

### Task 1: Скачать и разместить marked.min.js

**Files:**
- Create: `src/static/marked.min.js`

- [ ] **Step 1: Скачать marked.min.js v14.1.2**

```bash
curl -sL "https://unpkg.com/marked@14.1.2/marked.min.js" -o src/static/marked.min.js
```

Ожидаемый размер: ~36 КБ. Проверить: `wc -c src/static/marked.min.js` — должно быть ~36489.

- [ ] **Step 2: Проверить, что файл не пустой и начинается с комментария**

```bash
head -1 src/static/marked.min.js
```

Ожидаемый вывод: `/**`

- [ ] **Step 3: Закоммитить**

```bash
git add src/static/marked.min.js
git commit -m "chore: add marked.js v14.1.2 for markdown rendering"
```

### Task 2: Подключить marked.js и изменить showTextView

**Files:**
- Modify: `src/templates/index.html:8` (добавить `<script>`)
- Modify: `src/templates/index.html:137-145` (заменить body-секцию showTextView)

- [ ] **Step 1: Добавить `<script>` в `<head>`**

В [index.html:8](src/templates/index.html#L8) после подключения Font Awesome добавить:

```html
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="/static/marked.min.js"></script>
```

- [ ] **Step 2: Заменить body-секцию showTextView**

В [index.html:137-145](src/templates/index.html#L137-L145) заменить:

```js
            // Body
            const body = document.createElement('div');
            body.className = 'modal-body';

            const pre = document.createElement('pre');
            const code = document.createElement('code');
            code.textContent = content;
            pre.appendChild(code);
            body.appendChild(pre);
```

на:

```js
            // Body
            const body = document.createElement('div');
            body.className = 'modal-body';
            body.innerHTML = marked.parse(content);
```

- [ ] **Step 3: Закоммитить**

```bash
git add src/templates/index.html
git commit -m "feat: render markdown content in showTextView modal"
```

### Task 3: Добавить CSS-стили для markdown-элементов

**Files:**
- Modify: `src/static/new_style.css:1476-1502` (обновить `.modal-body` и добавить стили)

- [ ] **Step 1: Обновить `.modal-body` и добавить markdown-стили**

В [new_style.css:1476-1502](src/static/new_style.css#L1476-L1502) заменить блок `.modal-body` { ... } `.modal-body pre` { ... } `.modal-body code` { ... } на:

```css
.modal-body {
    padding: 20px;
    overflow-x: hidden;
    overflow-y: auto;
    font-family: 'Source Sans 3', monospace;
    font-size: 0.9rem;
    word-wrap: break-word;
    word-break: break-word;
    line-height: 1.6;
    color: var(--text-primary);
}

.modal-body h1,
.modal-body h2,
.modal-body h3,
.modal-body h4,
.modal-body h5,
.modal-body h6 {
    margin-top: 1.2em;
    margin-bottom: 0.5em;
    font-weight: 600;
    color: var(--primary-color);
    line-height: 1.3;
}

.modal-body h1 { font-size: 1.5rem; }
.modal-body h2 { font-size: 1.3rem; }
.modal-body h3 { font-size: 1.15rem; }
.modal-body h4 { font-size: 1.05rem; }
.modal-body h5,
.modal-body h6 { font-size: 0.95rem; }

.modal-body p {
    margin-top: 0;
    margin-bottom: 0.8em;
}

.modal-body p:last-child {
    margin-bottom: 0;
}

.modal-body ul,
.modal-body ol {
    margin-top: 0.5em;
    margin-bottom: 0.8em;
    padding-left: 1.5em;
}

.modal-body li {
    margin-bottom: 0.3em;
}

.modal-body li > ul,
.modal-body li > ol {
    margin-top: 0.3em;
    margin-bottom: 0;
}

.modal-body code {
    font-family: 'Source Sans 3', monospace;
    background-color: var(--background-dark);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85em;
    color: var(--text-primary);
}

.modal-body pre {
    margin: 0.8em 0;
    padding: 12px 16px;
    background-color: var(--background-dark);
    border-radius: 6px;
    overflow-x: auto;
    font-size: 0.85rem;
    line-height: 1.5;
}

.modal-body pre code {
    display: block;
    background: none;
    padding: 0;
    border-radius: 0;
    font-size: inherit;
    color: inherit;
}

.modal-body blockquote {
    margin: 0.8em 0;
    padding: 0.5em 1em;
    border-left: 3px solid var(--border-color);
    color: var(--text-secondary);
    background-color: var(--background-dark);
    border-radius: 0 4px 4px 0;
}

.modal-body blockquote p:last-child {
    margin-bottom: 0;
}

.modal-body a {
    color: var(--primary-color);
    text-decoration: underline;
}

.modal-body a:hover {
    opacity: 0.8;
}

.modal-body strong {
    font-weight: 600;
    color: var(--text-primary);
}

.modal-body em {
    font-style: italic;
    color: var(--text-primary);
}

.modal-body hr {
    margin: 1.5em 0;
    border: none;
    border-top: 1px solid var(--border-color);
}
```

- [ ] **Step 2: Закоммитить**

```bash
git add src/static/new_style.css
git commit -m "style: add markdown element styles for modal-body"
```

### Task 4: Верификация

- [ ] **Step 1: Запустить сервер**

```bash
source .venv/bin/activate && python src/main.py
```

- [ ] **Step 2: Проверить через браузер**

1. Открыть `http://localhost:8000`
2. Найти задание с результатом транскрипции
3. Нажать «Результат» — контент должен быть отрендерен как HTML
4. Проверить элементы: `**жирный**`, `*курсив*`, `# заголовок`, `- список`, `` `inline code` ``, `> цитата`, ```` ```код``` ``, `---`
5. Переключить тему (светлая/тёмная) — стили должны адаптироваться
6. Нажать «Копировать» — должен скопироваться исходный markdown-текст
7. Проверить `.md` файл — должен рендериться с форматированием

- [ ] **Step 3: Закоммитить**

```bash
git add .
git commit -m "verify: markdown rendering in showTextView modal"
```

# WYSIWYG Editor for Prompt Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить WYSIWYG-редактор markdown-промтов в страницу настроек через модальное окно.

**Architecture:** Встраиваем `@celsowm/markdown-wysiwyg` в модальное окно, создаваемое динамически. Textarea становится readonly-дисплеем. Кнопка "Редактировать" открывает модалку, кнопки "Сохранить"/"Отменить" управляют состоянием.

**Tech Stack:** Vanilla JS, `@celsowm/markdown-wysiwyg` v1.0.6, `marked.js` (CDN), Font Awesome 6.4.0 (CDN)

---

## Task 1: Извлечь файлы пакета в проект

**Files:**
- Create: `src/static/markdown-wysiwyg/editor.css`
- Create: `src/static/markdown-wysiwyg/editor.js`
- Create: `src/static/markdown-wysiwyg/marked.min.js` (CDN dependency)

- [ ] **Step 1: Установить пакет и извлечь файлы**

```bash
cd /Users/dvmironenko/dev/mlx_whisper
mkdir -p src/static/markdown-wysiwyg
npm pack @celsowm/markdown-wysiwyg@1.0.6 --pack-destination /tmp
tar -xzf /tmp/celsowm-markdown-wysiwyg-1.0.6.tgz -C /tmp
cp package/dist/editor.css src/static/markdown-wysiwyg/
cp package/dist/editor.js src/static/markdown-wysiwyg/
rm -rf package /tmp/celsowm-markdown-wysiwyg-1.0.6.tgz
```

- [ ] **Step 2: Скачать marked.min.js (CDN dependency)**

```bash
curl -sL https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js -o src/static/markdown-wysiwyg/marked.min.js
```

- [ ] **Step 3: Проверить что файлы существуют**

```bash
ls -la src/static/markdown-wysiwyg/
```

Expected: 3 файла: `editor.css`, `editor.js`, `marked.min.js`

- [ ] **Step 4: Commit**

```bash
git add src/static/markdown-wysiwyg/
git commit -m "chore: extract @celsowm/markdown-wysiwyg package to static files"
```

---

## Task 2: Добавить ссылки на ресурсы в settings.html

**Files:**
- Modify: `src/templates/settings.html`

- [ ] **Step 1: Добавить CDN marked.js и стили редактора в `<head>`**

Вставить после строки 8 (`<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">`):

```html
    <script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
    <link rel="stylesheet" href="/static/markdown-wysiwyg/editor.css">
    <script src="/static/markdown-wysiwyg/editor.js"></script>
```

- [ ] **Step 2: Commit**

```bash
git add src/templates/settings.html
git commit -m "feat: add marked.js CDN and WYSIWYG editor resources to settings.html"
```

---

## Task 3: Добавить кнопку "Редактировать"

**Files:**
- Modify: `src/templates/settings.html`

- [ ] **Step 1: Добавить кнопку после textarea промпта**

Вставить после строки 67 (закрытие `</div>` textarea промпта), перед `<div class="form-buttons">`:

```html
                    <button type="button" id="editPromptBtn" class="btn-edit-prompt">
                        <i class="fas fa-pen"></i>
                        <span>Редактировать</span>
                    </button>
```

- [ ] **Step 2: Commit**

```bash
git add src/templates/settings.html
git commit -m "feat: add edit button for prompt WYSIWYG editor"
```

---

## Task 4: Добавить CSS стили

**Files:**
- Modify: `src/static/new_style.css`

- [ ] **Step 1: Добавить стили для кнопки и контейнера модального окна**

В конец файла (или в секцию modal styles, ~line 1742):

```css
/* WYSIWYG Editor */
.btn-edit-prompt {
    background-color: var(--accent-color);
    color: white;
    padding: 8px 16px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    font-size: 0.9rem;
    font-family: 'Source Sans 3', sans-serif;
    transition: var(--transition);
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
}

.btn-edit-prompt:hover {
    opacity: 0.9;
}

.wysiwyg-modal-container {
    flex: 1;
    overflow: auto;
    min-height: 400px;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/new_style.css
git commit -m "style: add WYSIWYG editor button and modal container styles"
```

---

## Task 5: Добавить модальное окно и JS логику редактора

**Files:**
- Modify: `src/templates/settings.html`

- [ ] **Step 1: Добавить модальное окно в HTML (перед закрывающим `</div class="container">`)**

Вставить перед строкой 85 (`</div>` container):

```html
        <!-- WYSIWYG Editor Modal -->
        <div id="wysiwygModal" class="modal-overlay" style="display: none;">
            <div class="modal-content" style="max-width: 900px; max-height: 85vh;">
                <div class="modal-header">
                    <h3>Редактирование промта</h3>
                    <button type="button" class="modal-close" id="wysiwygModalClose">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="wysiwyg-editor-container" class="wysiwyg-modal-container"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" id="wysiwygSaveBtn" class="submit-button">
                        <i class="fas fa-save"></i>
                        <span>Сохранить</span>
                    </button>
                    <button type="button" id="wysiwygCancelBtn" class="btn-cancel-delete">
                        <i class="fas fa-times"></i>
                        <span>Отменить</span>
                    </button>
                </div>
            </div>
        </div>
```

- [ ] **Step 2: Добавить JS логику редактора в IIFE settings script**

Вставить после строки 118 (после `const notif = ...`), перед `let originalPrompts`:

```js
        // WYSIWYG Editor
        let editorInstance = null;

        function openPromptEditor() {
            const modal = document.getElementById('wysiwygModal');
            if (!modal) return;

            // Destroy previous instance if exists
            if (editorInstance) {
                editorInstance.destroy();
                editorInstance = null;
            }

            // Initialize editor
            editorInstance = new MarkdownWYSIWYG('wysiwyg-editor-container', {
                initialValue: textarea.value,
                showToolbar: true,
                initialMode: 'wysiwyg',
            });

            // Make textarea readonly
            textarea.readOnly = true;

            // Show modal
            modal.style.display = 'flex';
        }

        function savePromptEditor() {
            if (!editorInstance) return;

            const markdown = editorInstance.getValue();
            textarea.value = markdown;
            textarea.readOnly = false;
            textarea.dispatchEvent(new Event('input')); // triggers checkChanged()

            closePromptEditor();
        }

        function cancelPromptEditor() {
            if (!editorInstance) return;

            textarea.readOnly = false;
            closePromptEditor();
        }

        function closePromptEditor() {
            const modal = document.getElementById('wysiwygModal');
            if (modal) modal.style.display = 'none';
            if (editorInstance) {
                editorInstance.destroy();
                editorInstance = null;
            }
        }

        // Open editor on button click
        document.getElementById('editPromptBtn').addEventListener('click', openPromptEditor);

        // Save button
        document.getElementById('wysiwygSaveBtn').addEventListener('click', savePromptEditor);

        // Cancel button
        document.getElementById('wysiwygCancelBtn').addEventListener('click', cancelPromptEditor);

        // Close button (X)
        document.getElementById('wysiwygModalClose').addEventListener('click', cancelPromptEditor);

        // Close on overlay click
        document.getElementById('wysiwygModal').addEventListener('click', function(e) {
            if (e.target === this) cancelPromptEditor();
        });

        // Close on ESC
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const modal = document.getElementById('wysiwygModal');
                if (modal && modal.style.display !== 'none') {
                    cancelPromptEditor();
                }
            }
        });
```

- [ ] **Step 3: Commit**

```bash
git add src/templates/settings.html
git commit -m "feat: add WYSIWYG editor modal logic to settings page"
```

---

## Task 6: Проверка в браузере

- [ ] **Step 1: Запустить сервер**

```bash
cd /Users/dvmironenko/dev/mlx_whisper && source .venv/bin/activate && python src/main.py
```

- [ ] **Step 2: Открыть http://localhost:8000/settings в браузере**

Проверить:
1. Кнопка "Редактировать" отображается под textarea промпта
2. Клик по кнопке открывает модальное окно с WYSIWYG-редактором
3. Текущий промпт загружен в редактор
4. Редактирование текста работает (toolbar, форматирование)
5. "Сохранить" — текст возвращается в textarea, кнопка "Сохранить" формы активна
6. "Отменить" — textarea не изменён
7. ESC закрывает модалку без сохранения
8. Клик по оверлею закрывает модалку без сохранения
9. Переключение темы (light/dark) — редактор корректно отображается

---

## Verification

1. **Manual**: Открыть settings → выбрать тип отчёта → "Редактировать" → изменить промпт → "Сохранить" → проверить textarea → "Отменить" → проверить что unchanged
2. **Theme**: Проверить отображение в light и dark темах

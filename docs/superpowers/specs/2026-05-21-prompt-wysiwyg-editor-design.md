# Design: WYSIWYG Editor for Prompt Editing

## Context

The settings page (`settings.html`) uses plain `<textarea>` elements for editing report type prompts. Users need a visual WYSIWYG editor to compose markdown-formatted prompts more easily. A previous attempt used Quill (reverted in commit `f0eeb38`), so this design uses a different library.

## Package

- **npm**: `@celsowm/markdown-wysiwyg` v1.0.6
- **GitHub**: `celsowm/markdown-wysiwyg`
- **License**: MIT
- **Dependencies**: `marked.js` (external, loaded via CDN)
- **Files**: `dist/editor.css`, `dist/editor.js`
- **API**:
  - Constructor: `new MarkdownWYSIWYG(containerId, options)`
  - Methods: `getValue()`, `setValue(markdown, isInitialSetup)`, `switchToMode(mode)`, `destroy()`
  - Options: `initialValue`, `showToolbar`, `buttons`, `onUpdate`, `initialMode`, `tableGridMaxRows`, `tableGridMaxCols`

## Architecture

```
settings.html
├── <link> /static/markdown-wysiwyg/editor.css
├── <script> marked.min.js (CDN dependency)
├── <textarea id="promptTextarea"> (read-only display)
├── <button id="editPromptBtn"> Редактировать </button>
├── <!-- Modal (dynamically created) -->
│   ├── .modal-overlay
│   ├── .modal-content
│   │   ├── .modal-header "Редактирование промта"
│   │   ├── .modal-body
│   │   │   └── #wysiwyg-editor-container (MarkdownWYSIWYG instance)
│   │   └── .modal-footer
│   │       ├── Сохранить (submit-button style)
│   │       └── Отменить (secondary style)
│   └── </div>
└── <script> /static/markdown-wysiwyg/editor.js + edit logic
```

## Files to Modify

| File | Change |
|------|--------|
| `src/templates/settings.html` | Add CDN script, button, modal HTML, editor JS logic |
| `src/static/new_style.css` | Add styles for editor container + "Редактировать" button |

## Files to Create

| File | Source |
|------|--------|
| `src/static/markdown-wysiwyg/editor.css` | Extracted from `@celsowm/markdown-wysiwyg` npm package |
| `src/static/markdown-wysiwyg/editor.js` | Extracted from `@celsowm/markdown-wysiwyg` npm package |

## Behavior

### Opening the Editor

1. User clicks "Редактировать" button
2. Modal window is created (existing pattern from `uploads.html` `createModal()`)
3. `<div id="wysiwyg-editor-container">` is created inside `.modal-body`
4. `MarkdownWYSIWYG` instance is initialized:
   ```js
   const editor = new MarkdownWYSIWYG('wysiwyg-editor-container', {
       initialValue: textarea.value,
       showToolbar: true,
       initialMode: 'wysiwyg',
   });
   ```
5. `promptTextarea` becomes `readonly`

### Saving

1. User clicks "Сохранить" in modal
2. `const markdown = editor.getValue()`
3. `textarea.value = markdown`
4. `textarea.readOnly = false`
5. `textarea.dispatchEvent(new Event('input'))` → triggers `checkChanged()` → enables saveBtn if changed
6. Modal closed, `editor.destroy()`

### Canceling

1. User clicks "Отменить" in modal
2. `editor.destroy()`
3. `textarea.readOnly = false`
4. Modal closed, textarea unchanged

### Closing by ESC / overlay click

- Behavior matches existing modal pattern from `uploads.html`
- Closing without saving = cancel (textarea unchanged)

## CSS Adaptation

The editor has its own styles that may conflict with project themes. Scoped styles are added for the editor container:

```css
.wysiwyg-modal-container {
    flex: 1;
    overflow: auto;
    min-height: 400px;
}

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
```

## Data Flow

- Input/Output: Markdown format (matches existing `reports.json` format)
- No format conversion needed
- `getValue()` returns markdown string → assigned to `textarea.value`
- `textarea.value` is submitted via `POST /api/v1/settings` as-is

## Verification

1. **Manual**: Open settings page → select report type → click "Редактировать" → verify editor loads with current prompt → make changes → save → verify textarea updated → cancel → verify textarea unchanged
2. **Playwright**: Test modal open/close, save/cancel, ESC key, overlay click
3. **Theme**: Verify editor styles adapt to both light and dark themes

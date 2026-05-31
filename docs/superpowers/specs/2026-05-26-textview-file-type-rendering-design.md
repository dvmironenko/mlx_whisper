# showTextView: условный рендеринг по типу файла

## Контекст

`showTextView` в [index.html](src/templates/index.html) (строка 104) сейчас всегда рендерит контент через `marked.parse()` — Markdown-обработку. Это значит, что `.txt` файлы тоже обрабатываются как Markdown, что неверно.

## Цель

`showTextView` должен рендерить контент в зависимости от типа файла:
- `.md` → Markdown-рендеринг (`marked.parse()`)
- `.txt` → plain text с сохранением переносов строк (`white-space: pre-wrap`)

## Подход

**Factory-функция с параметром `fileType`.**

Единая функция `showTextView(title, content, fileType)` принимает `'markdown'` или `'text'`. Внутри — один условный блок для рендеринга тела модалки.

### Изменения в showTextView

**Было** ([index.html:147-148](src/templates/index.html#L147-L148)):
```js
const body = document.createElement('div');
body.className = 'modal-body';
body.innerHTML = marked.parse(content);
```

**Стало**:
```js
const body = document.createElement('div');
body.className = 'modal-body';
if (fileType === 'markdown') {
    body.innerHTML = marked.parse(content);
} else {
    body.textContent = content;
    body.style.whiteSpace = 'pre-wrap';
}
```

### Изменения на вызывающих

1. **[index.html:874-878](src/templates/index.html#L874-L878)** — кнопка просмотра файла:
```js
const ext = '.' + fileName.split('.').pop().toLowerCase();
const fileType = ext === '.md' ? 'markdown' : 'text';
// ...
showTextView(fileName, text, fileType);
```

2. **[index.html:933](src/templates/index.html#L933)** — кнопка «Результат»:
```js
showTextView(title, jobData.text || 'Нет данных', 'text');
```

### Копирование

Кнопка «Копировать» ([index.html:160-162](src/templates/index.html#L160-L162)):
- Markdown: копирует `body.innerHTML` (HTML) + `content` (исходный markdown)
- Text: копирует `body.textContent` (plain text)

### CSS

Для `fileType === 'text'` добавляется `white-space: pre-wrap` через JS (`body.style.whiteSpace`). CSS-изменений не требуется.

## Файлы для изменения

1. `src/templates/index.html` — `showTextView`, два вызова

## Верификация

1. Запустить сервер: `source .venv/bin/activate && python src/main.py`
2. Открыть задание с `.md` файлом — должен рендериться как Markdown (заголовки, жирный, списки)
3. Открыть задание с `.txt` файлом — должен рендериться как plain text (переносы строк сохранены, Markdown-синтаксис не обрабатывается)
4. Нажать «Результат» на завершённом задании — plain text, без Markdown-обработки
5. Копирование для обоих типов — корректный формат

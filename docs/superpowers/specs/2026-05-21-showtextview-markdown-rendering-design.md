# showTextView: Markdown-рендеринг

## Контекст

`showTextView` в [index.html](src/templates/index.html) (строка 96) отображает текст в модальном окне, используя `textContent` — без обработки разметки. Пользователь хочет, чтобы весь контент в модалке рендерился как Markdown.

## Цель

Заменить plain-text рендеринг на Markdown-рендеринг в `showTextView`. Весь контент (результаты транскрипции, содержимое `.md`/`.txt` файлов) будет парситься и отображаться как форматированный HTML.

## Подход

**marked.js, встраивание в проект, inline-рендеринг.**

### Зависимость

- Скачать `marked.min.js` (последняя стабильная версия) в `src/static/marked.min.js`
- Подключить через `<script src="/static/marked.min.js">` в `<head>` [index.html](src/templates/index.html)

### Изменение showTextView

**Было** ([index.html:141-144](src/templates/index.html#L141-L144)):
```js
const pre = document.createElement('pre');
const code = document.createElement('code');
code.textContent = content;
pre.appendChild(code);
body.appendChild(pre);
```

**Стало**:
```js
const rendered = marked.parse(content);
body.innerHTML = rendered;
```

### CSS

Текущие стили [new_style.css](src/static/new_style.css):
- `.modal-body` — `white-space: pre-wrap`, `monospace`, `font-size: 0.9rem`

Нужно добавить стили для HTML-элементов markdown внутри `.modal-body`:
- `h1-h6` — размер шрифта, отступы
- `p` — отступы между параграфами
- `ul, ol` — отступы, маркеры
- `li` — отступы
- `code` — inline-код: фон, моноширинный шрифт, `border-radius`
- `pre` — блок кода: фон, padding, `border-radius`, `overflow-x: auto`
- `blockquote` — левая граница, padding, цвет текста
- `a` — цвет ссылок
- `strong, em` — наследуют цвет текста
- `hr` — разделитель

### Копирование

Кнопка «Копировать» копирует исходный `content` (не HTML), изменений не требует.

### Тёмная тема

marked.js генерирует только HTML-теги. Цвета наследуются от CSS модалки через `var(--text-primary)`, `var(--card-bg)`, `var(--background-dark)`. Тёмная тема работает автоматически.

## Файлы для изменения

1. `src/static/marked.min.js` — новая зависимость (скачать)
2. `src/templates/index.html` — `<script>` в `<head>`, изменение body-секции showTextView
3. `src/static/new_style.css` — стили для markdown-элементов в `.modal-body`

## Верификация

1. Запустить сервер: `source .venv/bin/activate && python src/main.py`
2. Открыть задание с результатом транскрипции, содержащим markdown (жирный, курсив, заголовки, списки)
3. Нажать «Результат» — контент должен быть отрендерен как HTML
4. Открыть `.md` файл — должен рендериться с форматированием
5. Переключить тему — стили должны корректно адаптироваться
6. Нажать «Копировать» — должен скопироваться исходный текст (не HTML)
7. Проверить отображение всех markdown-элементов: `**bold**`, `*italic*`, `# заголовок`, `- список`, `` `inline code` ``, `> цитата`, ```` ```code block``` ```, `---`

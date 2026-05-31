# WYSIWYG Markdown Viewer — Design Doc

## Context

Текущий просмотр файлов (`viewFileContent` в `index.html`) отображает содержимое `.md` и `.txt` файлов в сыром виде через `<pre><code>`. Пользователь не видит форматирование — заголовки, списки, жирный текст отображаются как символы markdown. Необходимо добавить WYSIWYG-рендеринг markdown-контента в модальном окне просмотра файлов.

## Решение

Автоматический рендеринг markdown → HTML через `marked.js` для файлов `.md` и `.txt` в модальном окне просмотра.

## Файлы для изменений

### 1. `src/static/marked.min.js` — новый файл
- Библиотека `marked.js` (UMD, v14.x)
- CDN: https://cdn.jsdelivr.net/npm/marked/marked.min.js

### 2. `src/templates/index.html` — модификация
- Строка 88: добавить `<script src="/static/marked.min.js"></script>`
- Строка 96-119 (`viewFileContent`):
  - После получения `content`: проверить расширение файла
  - Для `.md` и `.txt`: `marked.parse(content)` → HTML
  - Вставить HTML в модалку вместо `<pre><code>`
- Строка 122-203 (`createModal`):
  - Добавить параметр `isMarkdown`
  - При `isMarkdown`: создавать `<div class="rendered-md">` вместо `<pre><code>`
  - Сохранять исходный markdown для кнопки «Копировать»

### 3. `src/static/new_style.css` — добавление CSS
- Класс `.rendered-md` и дочерние элементы:
  - `h1-h6` — заголовки с отступами
  - `p` — параграфы
  - `ul, ol` — списки
  - `li` — элементы списков
  - `strong, em, del` — форматирование текста
  - `code` — inline-код
  - `pre` — блоки кода
  - `blockquote` — цитаты
  - `hr` — горизонтальные линии
  - `a` — ссылки
  - Все стили используют существующие CSS-переменные тем

## Поддерживаемые Markdown-элементы

| Элемент | Тег | Стилизация |
|---------|-----|------------|
| Заголовки h1-h6 | `h1-h6` | Размер, отступы, цвет из переменной |
| Жирный | `strong` | font-weight: 600 |
| Курсив | `em` | font-style: italic |
| Зачёркнутый | `del` | text-decoration: line-through |
| Списки маркир. | `ul > li` | marker: "- " |
| Списки нумер. | `ol > li` | marker: "1. " |
| Inline-код | `code` | background + monospace |
| Блок кода | `pre > code` | background + padding |
| Цитаты | `blockquote` | border-left |
| Ссылки | `a` | color: primary |
| Горизонт. линия | `hr` | border-top |
| Таблицы | `table` | border-collapse |

## Что НЕ меняется

- API endpoint `/api/v1/files/{filename}/content` — без изменений
- Логика копирования — копирует исходный markdown
- Кнопки модалки — без изменений
- Существующие CSS-переменные тем — используются
- Остальные страницы — без изменений

## Копирование

Кнопка «Копировать» в модалке копирует исходный markdown-текст (не HTML-вывод), чтобы пользователь мог вставить форматированный текст.

## Верификация

1. Запустить сервер: `source .venv/bin/activate && python src/main.py`
2. Открыть `http://localhost:8000/settings`, создать тестовый файл с markdown-контентом
3. Открыть `http://localhost:8000/`, найти задание с `.md` или `.txt` файлом
4. Нажать кнопку просмотра (глаз) — контент должен отобразиться как отформатированный HTML
5. Проверить dark/light тему — стили `.rendered-md` должны адаптироваться
6. Нажать «Копировать» — в буфере должен быть исходный markdown
7. Проверить файлы `.json` — должны отображаться как raw text (без изменений)

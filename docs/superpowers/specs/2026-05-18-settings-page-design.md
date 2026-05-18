# Дизайн страницы «Настройки»

## Context

В приложении нет UI для редактирования промптов отчетов. Промпты хранятся в `config/reports.json` и могут быть изменены только ручной правкой файла. Требуется страница настроек с возможностью выбора отчета и редактирования его промпта.

## Архитектура

### Новые файлы
- `src/templates/settings.html` — шаблон страницы настроек

### Измененные файлы
- `src/main.py` — добавить маршрут `GET /settings`
- `src/api/router.py` — добавить API endpoints
- `src/templates/index.html` — добавить кнопку «Настройки» в хедер
- `src/templates/uploads.html` — добавить кнопку «Настройки» в хедер

### API endpoints

| Method | Path | Описание |
|--------|------|----------|
| `GET` | `/settings` | `TemplateResponse("settings.html")` |
| `GET` | `/api/v1/settings` | `{types: [{id, name, prompt}]}` — отчеты с промптами |
| `POST` | `/api/v1/settings` | `{report_type, prompt}` → перезапись `config/reports.json` → `{"status": "ok"}` |

### POST `/api/v1/settings` — детали
1. Парсит JSON body: `report_type` (str), `prompt` (str)
2. Загружает `config/reports.json` (UTF-8, indent=2)
3. Находит отчет с matching `id`, обновляет `prompt`
4. Записывает JSON обратно в файл
5. Возвращает `{"status": "ok"}` или `{"error": "..."}` с кодом 400/500

## UI страницы настроек

### Структура `settings.html`
- `<header class="app-header">` — название + переключатель темы
- Ссылка «Список заданий» (`href="/"`)
- `<main class="app-main">` → `<div class="upload-section">`
  - Заголовок «Настройки»
  - `<select id="reportTypeSelect" class="form-select">` — список отчетов
  - `<label>` — название выбранного отчета
  - `<textarea id="promptTextarea" class="form-input" rows="12">` — промпт
  - `<button id="saveButton" class="submit-button" disabled>Сохранить</button>`
  - Зона уведомлений

### Поведение JS
1. Загрузка: `GET /api/v1/settings` → заполнить `<select>`
2. Смена отчета: подставить `prompt` в `<textarea>`, сравнить с оригиналом, toggle кнопки
3. Клик «Сохранить»: `POST /api/v1/settings` → показать результат
4. Тема: `data-theme` (как на других страницах)

### Стили
Использовать существующие классы из `src/static/new_style.css`: `.form-select`, `.form-input`, `.submit-button`, `.upload-section`, `.app-header`, `.app-main`.

## Обработка ошибок

- `GET /api/v1/settings`: файл не найден/невалиден → `500 {"error": "..."}`
- `POST /api/v1/settings`: невалидный body / report_type не найден → `400 {"error": "..."}`
- Запись в файл не удалась → `500 {"error": "..."}`
- Клиент: ошибка POST → красное сообщение в зоне уведомлений, кнопка остаётся активной

## Тестирование

1. Открыть `/settings` — список отчетов загружен
2. Выбрать отчет — промпт подставлен
3. Изменить промпт — кнопка «Сохранить» активна
4. Нажать «Сохранить» — промпт обновлён в `config/reports.json`
5. Перезагрузить страницу — изменённый промпт загружен
6. Проверить, что `config/reports.json` валидный JSON после записи

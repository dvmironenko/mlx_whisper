# Дизайн: Выбор типа отчета для генерации

## Context

Сейчас кнопка "Отчет" в карточке задания всегда запускает генерацию с одним единственным промптом (`OPENAI_REPORT_PROMPT` из config). Нужно добавить поддержку нескольких типов отчетов с настраиваемыми промтами, хранящимися в JSON-файле. В карточке появляется dropdown выбора типа + кнопка "Отчет" (disabled, пока тип не выбран). Можно генерировать разные отчеты для одного job.

## Принятые решения

- JSON-конфиг размещается в `config/reports.json` (вне репозитория, рядом с проектом)
- Подход: отдельный `GET /api/v1/report-types` эндпоинт + расширение существующего `POST /api/v1/report/{job_id}`
- Каждый job может иметь несколько отчетов разных типов (уникальные имена файлов)

## Структура данных

Файл `config/reports.json`:
```json
[
  {
    "id": "summary",
    "name": "Сжатый пересказ",
    "prompt": "Создать сжатый пересказ разговора. Выделите основные темы, решения и следующие шаги."
  },
  {
    "id": "protocol",
    "name": "Протокол совещания",
    "prompt": "Создать протокол совещания из транскрипции. Выделить обсуждаемые темы, принятые решения и назначенные задачи."
  }
]
```

Поля: `id` (уникальный ключ), `name` (отображение в UI), `prompt` (промт для LLM).

## Бэкенд

### Новый файл: `src/services/report_types.py`
- `load_report_types()` — ищет `config/reports.json` по путям: `./config/reports.json`, `<проекту_root>/config/reports.json`
- Кэширует результат в модульном уровне переменной
- Возвращает список или пустой список с логами при ошибке чтения

### Новый эндпоинт: `GET /api/v1/report-types`
- Возвращает `{"types": [{id, name}]}` — без промптов (безопасность)
- Берёт данные из кэшированного конфига

### Изменение эндпоинта: `POST /api/v1/report/{job_id}` (router.py:538)
- Принимает optional JSON body `{"report_type": "summary"}`
- Если `report_type` не передан — падбэк на первый тип из конфига или `OPENAI_REPORT_PROMPT`
- Передаёт `report_type` в `_start_report_generation()`

### Изменение: `_start_report_generation()` (router.py:37)
- Принимает `report_type: str = None` параметр
- Загружает промт из конфига по `report_type`, фолбэк на `OPENAI_REPORT_PROMPT`
- Передаёт `report_type` в `save_report()`

### Изменение: `save_report()` (report.py:190)
- Принимает `report_type: str = None` для уникального именования файлов
- Именование: `Отчет_{type_id}_{job_id}.md` (например, `Отчет_summary_job123.md`)

### Изменение: `generate_report_via_openai_sync()` (report.py:222)
- Промт берётся из нового параметра, а не из `OPENAI_REPORT_PROMPT`

## Фронтенд

### Новый глобальный данные: `window.reportTypes = []`
- Загружается в `<script>` при загрузке страницы (DOMContentLoaded) через `GET /api/v1/report-types`

### Изменение: `createJobCard()` (index.html:708)
- В actions секции (строки 842-865): перед кнопкой "Отчет" добавляется `<select class="report-type-select">`
- Dropdown заполняется опциями из `window.reportTypes`
- Кнопка "Отчет" disabled если: статус != 'completed', или ничего не выбрано в dropdown
- При клике: берётся `select.value` (report_type id), отправляется `POST /api/v1/report/{job_id}` с телом

### Изменение: `generateReport(jobId)` (index.html:663)
- Принимает optional `reportType` параметр
- Отправляет `{report_type: reportType}` в теле запроса

### CSS: `.report-type-select` (new_style.css)
- Стилизован под существующие кнопки карточки

## Файлы для изменения

| Файл | Действие |
|------|----------|
| `src/services/report_types.py` | **Создать** — загрузка JSON-конфига |
| `src/api/router.py` | Изменить: эндпоинт `/report-types`, `/report/{job_id}`, `_start_report_generation()` |
| `src/models/report.py` | Изменить: `save_report()`, `generate_report_via_openai_sync()` — добавить report_type |
| `src/templates/index.html` | Изменить: `createJobCard()`, `generateReport()`, добавить загрузку report-types |
| `src/static/new_style.css` | Изменить: добавить стили для `.report-type-select` |
| `config/reports.json` | **Создать** — пример конфига с 2 типами отчетов |

## Верификация

1. `config/reports.json` читается при запуске сервера
2. `GET /api/v1/report-types` возвращает список типов (без промптов)
3. В UI dropdown заполняется типами, кнопка "Отчет" disabled до выбора
4. `POST /api/v1/report/{job_id}` с `report_type` запускает генерацию нужного типа
5. Файлы отчетов получают уникальные имена с type_id suffix
6. Можно сгенерировать несколько разных отчетов для одного job
7. pytest: тесты на загрузку конфига, endpoint response, fallback behavior

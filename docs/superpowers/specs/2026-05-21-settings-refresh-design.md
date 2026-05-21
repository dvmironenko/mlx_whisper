# Дизайн: Кнопка «Обновить параметры» на странице настроек

## Контекст

На странице настроек (`/settings`) пользователь может менять параметры транскрипции (initial_prompt, language, silence thresholds и т.д.) и промпты отчётов. Значения параметров читаются из `.env`, промпты — из `config/reports.json`.

**Проблема:** после изменения `.env` пользователю приходится перезапускать сервер или перезагружать страницу вручную, чтобы увидеть новые значения. Кэш `report_types.py` тоже никогда не инвалидируется.

**Решение:** кнопка «Обновить параметры», которая перечитывает `.env`, сбрасывает кэш и обновляет UI без перезагрузки страницы.

## Архитектура

```
Settings UI (settings.html)
  └── Кнопка «Обновить параметры»
        └── POST /api/v1/settings/refresh (router.py)
              ├── reload_dotenv() — перечитать .env через dotenv.load_dotenv()
              ├── clear_report_types_cache() — сбросить кэш report_types
              └── Возврат: { success: true, config: {...}, settings: {...} }
        └── JS: обновить все поля формы + показать тост
```

## Бэкенд

### Новый эндпоинт `POST /api/v1/settings/refresh`

**Файл:** `src/api/router.py`

Эндпоинт выполняет три действия:
1. Вызывает `python_dotenv.load_dotenv()` повторно для перечитывания `.env`
2. Вызывает `report_types.clear_cache()` для сброса модульного кэша
3. Возвращает свежие данные в одном ответе:

```json
{
  "success": true,
  "config": {
    "initial_prompt": "...",
    "remove_silence": true,
    "silence_threshold": -45.0,
    "silence_duration": 1.0,
    "default_language": "ru",
    "no_speech_threshold": 0.35,
    "hallucination_silence_threshold": 0.4,
    "omlx_enabled": true,
    "omlx_base_url": "...",
    "omlx_model": "...",
    "allowed_url_domains": "...",
    "max_download_size_mb": 2048,
    "download_timeout": 600
  },
  "settings": [
    {"id": "summary", "name": "Сжатый пересказ", "prompt": "..."},
    {"id": "protocol", "name": "ЭОТ: Образы и анализ", "prompt": "..."}
  ]
}
```

### Функция сброса кэша `report_types`

**Файл:** `src/services/report_types.py`

Добавить публичный метод `clear_cache()`:

```python
def clear_cache() -> None:
    """Reset the module-level cache so the next call reloads from disk."""
    global _report_types_cache
    _report_types_cache = None
```

### Перечитывание `.env`

**Файл:** `src/config.py`

Добавить публичную функцию `reload_dotenv()`:

```python
def reload_dotenv() -> None:
    """Re-read .env file and update environment variables."""
    dotenv.load_dotenv(_env_path, override=True)
```

Флаг `override=True` гарантирует, что существующие переменные будут перезаписаны значениями из `.env`.

## Фронтенд

### Кнопка

**Файл:** `src/templates/settings.html`

Добавить кнопку рядом с кнопкой «Сохранить»:

```html
<button type="button" id="refreshButton" class="btn-secondary">Обновить параметры</button>
```

### JS-логика

При клике на кнопку:
1. Отправить `POST /api/v1/settings/refresh` с CSRF-токеном
2. При успехе:
   - Обновить все поля `.env` в форме из `response.config`
   - Обновить select report types и textarea prompt из `response.settings`
   - Сохранить `originalNames` и `originalPrompts` из ответа
   - Показать зелёный тост «Параметры обновлены»
3. При ошибке:
   - Показать красный тост «Ошибка обновления: {message}»

### Тост-уведомление

Минимальный паттерн тоста:
- Зелёный (`#28a745`) для успеха
- Красный (`#dc3545`) для ошибки
- Позиция: fixed, top-right
- Авто-скрытие через 3 секунды

## Обработка ошибок

- Если `.env` недоступен — тост с ошибкой, UI не меняется
- Если `config/reports.json` недоступен — тост с ошибкой, UI не меняется
- Сетевая ошибка — тост с HTTP-статусом

## Тестирование

1. Изменить значение в `.env` → нажать «Обновить параметры» → значение в UI обновилось
2. Изменить промпт в `config/reports.json` → нажать «Обновить параметры» → промпт в UI обновился
3. Удалить `.env` → нажать кнопку → тост с ошибкой, UI не изменился
4. Нажать кнопку без изменений в `.env` → тост успеха, UI обновился

## Файлы для изменения

- `src/api/router.py` — новый эндпоинт `POST /api/v1/settings/refresh`
- `src/config.py` — новая функция `reload_dotenv()`
- `src/services/report_types.py` — новый метод `clear_cache()`
- `src/templates/settings.html` — кнопка + JS-логика
- `src/static/new_style.css` — стили тоста (если ещё нет)

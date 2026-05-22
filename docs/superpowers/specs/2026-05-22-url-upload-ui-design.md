# Дизайн: UI загрузки видео/аудио по URL

## Контекст

Бэкенд для транскрипции по URL уже реализован: endpoint `POST /api/v1/transcribe-url` в [router.py:291](src/api/router.py), утилиты скачивания в [download.py](src/utils/download.py), тесты в [test_url_download.py](tests/test_url_download.py). На странице uploads нет UI для ввода URL — функция недоступна через веб-интерфейс.

**Цель:** добавить поле ввода URL на страницу uploads, чтобы пользователи могли транскрибировать видео/аудио по ссылке без скачивания файла.

## Требования

### Функциональные
1. Текстовое поле ввода URL над существующей drag&drop зоной
2. Единая форма: один submit, JS автоматически выбирает endpoint (URL → `/transcribe-url`, файл → `/transcribe`)
3. Те же параметры формы (mechanism, language, model, transcription params) применяются к обоим способам
4. Клиентская валидация URL (не пустой, начинается с http(s)://)
5. Отображение URL в состоянии загрузки (обрезанный до ~60 символов)
6. После успеха — редирект на `/?redirect=<job_id>`
7. Ошибки отображаются через существующий toast-механизм

### Нефункциональные
1. Следовать существующим паттернам uploads.html
2. Использовать те же CSS-классы что `.form-input`
3. Поддержка тёмной/светлой темы

## Архитектура изменений

```
uploads.html
├── [НОВОЕ] URL input section (.url-input-section)
│   └── #urlInput (text, placeholder="Вставьте URL видео или аудио")
├── существующий .upload-area (drag & drop)
├── существующие select-ы (mechanism, language)
├── существующая collapsible секция параметров
└── существующая submit button

JS form submit handler:
  if urlInput.value.trim():
    → FormData { url, mechanism, language, ...params }
    → POST /api/v1/transcribe-url
  else:
    → FormData { file, mechanism, language, ...params }
    → POST /api/v1/transcribe
```

## Изменяемые файлы

| Файл | Изменение |
|------|-----------|
| `src/templates/uploads.html` | Добавить URL input section, модифицировать submit handler |
| `src/static/new_style.css` | Добавить стили `.url-input-section` и `#urlInput` |
| `docs/TODO.md` | Отметить задачу как выполненную |

## Детали реализации

### HTML: URL input section

Вставить перед `<div class="upload-area">` (строка ~57 uploads.html):

```html
<div class="url-input-section">
    <input type="url" id="urlInput" class="form-input url-input"
           placeholder="Вставьте URL видео или аудио">
</div>
```

### CSS: стили

```css
.url-input-section {
    width: 100%;
    margin-bottom: 12px;
}

.url-input {
    width: 100%;
}
```

Те же стили для тёмной темы (автоматически через `#urlInput.form-input`).

### JS: модификация submit handler

Текущий handler (строки 366-418) модифицируется:

```javascript
// В submit handler, перед отправкой:
const urlValue = document.getElementById('urlInput').value.trim();
const fileInput = document.getElementById('audioFile');

const endpoint = urlValue ? '/api/v1/transcribe-url' : '/api/v1/transcribe';

const formData = new FormData(form);
if (urlValue) {
    formData.set('url', urlValue);
}

// Отображение URL в loading state
if (urlValue) {
    const truncatedUrl = urlValue.length > 60 ? urlValue.substring(0, 60) + '...' : urlValue;
    loadingState.querySelector('.loading-text').textContent = `Транскрипция: ${truncatedUrl}`;
}
```

### JS: валидация URL

Перед отправкой:

```javascript
if (urlValue && !urlValue.match(/^https?:\/\//)) {
    showError('URL должен начинаться с http:// или https://');
    return;
}
```

### Обработка ошибок

Использовать существующий `showError()` механизм (строки ~570-590 uploads.html). Backend возвращает JSON с полем `detail` — отображать его в toast.

## Отмеченные задачи в TODO.md

Задача «Добавить загрузку видео и аудио по URL» отмечается как выполненная — бэкенд был реализован ранее, теперь добавляется UI.

## Верификация

1. Запустить приложение: `source .venv/bin/activate && python src/main.py`
2. Открыть `http://localhost:8000/uploads`
3. Проверить что URL поле отображается над drag&drop зоной
4. Проверить что URL поле корректно отображается в тёмной теме
5. Ввести URL (YouTube/прямая ссылка) и нажать «Транскрибировать» — проверить что запрос уходит на `/api/v1/transcribe-url`
6. Выбрать файл и нажать «Транскрибировать» — проверить что запрос уходит на `/api/v1/transcribe` (файловая загрузка не сломана)
7. Ввести невалидный URL (без http://) — проверить валидацию
8. Проверить отображение URL в loading state (обрезка до 60 символов)
9. Проверить редирект на `/?redirect=<job_id>` после успешной транскрипции по URL

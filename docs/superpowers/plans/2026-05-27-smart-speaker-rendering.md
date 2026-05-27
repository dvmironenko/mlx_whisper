# Smart Speaker Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Автоматически определять наличие спикеров в сегментах расшифровки и рендерить метки спикеров только когда они есть.

**Architecture:** Изменить `_build_formatted_text_from_segments` — убрать параметр `include_speaker`, добавить автоопределение по наличию `speaker != 0` в сегментах. Обновить двух вызывающих.

**Tech Stack:** Python 3.12+, FastAPI, vanilla JS frontend.

---

### Task 1: Изменить `_build_formatted_text_from_segments` — автоопределение спикеров

**Files:**
- Modify: `src/services/whisper_engines.py:152-179`

- [ ] **Шаг 1: Заменить функцию `_build_formatted_text_from_segments`**

  Убрать параметр `include_speaker`, добавить автоопределение.

  **Было:**
  ```python
  def _build_formatted_text_from_segments(
      segments: list[dict],
      *,
      include_speaker: bool = False,
      include_timestamps: bool = True,
  ) -> str:
      """Собрать текст из сегментов.

      При include_timestamps=True — формат [MM:SS]: Текст.
      При include_timestamps=False — только текст, без префикса.
      """
      lines: list[str] = []
      for seg in segments:
          start = seg.get("start", 0)
          speaker = seg.get("speaker", 0)
          text = seg.get("text", "").strip()
          if not text:
              continue
          if include_timestamps:
              minutes = int(start) // 60
              seconds = int(start) % 60
              if include_speaker:
                  lines.append(f"[{minutes:02d}:{seconds:02d}] Спикер {speaker} : {text}")
              else:
                  lines.append(f"[{minutes:02d}:{seconds:02d}]: {text}")
          else:
              lines.append(text)
      return "\n".join(lines)
  ```

  **Стало:**
  ```python
  def _build_formatted_text_from_segments(
      segments: list[dict],
      *,
      include_timestamps: bool = True,
  ) -> str:
      """Собрать текст из сегментов.

      Спикеры определяются автоматически: если хотя бы один сегмент
      имеет speaker != 0, рендерятся метки спикеров.
      Иначе — текст без меток.

      При include_timestamps=True — формат [MM:SS]: Текст.
      При include_timestamps=False — только текст, без префикса.
      """
      # Автоопределение: спикеры есть, если хотя бы у одного сегмента
      # speaker != 0
      has_speakers = any(seg.get("speaker", 0) != 0 for seg in segments)

      lines: list[str] = []
      for seg in segments:
          start = seg.get("start", 0)
          speaker = seg.get("speaker", 0)
          text = seg.get("text", "").strip()
          if not text:
              continue
          if include_timestamps:
              minutes = int(start) // 60
              seconds = int(start) % 60
              if has_speakers:
                  lines.append(f"[{minutes:02d}:{seconds:02d}] Спикер {speaker} : {text}")
              else:
                  lines.append(f"[{minutes:02d}:{seconds:02d}]: {text}")
          else:
              lines.append(text)
      return "\n".join(lines)
  ```

- [ ] **Шаг 2: Убедиться, что функция корректна**

  Проверить синтаксис: `python -c "import ast; ast.parse(open('src/services/whisper_engines.py').read())"`

- [ ] **Шаг 3: Закоммитить**

  ```bash
  git add src/services/whisper_engines.py
  git commit -m "refactor: auto-detect speakers in _build_formatted_text_from_segments

  Remove include_speaker parameter; scan segments for speaker != 0
  and render labels only when present. Handles both oMLX API formats."
  ```

### Task 2: Обновить вызовы `_build_formatted_text_from_segments`

**Files:**
- Modify: `src/services/omlx_engine.py:300-301`
- Modify: `src/services/whisper_engines.py:136` (WhisperEngine вызов)

- [ ] **Шаг 1: Обновить вызов в OMLXEngine**

  **Было** ([omlx_engine.py:300-301](src/services/omlx_engine.py#L300-L301)):
  ```python
  formatted_text = _build_formatted_text_from_segments(
      all_segments, include_speaker=True, include_timestamps=include_timestamps
  )
  ```

  **Стало:**
  ```python
  formatted_text = _build_formatted_text_from_segments(
      all_segments, include_timestamps=include_timestamps
  )
  ```

- [ ] **Шаг 2: Обновить вызов в WhisperEngine**

  Найти вызов в `whisper_engines.py` (около строки 136), убрать `include_speaker=False` — автоопределение даст тот же результат (все сегменты Whisper имеют `speaker=0`, поэтому `has_speakers=False`).

- [ ] **Шаг 3: Закоммитить**

  ```bash
  git add src/services/omlx_engine.py src/services/whisper_engines.py
  git commit -m "fix: remove include_speaker from callers of _build_formatted_text_from_segments

  Auto-detection handles speaker rendering, no need for explicit flag."
  ```

### Task 3: Верификация

- [ ] **Шаг 1: Запустить сервер**

  ```bash
  source .venv/bin/activate && python src/main.py
  ```

- [ ] **Шаг 2: Проверить транскрипцию через oMLX без спикеров**

  Загрузить аудио, транскрибировать через oMLX. В модальном окне результата не должно быть "Спикер 0" для всех сегментов.

- [ ] **Шаг 3: Проверить транскрипцию через локальный Whisper**

  Локальная транскрипция — без меток спикеров.

- [ ] **Шаг 4: Остановить сервер**

  ```bash
  kill $(lsof -ti:8801)
  ```

---

## Self-Review

1. **Spec coverage:** Все требования spec покрыты — автоопределение спикеров, оба формата API, обновление вызывающих.
2. **Placeholder scan:** Нет placeholder-ов. Каждый шаг содержит конкретный код и команды.
3. **Type consistency:** Сигнатура функции изменена консистентно во всех вызовах.

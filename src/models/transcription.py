"""Реализация транскрибации с помощью MLX-Whisper."""

import os
from typing import Any, Optional

# Import mlx_whisper.transcribe
try:
    from mlx_whisper.transcribe import transcribe
except ImportError:
    raise ImportError("mlx-whisper package is required. Install it with: pip install mlx-whisper")


def transcribe_audio(
    file_path: str,
    language: Optional[str] = None,
    task: str = "transcribe",
    model: str = "large",
    word_timestamps: bool = False,
    condition_on_previous_text: bool = True,
    no_speech_threshold: Optional[float] = None,
    hallucination_silence_threshold: Optional[float] = None,
    initial_prompt: Optional[str] = None,
) -> Any:
    """
    Транскрибировать аудиофайл с помощью MLX-Whisper.

    Parameters
    ----------
    file_path: str
        Путь к аудиофайлу для транскрибации
    language: Optional[str]
        Код языка аудио (например, 'ru', 'en'). Если None, определяется автоматически
    task: str
        Тип задачи: 'transcribe' (транскрипция) или 'translate' (перевод)
    model: str
        Размер модели (tiny, base, small, medium, turbo, large)
    word_timestamps: bool
        Извлекать таймстемпы на уровне слов
    condition_on_previous_text: bool
        Использовать предыдущий текст как промпт для следующего окна
    no_speech_threshold: Optional[float]
        Порог для определения тишины
    hallucination_silence_threshold: Optional[float]
        Порог для определения галлюцинаций
    initial_prompt: Optional[str]
        Начальный промпт для контекстной транскрипции

    Returns
    -------
    dict
        Результат транскрипции с ключами:
        - text: текст транскрипции
        - language: определённый язык
        - duration: продолжительность аудио
        - segments: сегменты с таймстемпами (если word_timestamps=True)
    """
    # Получаем путь к модели
    models_dir = os.getenv("MODELS_DIR", "models")

    # Сопоставляем имена моделей
    model_mapping = {
        "tiny": os.path.join(models_dir, "whisper-tiny"),
        "base": os.path.join(models_dir, "whisper-base"),
        "small": os.path.join(models_dir, "whisper-small"),
        "medium": os.path.join(models_dir, "whisper-medium"),
        "turbo": os.path.join(models_dir, "whisper-turbo"),
        "large": os.path.join(models_dir, "whisper-large"),
    }

    model_path = model_mapping.get(model, os.path.join(models_dir, "whisper-large"))

    # Проверяем существование модели
    if not os.path.exists(model_path):
        # Используем модель из HuggingFace
        model_path = f"mlx-community/whisper-{model}"

    # Подготавливаем параметры
    transcribe_options = {
        "language": language,
        "task": task,
        "word_timestamps": word_timestamps,
        "condition_on_previous_text": condition_on_previous_text,
    }

    # Добавляем threshold parameters
    if no_speech_threshold is not None:
        transcribe_options["no_speech_threshold"] = no_speech_threshold
    if hallucination_silence_threshold is not None:
        transcribe_options["hallucination_silence_threshold"] = hallucination_silence_threshold
    if initial_prompt is not None:
        transcribe_options["initial_prompt"] = initial_prompt

    # Выполняем транскрипцию
    result = transcribe(
        audio=file_path,
        path_or_hf_repo=model_path,
        **transcribe_options
    )

    return result

"""Утилиты для разрешения параметров транскрипции."""

from typing import Optional

from src.config import (
    DEFAULT_CONDITION_ON_PREVIOUS,
    DEFAULT_TASK,
    DEFAULT_WORD_TIMESTAMPS,
    HALLUCINATION_SILENCE_THRESHOLD,
    NO_SPEECH_THRESHOLD,
    OMLX_MODELS,
    OMLX_MODEL,
    REMOVE_SILENCE,
    SILENCE_DURATION,
    SILENCE_THRESHOLD,
)


def resolve_transcription_params(
    mechanism: str,
    model: str,
    language: Optional[str],
    task: str,
    word_timestamps: str,
    condition_on_previous_text: str,
    remove_silence: Optional[str],
    silence_threshold: Optional[str],
    silence_duration: Optional[str],
    no_speech_threshold: Optional[str],
    hallucination_silence_threshold: Optional[str],
    initial_prompt: Optional[str],
    include_timestamps: Optional[str],
) -> dict:
    """Resolve form parameters to resolved values with env defaults.

    Returns a dict with all resolved parameter values ready to pass
    to the transcription queue.
    """
    # Model resolution
    if mechanism == "omlx":
        model_value = OMLX_MODEL
        if model in OMLX_MODELS:
            model_value = model
    else:
        model_value = model

    # Task resolution — use env default
    task_value = task or DEFAULT_TASK

    # Word timestamps — form "false" means use env default
    if word_timestamps == "false":
        word_timestamps_value = DEFAULT_WORD_TIMESTAMPS.lower() == "true"
    else:
        word_timestamps_value = word_timestamps.lower() == "true"

    # Condition on previous — form "true" means use env default
    if condition_on_previous_text == "true":
        condition_on_previous_text_value = DEFAULT_CONDITION_ON_PREVIOUS.lower() == "true"
    else:
        condition_on_previous_text_value = condition_on_previous_text.lower() == "true"

    # Silence removal
    remove_silence_value = REMOVE_SILENCE if remove_silence is None else remove_silence.lower() == "true"

    # Silence thresholds
    silence_threshold_value = SILENCE_THRESHOLD if silence_threshold is None else float(silence_threshold)
    silence_duration_value = SILENCE_DURATION if silence_duration is None else float(silence_duration)

    # Transcription thresholds
    no_speech_threshold_value = NO_SPEECH_THRESHOLD if no_speech_threshold is None else float(no_speech_threshold)
    hallucination_silence_threshold_value = (
        HALLUCINATION_SILENCE_THRESHOLD
        if hallucination_silence_threshold is None
        else float(hallucination_silence_threshold)
    )

    # Include timestamps
    include_timestamps_value = include_timestamps is not None and include_timestamps.lower() == "true"

    return {
        "model": model_value,
        "language": language,
        "task": task_value,
        "word_timestamps": word_timestamps_value,
        "condition_on_previous_text": condition_on_previous_text_value,
        "no_speech_threshold": no_speech_threshold_value,
        "hallucination_silence_threshold": hallucination_silence_threshold_value,
        "initial_prompt": initial_prompt,
        "mechanism": mechanism,
        "include_timestamps": include_timestamps_value,
        "remove_silence": remove_silence_value,
        "silence_threshold": silence_threshold_value,
        "silence_duration": silence_duration_value,
    }

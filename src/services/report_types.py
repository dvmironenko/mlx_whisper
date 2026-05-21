"""Загрузка конфигурации типов отчетов из JSON-файла."""

import json
import os
from typing import List, Dict, Any

# Модульный кэш: список типов отчетов или None при ошибке
_report_types_cache: List[Dict[str, Any]] | None = None


def _find_reports_json() -> str | None:
    """Найти путь к config/reports.json."""
    candidates = [
        os.path.join(os.getcwd(), "config", "reports.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "reports.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def load_report_types() -> List[Dict[str, Any]]:
    """
    Загрузить список типов отчетов из config/reports.json.

    Результат кэшируется на уровне модуля. При первом вызове файл
    читается с диска, далее возвращается кэш.

    Returns
    -------
    List[Dict[str, Any]]
        Список словарей {id, name, prompt} или пустой список при ошибке.
    """
    global _report_types_cache

    if _report_types_cache is not None:
        return _report_types_cache

    try:
        path = _find_reports_json()
        if path is None:
            from src.config import logger
            logger.warning("config/reports.json не найден. Типы отчетов отключены.")
            _report_types_cache = []
            return _report_types_cache

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            from src.config import logger
            logger.error(f"config/reports.json: ожидается массив, получен {type(data).__name__}")
            _report_types_cache = []
            return _report_types_cache

        # Валидация: каждый элемент должен иметь id и name
        for item in data:
            if not isinstance(item, dict):
                raise ValueError(f"Ожидается словарь, получен {type(item).__name__}")
            if "id" not in item or "name" not in item:
                raise ValueError(f"Элемент конфига должен содержать 'id' и 'name': {item}")

        _report_types_cache = data
        return data

    except json.JSONDecodeError as e:
        from src.config import logger
        logger.error(f"config/reports.json: ошибка парсинга JSON: {e}")
        _report_types_cache = []
        return []
    except Exception as e:
        from src.config import logger
        logger.error(f"config/reports.json: не удалось загрузить: {e}")
        _report_types_cache = []
        return []


def clear_cache() -> None:
    """Сбросить модульный кэш — следующий вызов load_report_types() перечитает файл."""
    global _report_types_cache
    _report_types_cache = None


def save_report_prompt(report_type_id: str, prompt: str, *, name: str | None = None) -> None:
    """
    Сохранить промт (и опционально название) для заданного report_type_id.

    Parameters
    ----------
    report_type_id: str
        ID типа отчета.
    prompt: str
        Новый текст промпта.
    name: str | None
        Новое название отчета (опционально).

    Raises
    ------
    ValueError
        Если тип отчета не найден или файл не существует.
    """
    path = _find_reports_json()
    if path is None:
        raise ValueError("config/reports.json не найден")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        if isinstance(item, dict) and item.get("id") == report_type_id:
            item["prompt"] = prompt
            if name is not None:
                item["name"] = name
            break
    else:
        raise ValueError(f"Тип отчета '{report_type_id}' не найден")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Обновить кэш
    global _report_types_cache
    _report_types_cache = data


def get_prompt_for_report_type(report_type_id: str) -> str | None:
    """
    Вернуть промт для заданного report_type_id.

    Parameters
    ----------
    report_type_id: str
        ID типа отчета (например, "summary").

    Returns
    -------
    str | None
        Промт для LLM или None если тип не найден.
    """
    types = load_report_types()
    for t in types:
        if t["id"] == report_type_id:
            return t.get("prompt")
    return None

"""Тесты для src/services/report_types.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services import report_types


class TestLoadReportTypes:
    """Тесты загрузки конфигурации типов отчетов."""

    def test_returns_list(self):
        result = report_types.load_report_types()
        assert isinstance(result, list)

    def test_contains_two_items(self):
        result = report_types.load_report_types()
        assert len(result) == 2

    def test_first_item_has_correct_id(self):
        result = report_types.load_report_types()
        assert result[0]["id"] == "summary"

    def test_second_item_has_correct_id(self):
        result = report_types.load_report_types()
        assert result[1]["id"] == "protocol"

    def test_first_item_has_name(self):
        result = report_types.load_report_types()
        assert result[0]["name"] == "Сжатый пересказ"

    def test_second_item_has_name(self):
        result = report_types.load_report_types()
        assert result[1]["name"] == "Протокол терапевтической сессии"

    def test_each_item_has_prompt(self):
        result = report_types.load_report_types()
        for item in result:
            assert "prompt" in item
            assert len(item["prompt"]) > 0

    def test_caching_works(self):
        # Первый вызов загружает из файла
        first = report_types.load_report_types()
        # Второй должен вернуть кэш (тот же объект)
        second = report_types.load_report_types()
        assert first is second

    def test_each_item_has_required_keys(self):
        result = report_types.load_report_types()
        for item in result:
            assert "id" in item
            assert "name" in item


class TestGetPromptForReportType:
    """Тесты получения промта по report_type_id."""

    def test_summary_prompt(self):
        prompt = report_types.get_prompt_for_report_type("summary")
        assert prompt is not None
        assert len(prompt) > 0

    def test_protocol_prompt(self):
        prompt = report_types.get_prompt_for_report_type("protocol")
        assert prompt is not None
        assert "протокол" in prompt.lower() or "совещани" in prompt.lower()

    def test_unknown_type_returns_none(self):
        prompt = report_types.get_prompt_for_report_type("nonexistent")
        assert prompt is None

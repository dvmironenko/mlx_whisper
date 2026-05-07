"""Тест функции разделения текста на чанки."""

import os
import sys

# Получаем путь к проекту
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.models.report import split_text, load_segments_file
from src.config import MAX_REPORT_CHUNK_SIZE


def test_split_text_with_console_output():
    """Тест разбиения текста с выводом чанков в консоль и сохранением в файл."""
    # Путь к файлу с сегментами
    job_id = "9d379991-4098-4abf-a09f-bcc6b439f7c0"
    segments_dir = os.path.join(os.path.dirname(__file__), "..", "data", job_id)

    # Загружаем файл сегментов
    text = load_segments_file(segments_dir)

    if text is None:
        print("ОШИБКА: Не удалось загрузить файл сегментов")
        return

    print(f"\nЗагружен текст длиной {len(text)} символов")
    print(f"Используем MAX_REPORT_CHUNK_SIZE = {MAX_REPORT_CHUNK_SIZE} символов")

    # Разбиваем текст на чанки используя размер из конфигурации
    chunks = split_text(text)

    print(f"Текст разбит на {len(chunks)} чанков\n")
    print("=" * 80)

    # Формируем вывод для файла
    output_lines = []
    output_lines.append(f"Загружен текст длиной {len(text)} символов")
    output_lines.append(f"Используем MAX_REPORT_CHUNK_SIZE = {MAX_REPORT_CHUNK_SIZE} символов")
    output_lines.append(f"Текст разбит на {len(chunks)} чанков\n")
    output_lines.append("=" * 80)

    for i, chunk in enumerate(chunks):
        chunk_output = f"\n--- ЧАНК {i + 1}/{len(chunks)} (длина: {len(chunk)} символов) ---\n{chunk}"
        print(chunk_output)
        output_lines.append(chunk_output)

    output_lines.append("\n" + "=" * 80)
    output_lines.append(f"\nИтого: {len(chunks)} чанков сгенерировано успешно")

    # Сохраняем в файл
    output_file = os.path.join(os.path.dirname(__file__), "test_split_text_chunks.txt")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        print(f"\nРезультаты сохранены в {output_file}")
    except Exception as e:
        print(f"Ошибка при сохранении в файл: {e}")


if __name__ == "__main__":
    test_split_text_with_console_output()

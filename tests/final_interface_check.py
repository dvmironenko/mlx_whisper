#!/usr/bin/env python3
"""
Финальная проверка работы нового интерфейса MLX-Transcriber
"""

import requests
import time

def check_interface():
    """Проверить работоспособность нового интерфейса"""
    try:
        print("Проверка нового интерфейса MLX-Transcriber...")
        print("=" * 50)

        # Проверяем, что сервер отвечает
        response = requests.get('http://localhost:8802', timeout=5)

        if response.status_code == 200:
            print("✅ Сервер запущен и отвечает корректно")
            print(f"Статус код: {response.status_code}")

            # Проверяем содержимое
            content = response.text

            # Проверяем ключевые элементы интерфейса
            checks = [
                ("HTML заголовок", "<title>MLX-Transcriber Audio Transcription</title>" in content),
                ("Новый CSS файл", "/static/new_style.css" in content),
                ("Заголовок приложения", "app-title" in content),
                ("Форма загрузки", 'id="uploadForm"' in content),
                ("Чекбоксы", "checkbox" in content),
            ]

            print("\nПроверка элементов интерфейса:")
            all_passed = True
            for check_name, passed in checks:
                status = "✅" if passed else "❌"
                print(f"  {status} {check_name}")
                if not passed:
                    all_passed = False

            # Проверяем, что чекбоксы не дублируются
            if "wordTimestamps" in content and "conditionOnPreviousText" in content:
                # Подсчитываем вхождения
                word_timestamps_count = content.count('id="wordTimestamps"')
                condition_text_count = content.count('id="conditionOnPreviousText"')

                print(f"\nПроверка уникальности чекбоксов:")
                print(f"  ✅ wordTimestamps: {word_timestamps_count} раз(а)")
                print(f"  ✅ conditionOnPreviousText: {condition_text_count} раз(а)")

                if word_timestamps_count == 1 and condition_text_count == 1:
                    print("  ✅ Чекбоксы уникальны (не дублируются)")
                else:
                    print("  ❌ Чекбоксы дублируются!")
                    all_passed = False
            else:
                print("❌ Не найдены чекбоксы")
                all_passed = False

            if all_passed:
                print("\n🎉 Все проверки пройдены успешно!")
                print("✅ Новый интерфейс готов к использованию")
                return True
            else:
                print("\n❌ Некоторые проверки не пройдены")
                return False
        else:
            print(f"❌ Ошибка: HTTP статус {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Не удалось подключиться к серверу. Проверьте, что сервер запущен")
        return False
    except Exception as e:
        print(f"❌ Ошибка при проверке интерфейса: {e}")
        return False

def main():
    print("Финальная проверка нового интерфейса MLX-Transcriber")
    print("=" * 60)

    success = check_interface()

    if success:
        print("\n" + "=" * 60)
        print("✅ Финальная проверка завершена успешно!")
        print("\nДля использования интерфейса:")
        print("1. Запустите сервер: MLX_WHISPER_PORT=8802 python src/main.py")
        print("2. Откройте в браузере: http://localhost:8802")
        print("3. Используйте улучшенный интерфейс для транскрибации аудио")
    else:
        print("\n" + "=" * 60)
        print("❌ Финальная проверка не пройдена")
        print("Проверьте работу сервера и интерфейса")

if __name__ == "__main__":
    main()
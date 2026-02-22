#!/usr/bin/env python3
"""
Простая проверка нового интерфейса через HTTP-запрос
"""

import requests
import time

def test_interface():
    """Проверить доступность нового интерфейса"""
    try:
        # Попробуем получить главную страницу
        response = requests.get('http://localhost:8802', timeout=10)

        if response.status_code == 200:
            print("✅ Интерфейс успешно запущен и доступен")
            print(f"Статус код: {response.status_code}")

            # Проверим наличие ключевых элементов интерфейса
            content = response.text

            # Проверим наличие основных элементов нового дизайна
            checks = [
                ("Новый CSS файл", "new_style.css" in content),
                ("Новый заголовок", "<title>MLX-Whisper Audio Transcription</title>" in content),
                ("Кнопка отправки", 'class="submit-button"' in content),
                ("Форма загрузки", 'id="uploadForm"' in content),
            ]

            print("\nПроверка элементов интерфейса:")
            all_passed = True
            for check_name, passed in checks:
                status = "✅" if passed else "❌"
                print(f"  {status} {check_name}")
                if not passed:
                    all_passed = False

            if all_passed:
                print("\n🎉 Все элементы интерфейса корректно отображаются!")
                return True
            else:
                print("\n⚠️  Некоторые элементы отсутствуют")
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

if __name__ == "__main__":
    print("Проверка нового интерфейса MLX-Whisper...")
    print("=" * 50)

    success = test_interface()

    if success:
        print("\n" + "=" * 50)
        print("✅ Тест пройден успешно!")
        print("Новый интерфейс готов к использованию")
    else:
        print("\n" + "=" * 50)
        print("❌ Тест не пройден")
        print("Проверьте работу сервера и интерфейса")

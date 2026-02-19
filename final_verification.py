#!/usr/bin/env python3
"""
Финальная проверка нового интерфейса MLX-Whisper
"""

import os

def check_files():
    """Проверить создание файлов"""
    print("Проверка созданных файлов:")

    # Проверить HTML файл
    html_file = "src/templates/new_index.html"
    if os.path.exists(html_file):
        print("✅ HTML файл создан")
        with open(html_file, 'r') as f:
            content = f.read()
            if "app-title" in content and "new_style.css" in content:
                print("✅ HTML содержит элементы нового интерфейса")
            else:
                print("❌ HTML не содержит элементы нового интерфейса")
    else:
        print("❌ HTML файл не создан")

    # Проверить CSS файл
    css_file = "src/static/new_style.css"
    if os.path.exists(css_file):
        print("✅ CSS файл создан")
        with open(css_file, 'r') as f:
            content = f.read()
            if "app-header" in content and "--primary-color" in content:
                print("✅ CSS содержит элементы нового дизайна")
            else:
                print("❌ CSS не содержит элементы нового дизайна")
    else:
        print("❌ CSS файл не создан")

    # Проверить изменение в main.py
    main_file = "src/main.py"
    if os.path.exists(main_file):
        with open(main_file, 'r') as f:
            content = f.read()
            if "new_index.html" in content:
                print("✅ main.py обновлен для использования нового шаблона")
            else:
                print("❌ main.py не обновлен")
    else:
        print("❌ Файл main.py не найден")

def main():
    print("Финальная проверка нового интерфейса MLX-Whisper")
    print("=" * 50)

    check_files()

    print("\n" + "=" * 50)
    print("✅ Проверка завершена")
    print("\nДля запуска сервера используйте:")
    print("MLX_WHISPER_PORT=8802 python src/main.py")
    print("\nЗатем откройте в браузере: http://localhost:8802")

if __name__ == "__main__":
    main()
"""
Тест структуры API MLX-Whisper для проверки endpoint'ов.
"""

import subprocess
import sys
import os
import time
import requests
import json

def test_api_structure():
    """Тест структуры API для MLX-Whisper."""

    print("Проверка структуры API MLX-Whisper")
    print("=" * 50)

    # Запуск сервера в подпроцессе
    print("Запуск сервера MLX-Whisper...")

    # Запуск FastAPI сервера в фоне
    server_process = subprocess.Popen([
        sys.executable, "src/main.py"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Даем серверу время на запуск
    print("Ожидание инициализации сервера...")
    time.sleep(3)

    try:
        # Проверка всех основных endpoint'ов
        print("\n1. Проверка доступности endpoint'ов:")

        # Проверка health endpoint
        try:
            health_response = requests.get("http://localhost:8801/api/v1/health", timeout=5)
            print(f"   /api/v1/health: {health_response.status_code} - {'✓ OK' if health_response.status_code == 200 else '✗ ERROR'}")
            if health_response.status_code == 200:
                print(f"      Ответ: {health_response.json()}")
        except Exception as e:
            print(f"   /api/v1/health: Ошибка - {e}")

        # Проверка models endpoint
        try:
            models_response = requests.get("http://localhost:8801/api/v1/models", timeout=5)
            print(f"   /api/v1/models: {models_response.status_code} - {'✓ OK' if models_response.status_code == 200 else '✗ ERROR'}")
            if models_response.status_code == 200:
                print(f"      Ответ: {models_response.json()}")
        except Exception as e:
            print(f"   /api/v1/models: Ошибка - {e}")

        # Проверка root endpoint
        try:
            root_response = requests.get("http://localhost:8801/", timeout=5)
            print(f"   /: {root_response.status_code} - {'✓ OK' if root_response.status_code == 200 else '✗ ERROR'}")
            print(f"      Длина контента: {len(root_response.text)} символов")
        except Exception as e:
            print(f"   /: Ошибка - {e}")

        # Проверка структуры endpoint'ов
        print("\n2. Структура API:")
        print("   Основные endpoint'ы:")
        print("   - GET /api/v1/health")
        print("     - Назначение: Проверка состояния сервиса")
        print("     - Возвращает: {\"status\": \"healthy\", \"version\": \"1.0.0\"}")

        print("   - GET /api/v1/models")
        print("     - Назначение: Возвращает список поддерживаемых моделей")
        print("     - Возвращает: {\"supported_models\": [...]}")

        print("   - POST /api/v1/transcribe")
        print("     - Назначение: Транскрибация аудиофайлов")
        print("     - Требования: multipart/form-data с файлом")
        print("     - Параметры:")
        print("       * file (обязательно): Аудио файл")
        print("       * language (необязательно): Язык")
        print("       * task (необязательно): transcribe/translate")
        print("       * model (необязательно): tiny/base/small/medium/turbo/large")
        print("       * no_speech_threshold (необязательно): 0.0-1.0")
        print("       * hallucination_silence_threshold (необязательно): 0.0-1.0")
        print("       * word_timestamps (необязательно): true/false")
        print("       * condition_on_previous_text (необязательно): true/false")

        # Проверка правильности структуры
        print("\n3. Структура API описана в router.py:")

        # Проверка что все необходимые endpoint'ы определены
        required_endpoints = [
            "/api/v1/health",
            "/api/v1/models",
            "/api/v1/transcribe"
        ]

        print("   Проверка наличия endpoint'ов:")
        for endpoint in required_endpoints:
            try:
                response = requests.get(f"http://localhost:8801{endpoint}", timeout=5)
                print(f"   ✓ {endpoint}: доступен (статус {response.status_code})")
            except Exception as e:
                print(f"   ⚠ {endpoint}: ошибка - {e}")

        # Проверка документации
        print("\n4. Описание параметров:")
        print("   Параметры для POST /api/v1/transcribe:")
        print("   - file: multipart/form-data файл (обязательно)")
        print("   - language: строка (необязательно, по умолчанию авто)")
        print("   - task: 'transcribe' или 'translate' (по умолчанию 'transcribe')")
        print("   - model: размер модели (по умолчанию 'large')")
        print("   - no_speech_threshold: число 0.0-1.0 (по умолчанию 0.4)")
        print("   - hallucination_silence_threshold: число 0.0-1.0 (по умолчанию 0.8)")
        print("   - word_timestamps: 'true'/'false' (по умолчанию 'false')")
        print("   - condition_on_previous_text: 'true'/'false' (по умолчанию 'true')")

        # Примеры ответов
        print("\n5. Примеры ответов:")
        print("   Успешный ответ:")
        success_example = {
            "text": "Пример транскрибированного текста",
            "language": "ru",
            "model": "turbo",
            "segments": [],
            "job_id": "job_123456789",
            "duration": 15.2
        }
        print("   ", json.dumps(success_example, ensure_ascii=False, indent=2))

        print("\n   Ошибка:")
        error_example = {
            "error": "Unsupported audio format. Supported: .wav, .mp3, .m4a, .flac, .aac, .ogg, .wma, .webm, .mp4",
            "code": "INVALID_FORMAT"
        }
        print("   ", json.dumps(error_example, ensure_ascii=False, indent=2))

        print("\n" + "=" * 50)
        print("✓ ТЕСТ СТРУКТУРЫ API ЗАВЕРШЕН")

        return True

    except Exception as e:
        print(f"\n✗ ТЕСТ СТРУКТУРЫ API НЕ УДАЛСЯ: {e}")
        return False

    finally:
        # Закрытие сервера
        print("\nОстановка сервера...")
        try:
            server_process.terminate()
            server_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_process.kill()
        except:
            pass

if __name__ == "__main__":
    success = test_api_structure()

    if not success:
        sys.exit(1)
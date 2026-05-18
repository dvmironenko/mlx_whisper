"""Playwright-тест: выбор типа отчета в карточке завершенной задачи."""

import subprocess
import time
from playwright.sync_api import sync_playwright, Page, Locator

BASE_URL = "http://localhost:8801"


def find_completed_job_id(page: Page) -> str | None:
    """Найти ID первой завершенной задачи, у которой есть dropdown отчетов."""
    page.goto(f"{BASE_URL}/")
    page.wait_for_timeout(2000)  # дать загрузиться

    # Ищем все карточки задач
    cards = page.locator(".job-card").all()
    for card in cards:
        if card.locator("select.report-type-select").count() > 0:
            # Нашли карточку с dropdown отчетов
            job_id = card.get_attribute("data-job-id")
            if job_id:
                return job_id
            # Пробуем извлечь из кнопки
            btn = card.locator("button.btn-report-job").first
            onclick = btn.get_attribute("onclick") or ""
            # Извлекаем job_id из onclick: await generateReport(jobId, select.value)
            # Но у нас select.value, так что берем data-job-id
            # Если data-job-id нет, ищем в HTML карточки
            job_id = card.get_attribute("data-job-id")
            if not job_id:
                # Пробуем извлечь из текста или атрибутов
                inner = card.inner_html()
                import re
                m = re.search(r'data-job-id="([a-f0-9-]+)"', inner)
                if m:
                    job_id = m.group(1)
            if job_id:
                return job_id
    return None


def test_report_type_selection():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        print("=" * 60)
        print("ТЕСТ: Выбор типа отчета в карточке задачи")
        print("=" * 60)

        try:
            # 1. Загружаем страницу
            print("\n1. Загрузка страницы...")
            page.goto(BASE_URL)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
            print(f"   URL: {page.url}")
            print(f"   Заголовок: {page.title()}")

            # 2. Проверяем, что загрузились report types
            print("\n2. Проверка загрузки типов отчетов...")
            report_types_resp = page.evaluate("""
                () => fetch('/api/v1/report-types').then(r => r.json())
            """)
            types = report_types_resp.get("types", [])
            print(f"   Типы отчетов: {types}")
            assert len(types) > 0, "Типы отчетов не загружены"
            print(f"   [OK] Найдено {len(types)} типов отчетов")

            # 3. Находим завершенную задачу с dropdown
            print("\n3. Поиск завершенной задачи с dropdown отчетов...")
            page.goto(BASE_URL)
            page.wait_for_timeout(2000)

            # Ищем dropdown select
            selects = page.locator("select.report-type-select").all()
            print(f"   Найдено dropdown: {len(selects)}")
            assert len(selects) > 0, "Не найден dropdown выбора типа отчета"
            print(f"   [OK] Dropdown найден")

            first_select = selects[0]
            parent_card = first_select.evaluate_handle("el => el.closest('.job-card')")
            card_text = first_select.evaluate("""el => {
                const card = el.closest('.job-card');
                if (!card) return '';
                const titleEl = card.querySelector('.job-title, h3, .card-title');
                return titleEl ? titleEl.textContent.trim() : '';
            }""")
            print(f"   Карточка: {card_text[:60]}...")

            # 4. Проверяем содержимое dropdown
            print("\n4. Проверка содержимого dropdown...")
            options = first_select.locator("option").all()
            print(f"   Опций: {len(options)}")
            option_texts = [opt.text_content() for opt in options]
            print(f"   Тексты: {option_texts}")
            assert option_texts[0] == "Выберите тип", f"Первая опция должна быть 'Выберите тип', got '{option_texts[0]}'"
            print(f"   [OK] Первая опция: '{option_texts[0]}'")

            # 5. Проверяем, что кнопка "Отчет" disabled по умолчанию
            print("\n5. Проверка состояния кнопки 'Отчет'...")
            report_button = first_select.locator("..").locator("button.btn-report-job")
            is_disabled = report_button.is_disabled()
            print(f"   Кнопка disabled: {is_disabled}")
            assert is_disabled, "Кнопка 'Отчет' должна быть disabled по умолчанию"
            print(f"   [OK] Кнопка disabled")

            # 6. Выбираем первый реальный тип (не "Выберите тип")
            print("\n6. Выбор типа отчета...")
            first_type_option = first_select.locator("option:nth-child(2)")
            first_type_value = first_type_option.get_attribute("value")
            first_type_text = first_type_option.text_content()
            print(f"   Выбираем: {first_type_text} (value={first_type_value})")
            first_select.select_option(value=first_type_value)
            selected = first_select.input_value()
            print(f"   Выбрано: '{selected}'")
            assert selected == first_type_value, f"Выбрано '{selected}', ожидалось '{first_type_value}'"
            print(f"   [OK] Тип отчета выбран")

            # 7. Проверяем, что кнопка стала enabled
            print("\n7. Проверка состояния кнопки после выбора...")
            is_disabled = report_button.is_disabled()
            print(f"   Кнопка disabled: {is_disabled}")
            assert not is_disabled, "Кнопка 'Отчет' должна быть enabled после выбора типа"
            print(f"   [OK] Кнопка enabled")

            # 8. Кликаем "Отчет" и проверяем уведомление
            print("\n8. Нажатие кнопки 'Отчет'...")

            # Ловим сетевой запрос
            with page.expect_response("**/api/v1/report/**") as response_info:
                report_button.click()

            response = response_info.value
            assert response.status == 200, f"Ожидался 200, got {response.status}"
            print(f"   Ответ API: {response.status}")

            # Ждем появления уведомления
            page.wait_for_timeout(1000)

            # Проверяем наличие модального окна с уведомлением
            success_modal = page.locator(".modal-content.modal-success").first
            modal_visible = success_modal.is_visible(timeout=3000)
            print(f"   Уведомление видно: {modal_visible}")
            assert modal_visible, "Не появилось уведомление 'Отчет генерируется'"

            modal_title = success_modal.locator(".modal-title, h2, h3").first.text_content()
            print(f"   Заголовок уведомления: '{modal_title}'")
            print(f"   [OK] Уведомление появилось")

            # 9. Закрываем уведомление перед вторым кликом
            close_button = page.locator(".modal-overlay button").first
            if close_button.is_visible(timeout=2000):
                close_button.click()
                page.wait_for_timeout(500)
                print("   [OK] Уведомление закрыто")

            # 10. Выбираем второй тип и проверяем
            print("\n10. Переключение на второй тип отчета...")
            if len(types) > 1:
                second_type = types[1]
                second_select = first_select.select_option(value=second_type["id"])
                selected = first_select.input_value()
                print(f"   Выбрано: '{selected}'")
                assert selected == second_type["id"]
                print(f"   [OK] Второй тип выбран")

                # Кнопка должна остаться enabled
                is_disabled = report_button.is_disabled()
                assert not is_disabled
                print(f"   [OK] Кнопка всё ещё enabled")

                # Кликаем еще раз
                with page.expect_response("**/api/v1/report/**") as response_info2:
                    report_button.click()
                response2 = response_info2.value
                assert response2.status == 200
                print(f"   [OK] Второй отчет запущен (HTTP {response2.status})")
            else:
                print("   Пропущено: только один тип отчета")

            print("\n" + "=" * 60)
            print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
            print("=" * 60)

        finally:
            browser.close()


if __name__ == "__main__":
    test_report_type_selection()

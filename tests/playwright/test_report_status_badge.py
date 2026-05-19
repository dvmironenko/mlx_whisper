"""Playwright-тест: бейдж статуса генерации отчёта в карточке задания."""

from playwright.sync_api import sync_playwright, Page

BASE_URL = "http://localhost:8801"


def wait_for_selector(page: Page, selector: str, timeout: int = 30000) -> bool:
    """Ждать появления селектора."""
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return True
    except Exception:
        return False


def test_report_status_badge():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        print("=" * 60)
        print("ТЕСТ: Бейдж статуса генерации отчёта")
        print("=" * 60)

        try:
            # 1. Загрузка страницы
            print("\n1. Загрузка страницы...")
            page.goto(BASE_URL)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            print(f"   URL: {page.url}")

            # 2. Проверка endpoint report-status
            print("\n2. Проверка endpoint /api/v1/report-status/...")
            status_resp = page.evaluate("""
                () => fetch('/api/v1/report-status/test-job').then(r => r.json())
            """)
            assert status_resp["job_id"] == "test-job"
            assert status_resp["status"] == "idle"
            print(f"   [OK] Endpoint работает, статус: {status_resp['status']}")

            # 3. Проверка CSS класса report-status-badge
            print("\n3. Проверка CSS класса report-status-badge...")
            css_loaded = page.evaluate("""
                () => {
                    for (const sheet of document.styleSheets) {
                        try {
                            for (const rule of sheet.cssRules) {
                                if (rule.selectorText === '.report-status-badge') return true;
                            }
                        } catch(e) {}
                    }
                    return false;
                }
            """)
            assert css_loaded, "CSS класс .report-status-badge не найден"
            print("   [OK] CSS класс найден в стилях")

            # 4. Проверка JS переменных
            print("\n4. Проверка JS переменных...")
            has_reportingJobs = page.evaluate("() => typeof reportingJobs !== 'undefined'")
            has_pollReportStatuses = page.evaluate("() => typeof pollReportStatuses === 'function'")
            has_updateReportBadges = page.evaluate("() => typeof updateReportBadges === 'function'")
            assert has_reportingJobs, "reportingJobs Set не найден"
            assert has_pollReportStatuses, "pollReportStatuses не найден"
            assert has_updateReportBadges, "updateReportBadges не найден"
            print("   [OK] reportingJobs Set найден")
            print("   [OK] pollReportStatuses функция найдена")
            print("   [OK] updateReportBadges функция найдена")

            # 5. Проверка генерации отчёта на реальном job
            print("\n5. Поиск завершенной задачи для генерации отчёта...")
            page.goto(BASE_URL)
            page.wait_for_timeout(3000)

            # Ищем первую завершенную задачу
            report_buttons = page.locator("button.btn-report-job").all()
            target_card_id = None
            for btn in report_buttons:
                card = btn.evaluate_handle("el => el.closest('.job-card')")
                if card:
                    card_id = card.get_attribute("data-job-id")
                    if card_id:
                        target_card_id = card_id
                        break

            print(f"   Выбрана задача: {target_card_id}")
            assert target_card_id, "Нет завершенных задач для теста"

            # 6. Выбор типа отчёта и нажатие кнопки
            print(f"\n6. Выбор типа отчёта и нажатие кнопки на задаче {target_card_id}...")
            first_card = page.locator(f".job-card[data-job-id='{target_card_id}']")
            report_btn = first_card.locator("button.btn-report-job")
            select = first_card.locator("select")

            # Выбираем тип отчёта (index=1 — первый реальный тип, index=0 — placeholder)
            select.select_option(index=1)
            page.wait_for_timeout(500)

            # Ловим сетевой запрос
            with page.expect_response("**/api/v1/report/**") as response_info:
                report_btn.click()

            response = response_info.value
            assert response.status == 200, f"Ожидался 200, got {response.status}"
            print(f"   [OK] API вернул {response.status}")

            # 7. Проверка, что кнопка стала disabled
            print("\n7. Проверка disabled состояния кнопки...")
            page.wait_for_timeout(2000)
            is_disabled = report_btn.is_disabled()
            print(f"   Кнопка disabled: {is_disabled}")
            assert is_disabled, "Кнопка 'Отчет' должна быть disabled после нажатия"
            print("   [OK] Кнопка disabled")

            # 8. Проверка появления бейджа
            print("\n8. Проверка появления бейджа статуса...")
            badge_visible = wait_for_selector(page, ".report-status-badge", timeout=15000)
            assert badge_visible, "Бейдж .report-status-badge не появился"
            print("   [OK] Бейдж появился")

            # 9. Проверка содержимого бейджа
            print("\n9. Проверка содержимого бейджа...")
            badge_text = page.locator(".report-status-badge").first.text_content() or ""
            print(f"   Текст бейджа: '{badge_text}'")
            assert "Отчет" in badge_text, f"Ожидалось 'Отчет' в бейдже, got '{badge_text}'"
            print("   [OK] Бейдж содержит текст 'Отчет'")

            # 10. Проверка CSS стилей бейджа
            print("\n10. Проверка CSS стилей бейджа...")
            badge_color = page.locator(".report-status-badge").first.evaluate("""
                el => getComputedStyle(el).color
            """)
            print(f"   Цвет бейджа: {badge_color}")
            assert badge_color, "Цвет бейджа не определён"
            print("   [OK] CSS стили применены")

            # 11. Проверка анимации иконки
            print("\n11. Проверка иконки с анимацией...")
            icon_exists = page.locator(".report-status-badge .fa-file-circle-notch").count() > 0
            icon_spinning = page.locator(".report-status-badge .fa-file-circle-notch.fa-spin").count() > 0
            print(f"   Иконка .fa-file-circle-notch: {icon_exists}")
            print(f"   Иконка .fa-spin: {icon_spinning}")
            assert icon_exists, "Иконка fa-file-circle-notch не найдена"
            assert icon_spinning, "Класс fa-spin не найден"
            print("   [OK] Иконка с анимацией найдена")

            # 12. Проверка удаления бейджа после завершения
            print("\n12. Проверка удаления бейджа (симуляция завершения)...")
            # Удаляем job из reportingJobs через JS
            page.evaluate(f"""
                () => {{
                    reportingJobs = new Set([...reportingJobs].filter(id => id !== '{target_card_id}'));
                    updateReportBadges();
                }}
            """)
            page.wait_for_timeout(1000)
            badge_gone = page.locator(".report-status-badge").count() == 0
            print(f"   Бейдж удалён: {badge_gone}")
            assert badge_gone, "Бейдж должен быть удалён"
            print("   [OK] Бейдж удалён")

            # 13. Проверка восстановления кнопки
            print("\n13. Проверка восстановления кнопки...")
            # Кнопка должна быть enabled, т.к. тип отчёта выбран
            select_value = select.evaluate("el => el.value")
            is_disabled_after = report_btn.is_disabled()
            print(f"   Выбранный тип: '{select_value}', disabled: {is_disabled_after}")
            assert not is_disabled_after, "Кнопка должна быть enabled при выбранном типе"
            print("   [OK] Кнопка восстановлена")

            print("\n" + "=" * 60)
            print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
            print("=" * 60)

        finally:
            browser.close()


if __name__ == "__main__":
    test_report_status_badge()

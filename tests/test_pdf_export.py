from __future__ import annotations

from app.pdf_export import prepare_readable_markdown_for_pdf


def test_prepare_readable_markdown_for_pdf_strips_readable_scaffold() -> None:
    markdown_text = (
        "# Читабельный текст\n\n"
        "- Файл: `Лекция 01.mp4`\n"
        "- Модель: `medium`\n"
        "- Язык: `ru`\n"
        "- Создано: `2026-04-16 18:10:48`\n\n"
        "## Текст\n\n"
        "Первый абзац.\n\n"
        "Второй **абзац**.\n"
    )

    title, body = prepare_readable_markdown_for_pdf(markdown_text, fallback_title="fallback.mp4")

    assert title == "Лекция 01.mp4"
    assert body == "Первый абзац.\n\nВторой **абзац**."


def test_prepare_readable_markdown_for_pdf_falls_back_to_original_title() -> None:
    markdown_text = "Пользователь полностью переписал документ.\n\nБез служебной шапки.\n"

    title, body = prepare_readable_markdown_for_pdf(markdown_text, fallback_title="original.mp4")

    assert title == "original.mp4"
    assert body == "Пользователь полностью переписал документ.\n\nБез служебной шапки."

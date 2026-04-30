"""Генерация Markdown отчётов по расшифровке через OpenAI API."""

import os
import time
from typing import Optional, List

from openai import AsyncOpenAI, OpenAI

from src.config import logger, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_REPORT_PROMPT, OPENAI_BASE_URL, MAX_REPORT_CHUNK_SIZE

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None
    logger.warning("langchain-text-splitters не установлен. Установите: pip install langchain-text-splitters>=0.3.0")


def load_segments_file(job_path: str) -> Optional[str]:
    """
    Загрузить segments.txt из директории job_id.

    Parameters
    ----------
    job_path: str
        Путь к директории задания (data/{job_id}/)

    Returns
    -------
    Optional[str]
        Содержимое файла или None если не найден
    """
    segments_file = None
    for filename in os.listdir(job_path):
        if filename.endswith("_segments.txt"):
            segments_file = os.path.join(job_path, filename)
            break

    if segments_file is None:
        logger.warning(f"No segments.txt found in {job_path}")
        return None

    try:
        with open(segments_file, "r", encoding="utf-8") as f:
            content = f.read()
            logger.info(f"Loaded segments file: {segments_file}, length: {len(content)} chars")
            return content
    except Exception as e:
        logger.error(f"Failed to load segments file {segments_file}: {e}")
        return None


def split_text(text: str, max_chunk: Optional[int] = None) -> List[str]:
    """
    Разбить текст на части не более max_chunk символов с помощью
    RecursiveCharacterTextSplitter из LangChain.

    Parameters
    ----------
    text: str
        Текст для разбивки
    max_chunk: Optional[int]
        Максимальный размер части в символах (default: MAX_REPORT_CHUNK_SIZE из config)

    Returns
    -------
    List[str]
        Список частей текста
    """
    if max_chunk is None:
        max_chunk = MAX_REPORT_CHUNK_SIZE

    if RecursiveCharacterTextSplitter is None:
        logger.error(
            "langchain-text-splitters не установлен. Установите: pip install langchain-text-splitters>=0.3.0"
        )
        raise RuntimeError(
            "langchain-text-splitters не установлен. Установите: pip install langchain-text-splitters>=0.3.0"
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk,
        chunk_overlap=0,
        length_function=len,
        is_separator_regex=False,
    )
    return splitter.split_text(text)


def build_prompt(text: str, custom_prompt: Optional[str] = None) -> str:
    """
    Собрать финальный промпт для OpenAI.

    Parameters
    ----------
    text: str
        Текст транскрипции из segments.txt
    custom_prompt: Optional[str]
        Пользовательский промпт или None для использования дефолтного

    Returns
    -------
    str
        Полный промпт для отправки в OpenAI
    """
    base_prompt = custom_prompt or OPENAI_REPORT_PROMPT or "Создать отчет о сессии."
    return f"""{base_prompt}

Транскрипция:
{text}"""


async def generate_report_via_openai(text: str, prompt: Optional[str] = None) -> str:
    """
    Отправить на OpenAI и получить Markdown отчёт.

    Parameters
    ----------
    text: str
        Текст транскрипции для анализа
    prompt: Optional[str]
        Пользовательский промпт или None для использования дефолтного

    Returns
    -------
    str
        Сгенерированный Markdown отчёт

    Raises
    ------
    ValueError
        Если не задан OPENAI_API_KEY
    Exception
        Если API вызов не удался
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY не задана. Установите переменную окружения OPENAI_API_KEY"
        )

    client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    base_prompt = prompt or OPENAI_REPORT_PROMPT or "Создать отчет о сессии."

    logger.info(f"Sending report request to OpenAI model: {OPENAI_MODEL}")
    logger.debug(f"Base prompt length: {len(base_prompt)} chars, text length: {len(text)} chars")

    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": f"{base_prompt}\n\nВыводи только Markdown без дополнительных пояснений.",
                },
                {"role": "user", "content": f"Транскрипция:\n{text}"},
            ],
            temperature=0.7,
        )

        content = response.choices[0].message.content or ""
        logger.info(f"OpenAI API call successful. Response length: {len(content)} chars")

        return content

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise


def save_report(job_path: str, job_id: str, content: str) -> str:
    """
    Сохранить "Отчет по заданию [Job Id].md" в директории задания.

    Parameters
    ----------
    job_path: str
        Путь к директории задания (data/{job_id}/)
    job_id: str
        ID задания для именования файла
    content: str
        Содержимое Markdown отчёта

    Returns
    -------
    str
        Путь к сохраненному файлу
    """
    report_filename = f"Отчет по заданию {job_id}.md"
    report_path = os.path.join(job_path, report_filename)

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Report saved: {report_path}, length: {len(content)} chars")

        return report_path
    except Exception as e:
        logger.error(f"Failed to save report {report_path}: {e}")
        raise


def generate_report_via_openai_sync(text: str, prompt: Optional[str] = None) -> str:
    """
    Синхронная генерация Markdown отчёта через OpenAI API.
    Текст разбивается на части до 10000 символов и генерируется отчёт для каждой части.

    Parameters
    ----------
    text: str
        Текст транскрипции для анализа
    prompt: Optional[str]
        Пользовательский промпт или None для использования дефолтного

    Returns
    -------
    str
        Сгенерированный Markdown отчёт (конкатенация частей)

    Raises
    ------
    ValueError
        Если не задан OPENAI_API_KEY
    Exception
        Если API вызов не удался
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY не задана. Установите переменную окружения OPENAI_API_KEY"
        )

    # Разбить текст на части не более MAX_REPORT_CHUNK_SIZE символов
    chunks = split_text(text)
    logger.info(f"Split text into {len(chunks)} chunks for report generation")

    # Вывод чанков для тестирования
    print("\n" + "=" * 80)
    print(f"ТЕСТ: Текст разбит на {len(chunks)} чанков для отправки в LLM")
    print("=" * 80)
    for i, chunk in enumerate(chunks):
        preview = chunk[:200] + "..." if len(chunk) > 200 else chunk
        print(f"\n--- ЧАНК {i + 1}/{len(chunks)} (длина: {len(chunk)} символов) ---")
        print(preview)
    print("\n" + "=" * 80 + "\n")

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    all_reports = []
    total_start = time.time()

    base_prompt = prompt or OPENAI_REPORT_PROMPT or "Создать отчет о сессии."

    for i, chunk in enumerate(chunks):
        logger.info(f"Sending report request to OpenAI model: {OPENAI_MODEL} (chunk {i + 1}/{len(chunks)})")
        logger.debug(f"Base prompt length: {len(base_prompt)} chars, chunk length: {len(chunk)} chars")

        chunk_start = time.time()
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"{base_prompt}\n\nВыводи только Markdown без дополнительных пояснений.",
                    },
                    {"role": "user", "content": f"Транскрипция:\n{chunk}"},
                ],
                temperature=0.7,
            )

            content = response.choices[0].message.content or ""
            chunk_elapsed = time.time() - chunk_start
            logger.info(f"OpenAI API call successful. Response length: {len(content)} chars")
            logger.info(f"Chunk {i + 1}/{len(chunks)} processed in {chunk_elapsed:.2f} seconds")

            all_reports.append(content)

        except Exception as e:
            logger.error(f"OpenAI API error for chunk {i + 1}: {e}")
            raise

    total_elapsed = time.time() - total_start
    logger.info(f"Report generation completed in {total_elapsed:.2f} seconds")

    # Конкатенация результатов
    return "".join(all_reports)

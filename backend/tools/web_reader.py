"""
Web Content Reader - читает и извлекает текст из веб-страниц

Используется после web_search для получения ПОЛНОГО содержимого страниц,
а не только snippets.

Features:
- Чтение HTML страниц
- Извлечение основного контента (убирает навигацию, рекламу)
- Обработка ошибок (timeout, 404, blocked)
- Rate limiting
- Smart chunking с приоритизацией по keywords
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import Optional, Dict, List, Set
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)

from backend.core.web_utils import clean_ui_artifacts


def smart_chunk_content(
    text: str, 
    query_words: Set[str], 
    max_chars: int,
    paragraph_separator: str = "\n\n"
) -> Dict[str, any]:
    """
    Умный chunking контента с приоритизацией по keywords.
    
    Стратегия:
    1. Разбить текст на параграфы
    2. Оценить релевантность каждого параграфа (keyword matching)
    3. Выбрать самые релевантные параграфы до max_chars
    4. Вернуть текст + metadata (% показанного контента)
    
    :param text: Полный текст для chunking
    :param query_words: Множество ключевых слов из запроса
    :param max_chars: Максимальное количество символов
    :param paragraph_separator: Разделитель параграфов
    :return: Dict с полями content, coverage, num_paragraphs, truncated
    """
    if len(text) <= max_chars:
        # Текст влезает целиком
        return {
            "content": text,
            "coverage": 1.0,
            "num_paragraphs": text.count(paragraph_separator) + 1,
            "truncated": False
        }
    
    # Разбить на параграфы
    paragraphs = text.split(paragraph_separator)
    paragraphs = [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 20]
    
    if not paragraphs:
        # Fallback: просто обрезать текст
        return {
            "content": text[:max_chars] + "...",
            "coverage": max_chars / len(text),
            "num_paragraphs": 1,
            "truncated": True
        }
    
    # Оценить релевантность каждого параграфа
    scored_paragraphs = []
    for para in paragraphs:
        score = _calculate_paragraph_relevance(para, query_words)
        scored_paragraphs.append((score, para))
    
    # Отсортировать по релевантности (больше = лучше)
    scored_paragraphs.sort(reverse=True, key=lambda x: x[0])
    
    # Собрать топ параграфы до max_chars
    selected_paragraphs = []
    current_length = 0
    
    for score, para in scored_paragraphs:
        para_length = len(para) + len(paragraph_separator)
        if current_length + para_length <= max_chars:
            selected_paragraphs.append(para)
            current_length += para_length
        elif current_length < max_chars * 0.8:  # Если использовали меньше 80% - добавить частично
            remaining = max_chars - current_length - 50  # Reserve for "..."
            if remaining > 100:
                selected_paragraphs.append(para[:remaining] + "...")
                current_length = max_chars
                break
        else:
            break
    
    # Собрать финальный текст
    final_content = paragraph_separator.join(selected_paragraphs)
    coverage = len(final_content) / len(text)
    
    return {
        "content": final_content,
        "coverage": coverage,
        "num_paragraphs": len(selected_paragraphs),
        "truncated": True
    }


def _calculate_paragraph_relevance(paragraph: str, query_words: Set[str]) -> float:
    """
    Оцениваем релевантность параграфа.
    
    Критерии:
    - Количество совпадающих ключевых слов
    - Плотность ключевых слов (keyword density)
    - Длина параграфа (не слишком короткий, не слишком длинный)
    
    :param paragraph: Текст параграфа
    :param query_words: Ключевые слова для поиска
    :return: Оценка релевантности (чем выше, тем лучше)
    """
    score = 0.0
    
    # Нормализовать текст
    para_lower = paragraph.lower()
    para_words = set(re.findall(r'\w+', para_lower))
    
    # 1. Количество совпадающих keywords
    matching_words = query_words & para_words
    score += len(matching_words) * 10.0
    
    # 2. Бонус за несколько вхождений одного keyword
    for keyword in matching_words:
        occurrences = para_lower.count(keyword)
        if occurrences > 1:
            score += (occurrences - 1) * 2.0
    
    # 3. Длина параграфа (оптимум: 200-800 символов)
    para_len = len(paragraph)
    if 200 <= para_len <= 800:
        score += 5.0
    elif para_len > 800:
        score += 2.0  # Длинные параграфы тоже ок, но менее приоритетны
    elif para_len < 100:
        score -= 3.0  # Слишком короткие - штраф
    
    # 4. Бонус если параграф начинается с заголовочных слов
    header_indicators = ['introduction', 'overview', 'summary', 'conclusion', 
                        'введение', 'обзор', 'резюме', 'заключение']
    if any(para_lower.startswith(indicator) for indicator in header_indicators):
        score += 3.0
    
    return score


class WebReader:
    """
    Читает содержимое веб-страниц и извлекает основной текст.
    
    Использует requests + BeautifulSoup для парсинга.
    Извлекает: title, main_text, meta_description.
    """
    
    def __init__(self, timeout: int = 10, rate_limit: float = 1.0):
        """
        Инициализируем WebReader.
        
        :param timeout: Таймаут запроса в секундах (default: 10)
        :param rate_limit: Пауза между запросами в секундах (default: 1.0)
        """
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
        # User-Agent для обхода простых блокировок
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def read_url(self, url: str) -> Dict[str, str]:
        """
        Читаем содержимое URL.
        
        :param url: URL страницы для чтения
        :return: Dict с полями: url, title, main_text, meta_description, status, error
        """
        # Rate limiting - пауза между запросами
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        
        self.last_request_time = time.time()
        
        try:
            logger.info(f"Reading URL: {url}")
            
            # Загрузить страницу
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Парсинг HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Извлечь заголовок
            title = ""
            if soup.title:
                title = soup.title.string.strip() if soup.title.string else ""
            elif soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            
            # Извлечь meta description
            meta_desc = ""
            meta_tag = soup.find('meta', attrs={'name': 'description'}) or \
                      soup.find('meta', attrs={'property': 'og:description'})
            if meta_tag and meta_tag.get('content'):
                meta_desc = meta_tag.get('content').strip()
            
            # Извлечь основной текст
            main_text = self._extract_main_text(soup)
            
            # НЕ обрезаем здесь - это будет сделано в dialog agent с учетом LLM лимитов
            # Но установим разумный максимум на уровне web reader для защиты
            original_length = len(main_text)
            max_reader_limit = 50000  # 50K символов - защита от огромных страниц
            
            if len(main_text) > max_reader_limit:
                main_text = main_text[:max_reader_limit]
                logger.warning(f"Page content exceeds {max_reader_limit} chars, truncated from {original_length}")
            
            logger.info(f"Successfully read {len(main_text)} characters from {url}")
            
            return {
                "url": url,
                "title": title,
                "main_text": main_text,
                "meta_description": meta_desc,
                "status": "success",
                "length": len(main_text)
            }
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout reading {url}")
            return {
                "url": url,
                "status": "error",
                "error": "Timeout - page took too long to load"
            }
        
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error reading {url}: {e}")
            return {
                "url": url,
                "status": "error",
                "error": f"HTTP {response.status_code} - {e}"
            }
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error reading {url}: {e}")
            return {
                "url": url,
                "status": "error",
                "error": f"Network error - {str(e)}"
            }
        
        except Exception as e:
            logger.error(f"Unexpected error reading {url}: {e}")
            return {
                "url": url,
                "status": "error",
                "error": f"Parse error - {str(e)}"
            }
    
    def _extract_main_text(self, soup: BeautifulSoup) -> str:
        """
        Извлекаем основной текст из HTML, убирая навигацию и рекламу.
        
        Стратегия:
        1. Удалить ненужные теги (script, style, nav, footer, ads)
        2. Искать основной контент в <article>, <main>, или <div class="content">
        3. Извлечь текст из параграфов
        """
        # Удалить ненужные элементы
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
            tag.decompose()
        
        # Удалить рекламные блоки по class/id
        for ad_class in ['ad', 'ads', 'advertisement', 'promo', 'sponsored']:
            for element in soup.find_all(class_=lambda x: x and ad_class in x.lower()):
                element.decompose()
            for element in soup.find_all(id=lambda x: x and ad_class in x.lower()):
                element.decompose()
        
        # Попытаться найти основной контент
        main_content = None
        
        # Вариант 1: <article> тег (часто используется в блогах)
        main_content = soup.find('article')
        
        # Вариант 2: <main> тег (HTML5 semantic)
        if not main_content:
            main_content = soup.find('main')
        
        # Вариант 3: div с классом content/main/post
        if not main_content:
            for class_name in ['content', 'main-content', 'post-content', 'entry-content', 'article-body']:
                main_content = soup.find('div', class_=lambda x: x and class_name in x.lower())
                if main_content:
                    break
        
        # Вариант 4: весь body (fallback)
        if not main_content:
            main_content = soup.find('body')
        
        if not main_content:
            # Если ничего не нашли - вернуть весь текст
            return soup.get_text(separator=' ', strip=True)
        
        # Извлечь текст из найденного контента
        # Собираем текст из параграфов, заголовков, списков
        text_parts = []
        for element in main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote']):
            text = element.get_text(strip=True)
            if text and len(text) > 20:  # Игнорировать очень короткие строки
                text_parts.append(text)
        
        # Если параграфы не нашли - взять весь текст
        if not text_parts:
            return main_content.get_text(separator=' ', strip=True)
        
        return '\n\n'.join(text_parts)
    
    def read_multiple_urls(self, urls: list, max_urls: int = 3) -> list:
        """
        Читаем несколько URL.
        
        :param urls: Список URL для чтения
        :param max_urls: Максимум URL для чтения (default: 3)
        :return: Список результатов read_url()
        """
        results = []
        
        for url in urls[:max_urls]:
            result = self.read_url(url)
            results.append(result)
            
            # Если слишком много ошибок подряд - остановиться
            if len(results) >= 2:
                recent_errors = sum(1 for r in results[-2:] if r['status'] == 'error')
                if recent_errors == 2:
                    logger.warning("Too many consecutive errors, stopping reads")
                    break
        
        return results


def format_read_results(results: list) -> str:
    """
    Форматируем результаты чтения для отображения.
    
    :param results: Список результатов из read_multiple_urls()
    :return: Отформатированная строка с содержимым
    """
    if not results:
        return "⚠️ **No content read** - Failed to read any URLs."
    
    formatted = f"📖 **Read {len(results)} pages:**\n\n"
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = len(results) - success_count
    
    if error_count > 0:
        formatted += f"*(Successfully read {success_count}/{len(results)} pages)*\n\n"
    
    for i, result in enumerate(results, 1):
        if result['status'] == 'error':
            formatted += f"**{i}. ❌ {result['url']}**\n"
            formatted += f"   Error: {result['error']}\n\n"
        else:
            title = result.get('title', 'No title')
            text = result.get('main_text', '')
            
            formatted += f"**{i}. ✅ {title}**\n"
            formatted += f"   🔗 {result['url']}\n"
            
            # Показать первые 500 символов для preview
            preview = text[:500] + "..." if len(text) > 500 else text
            formatted += f"   📄 Content preview:\n   {preview}\n\n"
    
    return clean_ui_artifacts(formatted)


# Singleton instance
_web_reader = None

def get_web_reader() -> WebReader:
    """Получаем singleton экземпляр WebReader"""
    global _web_reader
    if _web_reader is None:
        _web_reader = WebReader(timeout=10, rate_limit=1.0)
    return _web_reader


def read_url(url: str) -> Dict[str, str]:
    """
    Удобная функция для чтения одного URL.
    :param url: URL
    :return: результат чтения
    """
    reader = get_web_reader()
    return reader.read_url(url)


def read_multiple_urls(urls: list, max_urls: int = 3) -> list:
    """
    Удобная функция для чтения нескольких URL.
    :param urls: список URL
    :param max_urls: лимит
    :return: список результатов
    """
    reader = get_web_reader()
    return reader.read_multiple_urls(urls, max_urls)

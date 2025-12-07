"""Web search tool using DuckDuckGo"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

from backend.core.web_utils import clean_ui_artifacts


def duckduckgo_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Выполняем поиск в DuckDuckGo.
    
    :param query: поисковый запрос
    :param max_results: максимальное количество результатов
    :return: список результатов с полями title, url, snippet, search_time
    """
    import time
    
    try:
        from ddgs import DDGS
        
        logger.info(f"Searching DuckDuckGo for: {query}")
        start_time = time.time()
        
        results = []
        with DDGS() as ddgs:
            search_results = ddgs.text(query, max_results=max_results)
            
            for r in search_results:
                results.append({
                    'title': r.get('title', ''),
                    'url': r.get('href', ''),
                    'snippet': r.get('body', '')
                })
        
        search_time = time.time() - start_time
        
        # Добавить время поиска к каждому результату
        for r in results:
            r['search_time'] = search_time
        
        logger.info(f"Found {len(results)} results in {search_time:.2f}s")
        return results
        
    except ImportError:
        logger.error("ddgs library not installed. Run: pip install ddgs")
        return []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


def format_search_results(results: List[Dict[str, str]]) -> str:
    """
    Форматируем результаты поиска в читаемый текст для LLM.
    
    :param results: список словарей с результатами
    :return: отформатированная строка
    """
    if not results:
        return "⚠️ **No results found** - Search returned 0 results. Cannot provide information on this query."
    
    search_time = results[0].get('search_time', 0) if results else 0
    
    formatted = f"🔍 **Search Results** (Found {len(results)} results in {search_time:.2f}s):\n\n"
    
    for i, result in enumerate(results, 1):
        title = result.get('title', 'No title')
        url = result.get('url', '')
        snippet = result.get('snippet', 'No description')
        
        formatted += f"{i}. **{title}**\n"
        formatted += f"   📎 {url}\n"
        formatted += f"   📝 {snippet[:200]}{'...' if len(snippet) > 200 else ''}\n\n"
    
    return clean_ui_artifacts(formatted)
    
    search_time = results[0].get('search_time', 0) if results else 0
    
    formatted = f"🔍 **Search Results** (Found {len(results)} results in {search_time:.2f}s):\n\n"
    
    for i, result in enumerate(results, 1):
        title = result.get('title', 'No title')
        url = result.get('url', '')
        snippet = result.get('snippet', 'No description')
        
        formatted += f"{i}. **{title}**\n"
        formatted += f"   📎 {url}\n"
        formatted += f"   📝 {snippet[:200]}{'...' if len(snippet) > 200 else ''}\n\n"
    
    return formatted

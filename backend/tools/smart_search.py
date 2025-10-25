"""
Smart Multi-Step Search Tool
Умный поиск БЕЗ API keys, только через DuckDuckGo
"""

from typing import List, Dict, Optional
import logging
import hashlib
import time
import re
from .web_search import duckduckgo_search

logger = logging.getLogger(__name__)

from backend.core.web_utils import clean_ui_artifacts

# Глобальный кеш для результатов поиска (живет в рамках сессии приложения)
_search_cache = {}
_cache_max_age = 600  # 10 минут


class SmartSearch:
    """
    Умный многоступенчатый поисковик
    
    Возможности:
    - Целевой поиск по конкретным сайтам (GitHub, StackOverflow, Reddit)
    - Многоступенчатый поиск (если первые результаты плохие - ищет по-другому)
    - Анализ качества результатов
    - LLM-driven переформулировка запросов (агент САМ думает как искать)
    """
    
    def __init__(self, llm_provider=None):
        self.max_steps = 5  # Увеличено до 5 раундов для лучшего покрытия
        self.results_per_step = 5
        self.llm_provider = llm_provider  # Для умной генерации запросов
        self.use_cache = True  # Включить кеширование
    
    def _get_cache_key(self, query: str, target: Optional[str]) -> str:
        """Создать ключ кеша для запроса"""
        cache_str = f"{query.lower()}:{target or 'none'}"
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _get_from_cache(self, query: str, target: Optional[str]) -> Optional[List[Dict]]:
        """Получить результаты из кеша если есть и не устарели"""
        if not self.use_cache:
            return None
        
        cache_key = self._get_cache_key(query, target)
        if cache_key in _search_cache:
            cached_data = _search_cache[cache_key]
            age = time.time() - cached_data['timestamp']
            
            if age < _cache_max_age:
                logger.info(f"Cache HIT for query '{query[:30]}...' (age: {age:.1f}s)")
                return cached_data['results']
            else:
                # Устаревший кеш - удалить
                del _search_cache[cache_key]
                logger.debug(f"Cache expired for query '{query[:30]}...'")
        
        return None
    
    def _save_to_cache(self, query: str, target: Optional[str], results: List[Dict]):
        """Сохранить результаты в кеш"""
        if not self.use_cache:
            return
        
        cache_key = self._get_cache_key(query, target)
        _search_cache[cache_key] = {
            'results': results,
            'timestamp': time.time()
        }
        logger.debug(f"Saved to cache: query '{query[:30]}...'")
        
        # Ограничить размер кеша (максимум 100 записей)
        if len(_search_cache) > 100:
            # Удалить самую старую запись
            oldest_key = min(_search_cache.keys(), key=lambda k: _search_cache[k]['timestamp'])
            del _search_cache[oldest_key]
            logger.debug("Cache size limit reached, removed oldest entry")
    
    def search(
        self,
        query: str,
        target: Optional[str] = None,
        deep: bool = True
    ) -> Dict:
        """
        Выполнить умный поиск
        
        Args:
            query: Поисковый запрос
            target: Целевой сайт ("github", "stackoverflow", "reddit", None)
            deep: Использовать глубокий поиск (несколько раундов)
        
        Returns:
            Dict с результатами:
                - results: List[Dict] - найденные результаты
                - steps: int - количество шагов поиска
                - queries: List[str] - использованные запросы
        """
        logger.info(f"SmartSearch starting: query='{query}', target={target}, deep={deep}")
        
        # Проверить кеш сначала
        cached_results = self._get_from_cache(query, target)
        if cached_results is not None:
            return {
                "results": cached_results[:10],
                "steps": 0,
                "queries": [query],
                "total_found": len(cached_results),
                "from_cache": True
            }
        
        all_results = []
        queries_used = []
        seen_urls = set()
        step = 0
        
        # Шаг 1: Основной поиск
        primary_query = self._build_query(query, target)
        queries_used.append(primary_query)
        step += 1
        
        results = duckduckgo_search(primary_query, max_results=self.results_per_step)
        for r in results:
            if r.get('url') not in seen_urls:
                all_results.append(r)
                seen_urls.add(r.get('url'))
        
        logger.info(f"Step {step}: found {len(results)} results (unique: {len(all_results)})")
        
        # Если deep режим - продолжаем искать до max_steps или пока не наберем достаточно
        if deep and step < self.max_steps:
            # Определяем нужно ли продолжать
            unique_count = len(all_results)
            target_results = 7  # Целевое количество уникальных результатов
            
            iterations_without_new_results = 0  # Защита от зацикливания
            max_empty_iterations = 2  # Максимум 2 итерации без новых результатов
            
            while unique_count < target_results and step < self.max_steps and iterations_without_new_results < max_empty_iterations:
                results_before = unique_count
                
                # Генерировать новые варианты запросов
                if self.llm_provider and step >= 2:
                    # С шага 3+ используем LLM для генерации умных вариантов
                    new_queries = self._generate_query_variants(query, target, all_results)
                else:
                    # Первые 2 шага - используем rule-based (быстрее)
                    if step == 1:
                        new_queries = [self._reformulate_query(query, target)]
                    elif step == 2 and target:
                        # Убрать site: фильтр для более широкого поиска
                        new_queries = [query]
                    else:
                        break  # Нет больше правил
                
                # Попробовать каждый новый запрос
                for new_query in new_queries:
                    if new_query in queries_used:
                        continue  # Уже пробовали
                    
                    if step >= self.max_steps:
                        break
                    
                    queries_used.append(new_query)
                    step += 1
                    
                    new_results = duckduckgo_search(new_query, max_results=self.results_per_step)
                    added = 0
                    for r in new_results:
                        if r.get('url') not in seen_urls:
                            all_results.append(r)
                            seen_urls.add(r.get('url'))
                            added += 1
                    
                    logger.debug(f"Step {step}: query='{new_query[:50]}...', found {len(new_results)} ({added} new unique)")
                
                # Проверить добавились ли новые результаты
                unique_count = len(all_results)
                if unique_count == results_before:
                    iterations_without_new_results += 1
                    logger.debug(f"No new results added, iteration {iterations_without_new_results}/{max_empty_iterations}")
                else:
                    iterations_without_new_results = 0
        
        # Отсортировать по релевантности
        ranked_results = self._rank_results(all_results, query, target)
        
        # Сохранить в кеш
        self._save_to_cache(query, target, ranked_results[:10])
        
        logger.info(f"SmartSearch complete: {len(ranked_results)} unique results from {step} steps")
        
        return {
            "results": ranked_results[:10],  # Топ-10
            "steps": step,
            "queries": queries_used,
            "total_found": len(all_results),
            "from_cache": False
        }
    
    def _build_query(self, query: str, target: Optional[str]) -> str:
        """Построить целевой запрос"""
        if not target:
            return query
        
        # Целевые сайты
        site_map = {
            "github": "site:github.com",
            "stackoverflow": "site:stackoverflow.com",
            "reddit": "site:reddit.com",
            "arxiv": "site:arxiv.org",
            "medium": "site:medium.com",
            "docs": "site:readthedocs.io OR site:docs.python.org"
        }
        
        site_filter = site_map.get(target.lower(), "")
        if site_filter:
            return f"{query} {site_filter}"
        
        return query
    
    def _generate_query_variants(
        self,
        original_query: str,
        target: Optional[str],
        current_results: List[Dict]
    ) -> List[str]:
        """
        Генерировать альтернативные варианты запроса используя LLM
        
        LLM анализирует оригинальный запрос и текущие результаты,
        затем предлагает 2-3 альтернативных формулировки
        """
        if not self.llm_provider:
            # Fallback на rule-based если нет LLM
            return [self._reformulate_query(original_query, target)]
        
        try:
            # Подготовить контекст для LLM
            results_preview = ""
            if current_results:
                results_preview = "Current results found:\n"
                for i, r in enumerate(current_results[:3], 1):
                    results_preview += f"{i}. {r.get('title', 'No title')}\n"
            else:
                results_preview = "No results found yet."
            
            target_hint = ""
            if target:
                target_hint = f"\nTarget site: {target}"
            
            # Промпт для LLM с JSON форматом (более надежный парсинг)
            prompt = f"""Generate 2-3 alternative search queries to find better results.

Original query: "{original_query}"{target_hint}

{results_preview}

Task: Create alternative search queries that:
- Use different keywords or synonyms
- Try different angles or aspects
- Are specific and focused
- Would work well in DuckDuckGo search

Respond with ONLY valid JSON array of strings, nothing else.
Example format:
["alternative query one", "another search variation", "third search option"]"""

            # Получить варианты от LLM
            response = self.llm_provider.generate(prompt, temperature=0.7)
            
            # Парсить JSON ответ
            variants = []
            try:
                import json
                # Попытка извлечь JSON из ответа (может быть обернут в ```json```)
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    if isinstance(parsed, list):
                        for item in parsed[:3]:  # Максимум 3
                            if isinstance(item, str) and len(item.strip()) > 3:
                                query = item.strip()
                                # Добавить site: фильтр если нужен
                                if target:
                                    query = self._build_query(query, target)
                                variants.append(query)
                        
                        if variants:
                            logger.info(f"LLM generated {len(variants)} query variants (JSON format)")
                            return variants[:3]
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse JSON from LLM, trying fallback parsing: {e}")
            
            # Fallback: plain text парсинг если JSON не удался
            for line in response.strip().split('\n'):
                line = line.strip()
                # Убрать markdown code blocks
                if line.startswith('```') or line.startswith('[') or line.startswith(']'):
                    continue
                # Убрать нумерацию если есть
                if line and not line.startswith('#'):
                    # Убрать "1. ", "- ", кавычки и т.д.
                    cleaned = re.sub(r'^[\d\.\-\)\s"]+', '', line).rstrip('",')
                    if cleaned and len(cleaned) > 3 and not cleaned.startswith('{'):
                        # Добавить site: фильтр если нужен
                        if target:
                            cleaned = self._build_query(cleaned, target)
                        variants.append(cleaned)
            
            if variants:
                logger.info(f"LLM generated {len(variants)} query variants")
                return variants[:3]  # Максимум 3 варианта
            
        except Exception as e:
            logger.error(f"Error generating query variants with LLM: {e}")
        
        # Fallback на rule-based
        return [self._reformulate_query(original_query, target)]
    
    def _reformulate_query(self, query: str, target: Optional[str]) -> str:
        """
        Переформулировать запрос для лучших результатов (rule-based fallback)
        
        Стратегии:
        - Добавить ключевые слова
        - Убрать лишние слова
        - Использовать синонимы
        """
        # Для GitHub: добавить технические термины
        if target == "github":
            if "repository" not in query.lower() and "repo" not in query.lower():
                query = f"{query} repository"
            if "implementation" not in query.lower():
                query = f"{query} implementation"
        
        # Для StackOverflow: добавить "how to" или "tutorial"
        elif target == "stackoverflow":
            if not any(word in query.lower() for word in ["how", "tutorial", "example"]):
                query = f"how to {query}"
        
        # Для Reddit: добавить "discussion" или "best"
        elif target == "reddit":
            if "discussion" not in query.lower():
                query = f"{query} discussion"
        
        return self._build_query(query, target)
    
    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        """Убрать дубликаты по URL"""
        seen_urls = set()
        unique = []
        
        for result in results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(result)
        
        return unique
    
    def _rank_results(
        self,
        results: List[Dict],
        query: str,
        target: Optional[str]
    ) -> List[Dict]:
        """
        Ранжировать результаты по релевантности
        
        Критерии:
        - Наличие ключевых слов в title/snippet
        - Популярность сайта
        - Актуальность (если есть дата)
        """
        query_words = set(query.lower().split())
        
        def calculate_score(result: Dict) -> float:
            score = 0.0
            
            title = result.get('title', '').lower()
            snippet = result.get('snippet', '').lower()
            url = result.get('url', '').lower()
            
            # Бонус за ключевые слова в заголовке
            title_words = set(title.split())
            matching_words = query_words & title_words
            score += len(matching_words) * 2.0
            
            # Бонус за ключевые слова в описании
            snippet_words = set(snippet.split())
            matching_snippet = query_words & snippet_words
            score += len(matching_snippet) * 1.0
            
            # Бонус за целевой сайт
            if target:
                site_map = {
                    "github": "github.com",
                    "stackoverflow": "stackoverflow.com",
                    "reddit": "reddit.com"
                }
                if site_map.get(target, "") in url:
                    score += 5.0
            
            # Популярные сайты
            if "github.com" in url:
                score += 3.0
            if "stackoverflow.com" in url:
                score += 2.5
            if "medium.com" in url or "towardsdatascience.com" in url:
                score += 2.0
            if "arxiv.org" in url:
                score += 3.5
            
            # Штраф за рекламные сайты
            spam_indicators = ["ad", "promo", "buy", "shop"]
            if any(spam in url for spam in spam_indicators):
                score -= 5.0
            
            return score
        
        # Добавить score к каждому результату
        for result in results:
            result['relevance_score'] = calculate_score(result)
        
        # Отсортировать по score (больше = лучше)
        return sorted(results, key=lambda x: x.get('relevance_score', 0), reverse=True)


def smart_search(
    query: str,
    target: Optional[str] = None,
    deep: bool = True,
    llm_provider=None
) -> Dict:
    """
    Удобная функция для быстрого умного поиска
    
    Args:
        query: Поисковый запрос
        target: Целевой сайт (github, stackoverflow, reddit, None)
        deep: Глубокий поиск (несколько раундов)
        llm_provider: LLM провайдер для умной генерации запросов (опционально)
    
    Returns:
        Dict с результатами
    
    Example:
        # Поиск на GitHub
        results = smart_search("reinforcement learning blackjack", target="github")
        
        # Общий поиск с углублением
        results = smart_search("best practices python async", deep=True)
        
        # Stack Overflow поиск
        results = smart_search("how to use asyncio", target="stackoverflow")
        
        # С LLM для умной генерации запросов
        results = smart_search("RL blackjack", target="github", llm_provider=llm)
    """
    searcher = SmartSearch(llm_provider=llm_provider)
    return searcher.search(query, target, deep)


def format_smart_results(search_result: Dict) -> str:
    """
    Форматировать результаты SmartSearch для отображения
    
    Args:
        search_result: Dict из smart_search()
    
    Returns:
        Отформатированная строка
    """
    results = search_result.get('results', [])
    steps = search_result.get('steps', 0)
    queries = search_result.get('queries', [])
    total_found = search_result.get('total_found', 0)
    
    if not results:
        return "⚠️ **No results found** - Smart search tried multiple queries but found nothing. Cannot provide information on this topic."
    
    formatted = f"🔍 **Smart Search Results** (Found {len(results)} unique results from {total_found} total, {steps} steps):\n\n"
    
    # Показать использованные запросы если несколько
    if len(queries) > 1:
        formatted += "📊 *Search strategy:*\n"
        for i, q in enumerate(queries, 1):
            formatted += f"  Step {i}: `{q}`\n"
        formatted += "\n"
    
    # Топ результаты
    for i, result in enumerate(results[:7], 1):  # Топ-7
        score = result.get('relevance_score', 0)
        title = result.get('title', 'No title')
        snippet = result.get('snippet', 'No description')
        url = result.get('url', '')
        
        # Эмодзи по релевантности
        relevance_badge = ""
        if score >= 5:
            relevance_badge = " 🔥"
        elif score >= 3:
            relevance_badge = " ⭐"
        
        formatted += f"{i}. **{title}**{relevance_badge}\n"
        formatted += f"   📎 {url}\n"
        formatted += f"   📝 {snippet[:180]}{'...' if len(snippet) > 180 else ''}\n\n"
    
    return clean_ui_artifacts(formatted)

"""
Dialog Agent - продвинутый чат-ассистент с ReAct подходом

Функции:
- Отвечает на вопросы
- Веб-поиск через DuckDuckGo + ЧТЕНИЕ содержимого страниц
- Может читать файлы из session/input/
- Может генерировать и выполнять Python код
- ReAct подход: Reasoning → Acting → Observation
"""
from backend.core.agent_framework import Agent
from backend.core.llm_provider import BaseLLMProvider
from backend.core.web_utils import clean_ui_artifacts
from backend.core.code_executor import LocalCodeExecutor
from backend.tools.web_search import duckduckgo_search, format_search_results
from backend.tools.smart_search import smart_search, format_smart_results
from backend.tools.web_reader import read_multiple_urls, format_read_results, smart_chunk_content
from pathlib import Path
import re
import logging
import datetime
from .prompts import DIALOG_INSTRUCTION

logger = logging.getLogger(__name__)


def create_dialog_agent(
    llm_provider: BaseLLMProvider,
    session_path: Path
) -> Agent:
    """Создаем Dialog Agent с веб-поиском."""
    
    code_executor = LocalCodeExecutor(session_path)

    def get_instruction_with_context(state):
        """Динамически добавляем дату, список файлов и статус поиска в промпт."""
        search_enabled = state.get("search_enabled", True)
        
        # Текущая дата и время UTC
        current_datetime = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Получить базовый промпт с учетом статуса поиска
        if search_enabled:
            base_instruction = DIALOG_INSTRUCTION.format(current_datetime=current_datetime)
        else:
            # Промпт БЕЗ инструкций по поиску
            base_instruction = f"""You are a helpful AI assistant with advanced capabilities.

**CURRENT DATE AND TIME:** {current_datetime}

**Core Capabilities:**
1. **Answer questions** - provide clear, accurate answers on any topic
2. **Read and analyze files** - work with files in ./input/ directory
3. **Generate and execute Python code** - analyze data, create visualizations, etc.

**NOTE: Web search is currently DISABLED by user. You cannot use SEARCH[] or SMART_SEARCH[] commands.**

**Data Analysis:**
Available Python libraries: pandas, numpy, matplotlib, seaborn, scikit-learn, xgboost, lightgbm

When analyzing data:
1. List available files
2. Load with pandas
3. Perform analysis
4. Show results clearly

**General Guidelines:**
- Be concise and helpful
- **CRITICAL: NEVER make up or hallucinate information!**
- If you don't know something, admit it honestly
- Show code when executing Python

Let's help the user effectively!"""
        
        # Добавить список файлов если есть
        input_files = list(Path(session_path / "input").glob("*"))
        if input_files:
            files_list = "\n".join([f"- {f.name}" for f in input_files])
            return f"{base_instruction}\n\n**Available Files in Current Session:**\n{files_list}"
        
        return base_instruction

    def before_run(state):
        """Выполняем обработку перед запуском агента."""
        logger.info(f"[DialogAgent] Starting new interaction")
        # Сохранить текущий user input для использования в after_run
        # (будет установлено в agent_framework.py перед вызовом before_callback)
    
    def after_run(state, response):
        """
        Обрабатываем ответ после получения (ITERATIVE multi-turn reasoning):
        1. Выполняем веб-поиск если нужно
        2. Читаем содержимое найденных страниц (ТОП-3)
        3. Делаем ВТОРОЙ ВЫЗОВ LLM для анализа прочитанного
        4. Если нужен еще раунд - повторяем (до 3 циклов)
        5. Возвращаем финальный ответ с источниками
        """
        
        # Проверить включен ли поиск
        search_enabled = state.get("search_enabled", True)
        
        # Инициализировать счетчик раундов (для iterative reasoning)
        current_round = state.get("reasoning_round", 0)
        
        search_results_text = ""
        read_content_text = ""
        cleaned_response = response
        all_urls_to_read = []
        
        # 1. Ищем паттерн SMART_SEARCH["query", "target"]
        smart_pattern = r'SMART_SEARCH\["([^"]+)"(?:,\s*"([^"]*)")?\]'
        smart_searches = re.findall(smart_pattern, response)
        
        if smart_searches and not search_enabled:
            # Поиск отключен, но LLM попытался использовать
            logger.warning("[DialogAgent] LLM attempted to use SMART_SEARCH but it's disabled by user")
            cleaned_response = re.sub(smart_pattern, '[Web search is disabled]', response)
        elif smart_searches and search_enabled:
            for query, target in smart_searches:
                target = target.strip() if target else None
                logger.info(f"[DialogAgent] Performing SMART search: query='{query}', target='{target}'")
                
                # Передаем llm_provider для умной генерации запросов
                result = smart_search(query, target=target, deep=True, llm_provider=llm_provider)
                formatted = format_smart_results(result)
                search_results_text += f"\n\n{formatted}"
                
                # Собрать URLs для чтения
                if result.get('results'):
                    urls = [r['url'] for r in result['results'][:3]]  # ТОП-3
                    all_urls_to_read.extend(urls)
            
            # Удалить SMART_SEARCH[] паттерны
            cleaned_response = re.sub(smart_pattern, '', response)
        
        # 2. Ищем паттерн обычного SEARCH["query"]  
        search_pattern = r'SEARCH\["([^"]+)"\]'
        searches = re.findall(search_pattern, response)
        
        if searches and not search_enabled:
            # Поиск отключен
            logger.warning("[DialogAgent] LLM attempted to use SEARCH but it's disabled by user")
            cleaned_response = re.sub(search_pattern, '[Web search is disabled]', cleaned_response)
        elif searches and search_enabled:
            for query in searches:
                logger.info(f"[DialogAgent] Performing quick search: {query}")
                results = duckduckgo_search(query, max_results=5)
                formatted = format_search_results(results)
                search_results_text += f"\n\n**Quick Search: {query}**\n{formatted}"
                
                # Собрать URLs для чтения
                if results:
                    urls = [r['url'] for r in results[:3]]  # ТОП-3
                    all_urls_to_read.extend(urls)
            
            # Удалить SEARCH[] паттерны
            cleaned_response = re.sub(search_pattern, '', cleaned_response)
        
        # 3. ЧИТАТЬ содержимое найденных страниц (ТОП-3)
        if all_urls_to_read and search_enabled:
            try:
                logger.info(f"[DialogAgent] Reading content from {len(all_urls_to_read)} URLs...")
                
                # Читать только уникальные URLs, максимум 3
                unique_urls = list(dict.fromkeys(all_urls_to_read))[:3]
                read_results = read_multiple_urls(unique_urls, max_urls=3)
                
                formatted_content = format_read_results(read_results)
                read_content_text = f"\n\n{formatted_content}"
                
                # ДИНАМИЧЕСКИЙ РАСЧЕТ ЛИМИТОВ с использованием LLM провайдера
                # Получить доступное пространство для контента
                user_query = state.get('current_user_input', '')
                instruction = DIALOG_INSTRUCTION.format(current_datetime=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
                
                # Рассчитать доступное место (с учетом промпта, истории, буфера)
                available_chars = llm_provider.calculate_available_space(
                    system_prompt=instruction,
                    history="",  # История уже учтена в промпте
                    buffer_ratio=0.25  # 25% для ответа агента
                )
                
                # Оценить токены для метрик
                estimated_tokens = llm_provider.estimate_tokens(instruction)
                context_limit = llm_provider.get_context_limit()
                
                logger.info(f"[DialogAgent] Context: {estimated_tokens}/{context_limit} tokens used by prompt, {available_chars} chars available for content")
                
                # Извлечь ключевые слова из запроса для smart chunking
                query_words = set(re.findall(r'\w+', user_query.lower()))
                
                # Распределить место между страницами (поровну)
                num_successful = len([r for r in read_results if r['status'] == 'success'])
                if num_successful > 0:
                    chars_per_page = available_chars // num_successful
                else:
                    chars_per_page = 10000  # Fallback
                
                # Добавить УМНЫЙ CHUNKING для LLM анализа
                full_content_for_analysis = "\n\n**Page Content:**\n\n"
                total_truncated = 0
                
                for result in read_results:
                    if result['status'] == 'success':
                        main_text = result.get('main_text', '')
                        
                        # Применить smart chunking
                        chunked = smart_chunk_content(
                            text=main_text,
                            query_words=query_words,
                            max_chars=chars_per_page
                        )
                        
                        full_content_for_analysis += f"**Source: {result['title']}**\n"
                        full_content_for_analysis += f"URL: {result['url']}\n"
                        
                        # Добавить metadata если контент был обрезан
                        if chunked['truncated']:
                            coverage_percent = int(chunked['coverage'] * 100)
                            full_content_for_analysis += f"*[Showing {coverage_percent}% of content - {chunked['num_paragraphs']} most relevant paragraphs]*\n\n"
                            total_truncated += 1
                        else:
                            full_content_for_analysis += "\n"
                        
                        full_content_for_analysis += f"{chunked['content']}\n\n"
                        full_content_for_analysis += "---\n\n"
                
                read_content_text = clean_ui_artifacts(full_content_for_analysis) + read_content_text
                
                # Финальные метрики
                content_tokens = llm_provider.estimate_tokens(full_content_for_analysis)
                total_tokens = estimated_tokens + content_tokens
                usage_percent = (total_tokens / context_limit) * 100
                
                if total_truncated > 0:
                    logger.warning(f"[DialogAgent] {total_truncated}/{num_successful} pages were truncated to fit context")
                
                logger.info(f"[DialogAgent] Successfully read {num_successful} pages (chars: {len(full_content_for_analysis)}, tokens: ~{content_tokens}, total usage: {usage_percent:.1f}%)")
            except Exception as e:
                logger.error(f"[DialogAgent] Error reading URLs: {e}")
                read_content_text = f"\n\n**Note:** Could not read some web pages due to error: {e}"
        
        # 4. Если был поиск или чтение - ВТОРОЙ ВЫЗОВ LLM для анализа (ITERATIVE)
        if search_results_text or read_content_text:
            current_round += 1
            state.set("reasoning_round", current_round)
            
            logger.info(f"[DialogAgent] Round {current_round}: Performing analysis LLM call...")
            
            # Сохранить промежуточные результаты в state (аккумулятивно для всех раундов)
            prev_searches = state.get("all_search_results", [])
            prev_searches.append({"round": current_round, "search": search_results_text, "content": read_content_text})
            state.set("all_search_results", prev_searches)
            
            # Создать промпт для анализа с учетом iterative reasoning
            history_text = ""
            if current_round > 1:
                history_text = f"\n**Previous rounds:**\n"
                for prev in prev_searches[:-1]:
                    history_text += f"Round {prev['round']}: searched and read pages\n"
            
            analysis_prompt = f"""You are analyzing search results. Round {current_round}/3.{history_text}

**Information from current search:**
{read_content_text}

{search_results_text}

**User's question:** {state.get('current_user_input', 'previous question')}

**Your task:**
1. Analyze the information you found
2. Decide: do you have ENOUGH information to answer OR need MORE?
3. If you need MORE specific information: respond with CONTINUE_SEARCH["specific query here"]
4. If you have ENOUGH: provide a clear answer (NO markers like "Final Answer:", just write naturally)

**Guidelines:**
- Use ONLY information from the pages you read
- Cite sources (mention website names)
- Be honest if information is incomplete
- Write conversationally, not with technical markers

**Your response:**"""
            
            # Второй вызов LLM для анализа прочитанного
            try:
                analysis_response = llm_provider.generate(analysis_prompt, temperature=0.7)
                
                # Проверить нужен ли еще раунд поиска (паттерн CONTINUE_SEARCH)
                continue_pattern = r'CONTINUE_SEARCH\["([^"]+)"\]'
                continue_searches = re.findall(continue_pattern, analysis_response)
                
                # Если агент хочет продолжить И не превышен лимит раундов
                if continue_searches and current_round < 3 and search_enabled:
                    logger.info(f"[DialogAgent] Round {current_round}: Agent requests CONTINUE_SEARCH, starting round {current_round + 1}...")
                    
                    # Очистить паттерн из ответа
                    analysis_response = re.sub(continue_pattern, '', analysis_response).strip()
                    
                    # Выполнить новый поиск
                    new_query = continue_searches[0]
                    logger.info(f"[DialogAgent] Round {current_round + 1}: Searching for: {new_query}")
                    
                    new_results = duckduckgo_search(new_query, max_results=5)
                    new_formatted = format_search_results(new_results)
                    
                    # Прочитать новые URLs с умным chunking
                    if new_results:
                        new_urls = [r['url'] for r in new_results[:3]]
                        new_read_results = read_multiple_urls(new_urls, max_urls=3)
                        new_read_content = ""
                        
                        # Рассчитать лимиты для нового раунда
                        num_new_successful = len([r for r in new_read_results if r['status'] == 'success'])
                        if num_new_successful > 0:
                            new_chars_per_page = available_chars // num_new_successful
                        else:
                            new_chars_per_page = 10000
                        
                        for result in new_read_results:
                            if result['status'] == 'success':
                                # Применить smart chunking
                                new_chunked = smart_chunk_content(
                                    text=result.get('main_text', ''),
                                    query_words=query_words,
                                    max_chars=new_chars_per_page
                                )
                                
                                new_read_content += f"**Source: {result['title']}**\n"
                                new_read_content += f"URL: {result['url']}\n"
                                
                                if new_chunked['truncated']:
                                    coverage = int(new_chunked['coverage'] * 100)
                                    new_read_content += f"*[Showing {coverage}% - {new_chunked['num_paragraphs']} paragraphs]*\n\n"
                                else:
                                    new_read_content += "\n"
                                
                                new_read_content += f"{new_chunked['content']}\n\n---\n\n"
                        
                        # Добавить новые результаты в state
                        prev_searches.append({"round": current_round + 1, "search": new_formatted, "content": new_read_content})
                        state.set("all_search_results", prev_searches)
                        state.set("reasoning_round", current_round + 1)
                        
                        # Финальный анализ после нового раунда
                        final_prompt = f"""You completed multiple search rounds. Here's ALL the information gathered:

**Previous analysis:**
{analysis_response}

**New search results (round {current_round + 1}):**
{new_read_content}

**User's question:** {state.get('current_user_input')}

**Now provide your FINAL answer:**
- Use all information from all rounds
- Write naturally and conversationally (NO "Final Answer:", "Thought:" markers!)
- Cite sources at the end
- Be clear and helpful

**Your answer:**"""
                        
                        final_response = llm_provider.generate(final_prompt, temperature=0.7)
                        state.set("final_response", final_response)
                        
                        # Добавить источники в конец
                        sources_text = "\n\n**📚 Sources:**\n"
                        for prev in prev_searches:
                            urls = re.findall(r'URL: (https?://[^\s]+)', prev['content'])
                            for url in set(urls):
                                sources_text += f"- {url}\n"
                        
                        logger.info(f"[DialogAgent] Iterative reasoning complete after {current_round + 1} rounds")
                        return final_response + sources_text
                
                elif continue_searches and not search_enabled:
                    logger.warning("[DialogAgent] LLM attempted to use CONTINUE_SEARCH but it's disabled by user")
                    analysis_response = re.sub(continue_pattern, '[Web search is disabled]', analysis_response)
                
                # Если не нужен еще раунд ИЛИ достигнут лимит - финальный ответ
                state.set("final_response", analysis_response)
                
                # Добавить источники в конец
                sources_text = "\n\n**📚 Sources:**\n"
                for prev in prev_searches:
                    urls = re.findall(r'URL: (https?://[^\s]+)', prev['content'])
                    for url in set(urls):
                        sources_text += f"- {url}\n"
                
                logger.info(f"[DialogAgent] Analysis complete after {current_round} round(s)")
                
                return analysis_response + sources_text
                
            except Exception as e:
                logger.error(f"[DialogAgent] Error in analysis LLM call: {e}")
                # Fallback - вернуть хотя бы промежуточные результаты
                enhanced = clean_ui_artifacts(cleaned_response + search_results_text + read_content_text)
                return enhanced
        
        return clean_ui_artifacts(cleaned_response) if cleaned_response else None

    agent = Agent(
        name="dialog_agent",
        llm_provider=llm_provider,
        instruction=get_instruction_with_context,
        code_executor=code_executor,
        temperature=0.7,
        before_callback=before_run,
        after_callback=after_run
    )
    
    return agent
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot, File, ChevronDown, ChevronUp } from 'lucide-react';
import type { Message as MessageType } from '../../types';

interface MessageProps {
  message: MessageType;
}

// Функция для разделения контента на части
const parseMessageContent = (content: string) => {
  // Паттерны для ReAct формата (русский и английский)
  const reactPatterns = {
    thought: /\*\*(?:Мысль|Thought):\*\*\s*([^\n]+(?:\n(?!\*\*(?:Действие|Action)).*)*)/gi,
    action: /\*\*(?:Действие|Action):\*\*\s*([^\n]+)/gi,
    params: /\*\*(?:Параметры|Parameters):\*\*\s*```(?:json)?\s*([\s\S]*?)```/gi,
  };

  // Английские паттерны
  const thoughtPattern = /\*\*Thought:\*\*[\s\S]*?(?=\n\n\*\*|$)/gi;
  const analysisPattern = /Analysis[\s\S]*?(?=\n\nFinal Answer|$)/gi;

  // Паттерны поиска
  const searchPatterns = [
    /Quick Search:[\s\S]*?(?=📖|$)/gi,
    /🔍 \*\*Search Results\*\*[\s\S]*?(?=📖|$)/gi,
    /🔍 \*\*Smart Search Results\*\*[\s\S]*?(?=📖|$)/gi,
    /📖 \*\*Read [\s\S]*?(?=\n\n\n|$)/gi,
    /📖 FULL PAGE CONTENT[\s\S]*?(?=\n\n\n|$)/gi,
  ];

  // Паттерн источников
  const sourcesPattern = /\*\*📚 Sources:\*\*[\s\S]*$/gi;

  let thoughts = '';
  let actions = '';
  let searchSteps = '';
  let sources = '';
  let finalAnswer = content;

  // 1. Извлечь ReAct reasoning (русский формат)
  let reactReasoning = '';

  // Мысли
  const thoughtMatches = content.match(reactPatterns.thought);
  if (thoughtMatches) {
    reactReasoning += thoughtMatches.join('\n\n');
    thoughts = thoughtMatches.join('\n\n');
  }

  // Действия
  const actionMatches = content.match(reactPatterns.action);
  if (actionMatches) {
    reactReasoning += '\n\n' + actionMatches.join('\n');
    actions = actionMatches.join('\n');
  }

  // Параметры - извлечь сообщение из JSON если есть
  const paramMatches = content.match(reactPatterns.params);
  if (paramMatches) {
    for (const match of paramMatches) {
      reactReasoning += '\n\n' + match;

      // Попробовать извлечь "message" из JSON
      try {
        const jsonMatch = match.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (jsonMatch) {
          const jsonStr = jsonMatch[1].trim();
          const parsed = JSON.parse(jsonStr);
          if (parsed.message) {
            // Это финальный ответ!
            finalAnswer = parsed.message;
          }
        }
      } catch {
        // Не JSON, игнорируем
      }
    }
  }

  // 2. Английские паттерны для thoughts
  const engThoughtMatches = content.match(thoughtPattern) || content.match(analysisPattern);
  if (engThoughtMatches) {
    thoughts += '\n\n' + engThoughtMatches.join('\n\n');
  }

  // 3. Поисковые шаги
  searchPatterns.forEach(pattern => {
    const matches = content.match(pattern);
    if (matches) {
      matches.forEach(match => {
        searchSteps += match + '\n\n';
      });
    }
  });

  // 4. Источники
  const sourcesMatch = content.match(sourcesPattern);
  if (sourcesMatch) {
    sources = sourcesMatch[0];
  }

  // 5. Дополнительные паттерны для reasoning без форматирования
  const additionalReasoningPatterns = [
    // "Пользователь приветствует..." - начало анализа
    /^Пользователь\s+[^\n]+[\s\S]*?(?=Ответить пользователю|Здравствуйте|Привет|$)/i,
    // "Ответить пользователю" - действие
    /Ответить пользователю\s*/gi,
    // "Наблюдение:" без звёздочек
    /Наблюдение:\s*[^\n]+/gi,
    // "Я успешно..." - самоанализ
    /Я успешно[^\n]+/gi,
  ];

  // 6. Если не нашли JSON message, очищаем finalAnswer от ReAct формата
  if (finalAnswer === content) {
    // Убираем все ReAct паттерны (с markdown)
    finalAnswer = content
      .replace(/\*\*(?:Мысль|Thought):\*\*[\s\S]*?(?=\*\*(?:Действие|Action)|\n\n\*\*|$)/gi, '')
      .replace(/\*\*(?:Действие|Action):\*\*[^\n]*/gi, '')
      .replace(/\*\*(?:Параметры|Parameters):\*\*\s*```(?:json)?[\s\S]*?```/gi, '')
      .replace(/\*\*(?:Наблюдение|Observation):\*\*[\s\S]*?(?=\*\*|$)/gi, '');

    // Убираем reasoning без markdown
    additionalReasoningPatterns.forEach(pattern => {
      finalAnswer = finalAnswer.replace(pattern, '');
    });

    // Убираем поиск и источники
    searchPatterns.forEach(pattern => {
      finalAnswer = finalAnswer.replace(pattern, '');
    });
    if (sources) {
      finalAnswer = finalAnswer.replace(sources, '');
    }

    // Очистить пустые строки
    finalAnswer = finalAnswer.replace(/\n{3,}/g, '\n\n').trim();
  }

  // Если ничего не осталось, показать оригинал без ReAct
  if (!finalAnswer || finalAnswer.length < 5) {
    finalAnswer = content.replace(/\*\*(?:Мысль|Thought|Действие|Action|Параметры|Parameters):\*\*/gi, '')
      .replace(/```json[\s\S]*?```/gi, '')
      .trim() || content;
  }


  return {
    finalAnswer: finalAnswer.trim(),
    thoughts: thoughts.trim(),
    actions: actions.trim(),
    searchSteps: searchSteps.trim(),
    sources: sources.trim(),
    hasThoughts: thoughts.length > 0 || actions.length > 0,
    hasSearchSteps: searchSteps.length > 0,
    hasSources: sources.length > 0,
    hasReactReasoning: reactReasoning.length > 0,
    reactReasoning: reactReasoning.trim(),
  };
};

export const Message: React.FC<MessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const [showThoughts, setShowThoughts] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [showSources, setShowSources] = useState(false);

  // Парсить контент для assistant сообщений
  const parsed = !isUser ? parseMessageContent(message.content) : null;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser ? 'bg-blue-600' : 'bg-green-600'
        }`}>
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>

      {/* Message content */}
      <div className={`flex-1 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`max-w-[80%] rounded-lg p-4 ${isUser ? 'bg-blue-600 text-white' : 'bg-dark-surface text-dark-text'
          }`}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <>
              {/* Final Answer */}
              <ReactMarkdown className="markdown">
                {parsed?.finalAnswer || message.content}
              </ReactMarkdown>

              {/* Collapsible ReAct Reasoning */}
              {parsed?.hasThoughts && (
                <div className="mt-3 pt-3 border-t border-dark-border/50">
                  <button
                    onClick={() => setShowThoughts(!showThoughts)}
                    className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-gradient-to-r from-purple-500/10 to-blue-500/10 hover:from-purple-500/20 hover:to-blue-500/20 transition-all duration-300 group"
                  >
                    <span className="flex items-center gap-2 text-xs font-medium text-purple-300">
                      🧠 Ход мыслей агента
                    </span>
                    <span className="text-xs text-dark-muted group-hover:text-white transition-colors">
                      {showThoughts ? '▲ Скрыть' : '▼ Показать'}
                    </span>
                  </button>

                  {showThoughts && (
                    <div className="mt-2 p-3 rounded-lg bg-dark-bg/50 border border-dark-border/30 overflow-x-auto">
                      <ReactMarkdown className="markdown text-xs text-dark-muted leading-relaxed">
                        {parsed.reactReasoning || parsed.thoughts}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              )}

              {/* Collapsible Search Steps */}
              {parsed?.hasSearchSteps && (
                <div className="mt-2 pt-2">
                  <button
                    onClick={() => setShowSearch(!showSearch)}
                    className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-gradient-to-r from-blue-500/10 to-cyan-500/10 hover:from-blue-500/20 hover:to-cyan-500/20 transition-all duration-300 group"
                  >
                    <span className="flex items-center gap-2 text-xs font-medium text-blue-300">
                      🔍 Результаты поиска
                    </span>
                    <span className="text-xs text-dark-muted group-hover:text-white transition-colors">
                      {showSearch ? '▲ Скрыть' : '▼ Показать'}
                    </span>
                  </button>

                  {showSearch && (
                    <div className="mt-2 p-3 rounded-lg bg-dark-bg/50 border border-dark-border/30 overflow-x-auto">
                      <ReactMarkdown className="markdown text-xs text-dark-muted leading-relaxed">
                        {parsed.searchSteps}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              )}

              {/* Collapsible Sources */}
              {parsed?.hasSources && (
                <div className="mt-2 border-t border-dark-border pt-2">
                  <button
                    onClick={() => setShowSources(!showSources)}
                    className="flex items-center gap-2 text-xs text-dark-muted hover:text-dark-text transition-colors"
                  >
                    {showSources ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    <span>📚 {showSources ? 'Hide' : 'Show'} sources</span>
                  </button>

                  {showSources && (
                    <div className="mt-2 text-xs bg-dark-bg rounded p-2">
                      <ReactMarkdown
                        className="markdown text-dark-text"
                        components={{
                          a: ({ node, ...props }) => (
                            <a
                              {...props}
                              className="text-blue-400 hover:text-blue-300 underline break-all"
                              target="_blank"
                              rel="noopener noreferrer"
                            />
                          )
                        }}
                      >
                        {parsed.sources}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Attached files */}
          {message.files && message.files.length > 0 && (
            <div className="mt-3 space-y-1">
              {message.files.map((file, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm opacity-80">
                  <File size={14} />
                  <span>{file}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span className="text-xs text-dark-muted mt-1 px-2">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
};

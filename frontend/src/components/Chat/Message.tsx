import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Bot, File, ChevronDown, ChevronUp } from 'lucide-react';
import { ToolUsage } from './ToolUsage';
import type { Message as MessageType, ToolCall } from '../../types';

interface MessageProps {
  message: MessageType;
}

// Функция для разделения контента на части
const parseMessageContent = (content: string) => {
  let thoughts = '';
  let toolCalls: ToolCall[] = [];
  let sources = '';
  let finalAnswer = content;
  let hasReasoning = false;

  // 0. Извлекаем <thinking>...</thinking> (DeepSeek / Chain of Thought)
  const thinkingPattern = /<thinking>([\s\S]*?)<\/thinking>/gi;
  let thinkingMatch;
  while ((thinkingMatch = thinkingPattern.exec(content)) !== null) {
    thoughts += thinkingMatch[1] + '\n\n';
    hasReasoning = true;
  }

  // 1. Извлекаем tool calls (JSON в code blocks или просто JSON)
  const codeBlockToolPattern = /```(?:json)?\s*(\{[\s\S]*?"tool"\s*:\s*"[^"]+"[\s\S]*?\})\s*```/gi;
  const rawToolPattern = /(\{[\s\S]*?"tool"\s*:\s*"[^"]+"[\s\S]*?\})/gi;

  const matches: string[] = [];
  let execMatch;

  // 1a. Code blocks
  while ((execMatch = codeBlockToolPattern.exec(content)) !== null) {
    if (execMatch[1]) matches.push(execMatch[1]);
  }

  // 1b. Fallback на сырой JSON
  if (matches.length === 0) {
    while ((execMatch = rawToolPattern.exec(content)) !== null) {
      if (execMatch[1] && execMatch[1].trim().endsWith('}')) {
        matches.push(execMatch[1]);
      }
    }
  }

  // Парсим JSON объекты
  matches.forEach(jsonStr => {
    try {
      const parsed = JSON.parse(jsonStr);
      if (parsed.tool) {
        toolCalls.push({
          tool: parsed.tool,
          params: parsed.params || {}
        });
      }
    } catch (e) {
      console.error("Failed to parse tool call:", jsonStr, e);
    }
  });


  // 4. Очищаем finalAnswer от всего технического
  finalAnswer = content
    // Убираем <thinking> blocks
    .replace(/<thinking>[\s\S]*?<\/thinking>/gi, '')
    // Убираем JSON tool calls в code blocks
    .replace(/```(?:json)?\s*\{[\s\S]*?"tool"\s*:\s*"[^"]+"[\s\S]*?\}\s*```/gi, '')
    // Убираем Raw JSON tool calls
    .replace(/\{[\s\S]*?"tool"\s*:\s*"[^"]+"[\s\S]*?\}/gi, '')
    // Убираем ReAct формат с markdown
    .replace(/\*\*(?:Мысль|Thought):\*\*[^\n]*/gi, '')
    .replace(/\*\*(?:Действие|Action):\*\*[^\n]*/gi, '')
    .replace(/\*\*(?:Параметры|Parameters):\*\*\s*(?:```(?:json)?[\s\S]*?```|\{[\s\S]*?\})/gi, '')
    .replace(/\*\*(?:Наблюдение|Observation):\*\*[\s\S]*?(?=\*\*|$)/gi, '')
    // Убираем результаты выполнения
    .replace(/## Результаты выполнения:[\s\S]*$/gi, '')
    // Убираем верификацию
    .replace(/## Верификация кода:[\s\S]*$/gi, '')
    // Убираем подписи к файлам перед tool calls
    .replace(/(?:Файл \d+|Сначала создам|Теперь создам|Создам файл|Выполняю)[^:\n]*:\s*$/gim, '')
    // Убираем пустые code blocks
    .replace(/```\s*```/g, '')
    // Убираем лишние переносы
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  // 5. Если после очистки остался только заголовок без контента
  if (finalAnswer.length < 20 && toolCalls.length > 0) {
    // Есть tool calls но нет текста
    if (finalAnswer.length === 0) finalAnswer = '';
  }

  return {
    thoughts: thoughts.trim(),
    actions: toolCalls,
    searchSteps: '',
    sources: sources.trim(),
    finalAnswer: finalAnswer.trim(),
    hasReasoning,
  };
};


export const Message: React.FC<MessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const [showThoughts, setShowThoughts] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [showSources, setShowSources] = useState(false);
  // const [showTools, setShowTools] = useState(false); // Handled by ToolUsage

  // Парсим контент
  const parsed = !isUser ? parseMessageContent(message.content) : null;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser ? 'bg-blue-600' : 'bg-green-600'}`}>
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>

      {/* Message content */}
      <div className={`flex-1 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`max-w-[80%] rounded-lg p-4 ${isUser ? 'bg-blue-600 text-white' : 'bg-dark-surface text-dark-text'}`}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <>
              {/* Modular Tool Usage UI */}
              {parsed?.actions && parsed.actions.length > 0 && (
                <ToolUsage toolCalls={parsed.actions} />
              )}

              {/* Final Answer */}
              <ReactMarkdown className="markdown" remarkPlugins={[remarkGfm]}>
                {parsed?.finalAnswer || (parsed?.actions ? '' : message.content)}
              </ReactMarkdown>

              {/* Collapsible ReAct Reasoning */}
              {parsed?.hasReasoning && (
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
                      <ReactMarkdown className="markdown text-xs text-dark-muted leading-relaxed" remarkPlugins={[remarkGfm]}>
                        {parsed.thoughts}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Collapsible Search Steps */}
          {parsed?.searchSteps && (
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
                  <ReactMarkdown className="markdown text-xs text-dark-muted leading-relaxed" remarkPlugins={[remarkGfm]}>
                    {parsed.searchSteps}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          )}

          {/* Collapsible Sources */}
          {parsed?.sources && (
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
        </div>

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
  );
};

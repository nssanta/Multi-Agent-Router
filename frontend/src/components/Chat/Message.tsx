import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Bot, File, ChevronDown, ChevronUp, CheckCircle, XCircle, FileText, Play, Code } from 'lucide-react';
import { ToolUsage } from './ToolUsage';
import type { Message as MessageType, ToolCall } from '../../types';

interface MessageProps {
  message: MessageType;
}

// Типы результатов инструментов
interface ToolResult {
  type: 'success' | 'error' | 'file_content' | 'execution_result';
  title: string;
  content: string;
}

// Функция для разделения контента на части
const parseMessageContent = (content: string) => {
  let thoughts = '';
  let toolCalls: ToolCall[] = [];
  let toolResults: ToolResult[] = [];
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

  // 2. Извлекаем результаты инструментов
  // ✅ Success messages
  const successPattern = /[✅✔️]\s*(?:File\s+)?([^\n]+?)\s*(?:written successfully|created|saved)[.!]?/gi;
  let successMatch;
  while ((successMatch = successPattern.exec(content)) !== null) {
    toolResults.push({
      type: 'success',
      title: 'Файл создан',
      content: successMatch[1].trim().replace(/^`|`$/g, '')
    });
  }

  // ❌ or 🔧 Execution Failed
  const errorPattern = /[❌🔧⚠️]\s*(?:Execution\s+Failed|Error)[:\s]+([^\n]+(?:\n(?![❌✅🔧⚠️▶️📄])[^\n]+)*)/gi;
  let errorMatch;
  while ((errorMatch = errorPattern.exec(content)) !== null) {
    const errorContent = errorMatch[1].trim();
    // Сокращаем длинные ошибки
    const shortError = errorContent.length > 150
      ? errorContent.substring(0, 150) + '...'
      : errorContent;
    toolResults.push({
      type: 'error',
      title: 'Ошибка выполнения',
      content: shortError
    });
  }

  // 📄 File Content
  const fileContentPattern = /📄\s*File\s+Content\s*\(([^)]+)\)[:\s]+([^\n]+(?:\n(?![❌✅🔧⚠️▶️📄])[^\n]+)*)/gi;
  let fileMatch;
  while ((fileMatch = fileContentPattern.exec(content)) !== null) {
    toolResults.push({
      type: 'file_content',
      title: fileMatch[1].trim(),
      content: fileMatch[2].trim()
    });
  }

  // ▶️ Execution Result
  const execResultPattern = /▶️\s*Execution\s+Result[:\s]+([^\n]+(?:\n(?![❌✅🔧⚠️▶️📄•\-\*])[^\n]+)*)/gi;
  let execResultMatch;
  while ((execResultMatch = execResultPattern.exec(content)) !== null) {
    toolResults.push({
      type: 'execution_result',
      title: 'Результат выполнения',
      content: execResultMatch[1].trim()
    });
  }

  // 4. Очищаем finalAnswer от всего технического
  finalAnswer = content
    // Убираем <thinking> blocks
    .replace(/<thinking>[\s\S]*?<\/thinking>/gi, '')
    // Убираем JSON tool calls в code blocks
    .replace(/```(?:json)?\s*\{[\s\S]*?"tool"\s*:\s*"[^"]+"[\s\S]*?\}\s*```/gi, '')
    // Убираем Raw JSON tool calls
    .replace(/\{[\s\S]*?"tool"\s*:\s*"[^"]+"[\s\S]*?\}/gi, '')
    // Убираем статусные сообщения инструментов
    .replace(/[✅✔️]\s*(?:File\s+)?[^\n]+?\s*(?:written successfully|created|saved)[.!]?/gi, '')
    .replace(/[❌🔧⚠️]\s*(?:Execution\s+Failed|Error)[:\s]+[^\n]+(?:\n(?![❌✅🔧⚠️▶️📄•\-\*])[^\n]+)*/gi, '')
    .replace(/📄\s*File\s+Content\s*\([^)]+\)[:\s]+[^\n]+(?:\n(?![❌✅🔧⚠️▶️📄•\-\*])[^\n]+)*/gi, '')
    .replace(/▶️\s*Execution\s+Result[:\s]+[^\n]+(?:\n(?![❌✅🔧⚠️▶️📄•\-\*])[^\n]+)*/gi, '')
    // Убираем битые emoji (replacement character)
    .replace(/[\uFFFD�]/g, '')
    // Убираем сырые print statements (одна строка)
    .replace(/^print\([^)]+\)\s*$/gm, '')
    // Убираем несколько print подряд
    .replace(/print\([^)]+\)\s*print\([^)]+\)/gi, '')
    // Убираем def/return на одной строке (сжатый код)
    .replace(/def\s+\w+\([^)]*\):[^\n]*return[^\n]*/gi, '')
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
    // Убираем одиночные backticks с пробелами
    .replace(/^\s*`\s*$/gm, '')
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
    toolResults,
    searchSteps: '',
    sources: sources.trim(),
    finalAnswer: finalAnswer.trim(),
    hasReasoning,
  };
};

// Компонент для красивого отображения результата инструмента
const ToolResultCard: React.FC<{ result: ToolResult }> = ({ result }) => {
  const configs = {
    success: {
      icon: CheckCircle,
      bg: 'bg-green-500/10',
      border: 'border-green-500/30',
      iconColor: 'text-green-400',
      titleColor: 'text-green-300'
    },
    error: {
      icon: XCircle,
      bg: 'bg-red-500/10',
      border: 'border-red-500/30',
      iconColor: 'text-red-400',
      titleColor: 'text-red-300'
    },
    file_content: {
      icon: FileText,
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      iconColor: 'text-blue-400',
      titleColor: 'text-blue-300'
    },
    execution_result: {
      icon: Play,
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/30',
      iconColor: 'text-purple-400',
      titleColor: 'text-purple-300'
    }
  };

  const config = configs[result.type];
  const Icon = config.icon;

  return (
    <div className={`flex items-start gap-2 p-2 rounded-lg ${config.bg} border ${config.border} mb-2`}>
      <Icon size={16} className={`mt-0.5 ${config.iconColor} flex-shrink-0`} />
      <div className="flex-1 min-w-0">
        <div className={`text-xs font-medium ${config.titleColor}`}>{result.title}</div>
        {result.content && (
          <div className="text-xs text-dark-muted mt-0.5 font-mono truncate">
            {result.content}
          </div>
        )}
      </div>
    </div>
  );
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

              {/* Tool Results - красивые карточки */}
              {parsed?.toolResults && parsed.toolResults.length > 0 && (
                <div className="mb-3">
                  {parsed.toolResults.map((result, idx) => (
                    <ToolResultCard key={idx} result={result} />
                  ))}
                </div>
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

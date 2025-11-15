import React, { useState, useEffect } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { TypingIndicator } from './TypingIndicator';
import { api } from '../../services/api';
import type { Message, ChatUsage, ActiveModelInfo } from '../../types';

interface ChatWindowProps {
  sessionId: string | null;
  agentType: string;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ sessionId, agentType }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [usage, setUsage] = useState<ChatUsage | null>(null);
  const [modelInfo, setModelInfo] = useState<ActiveModelInfo | null>(null);
  const [lastErrorCode, setLastErrorCode] = useState<number | null>(null);
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null);
  const [lastSearchEnabled, setLastSearchEnabled] = useState<boolean>(true);
  const [isRetrying, setIsRetrying] = useState(false);

  // Load session history and reset retry state
  useEffect(() => {
    // ВСЕГДА сбрасываем retry state при смене сессии
    setLastErrorCode(null);
    setLastUserMessage(null);
    setIsRetrying(false);

    if (!sessionId) {
      setMessages([]);
      setUsage(null);
      setModelInfo(null);
      return;
    }

    const loadSession = async () => {
      setLoadingHistory(true);
      try {
        console.log('Loading session:', agentType, sessionId);
        const session = await api.getSession(agentType, sessionId);
        console.log('Loaded messages:', session.messages);
        setMessages(session.messages || []);

        // Восстановить usage и информацию о модели из state сессии (если есть)
        const state = session.state || {};
        if (state.usage) {
          setUsage(state.usage as ChatUsage);
        } else {
          setUsage(null);
        }
        if (state.model_info) {
          setModelInfo(state.model_info as ActiveModelInfo);
        } else {
          setModelInfo(null);
        }

        // Сбрасываем retry state после загрузки (на случай если были ошибки)
        setLastErrorCode(null);
        setLastUserMessage(null);
      } catch (error) {
        console.error('Failed to load session:', error);
        alert(`Failed to load session: ${error}`);
      } finally {
        setLoadingHistory(false);
      }
    };

    loadSession();
  }, [sessionId, agentType]);

  const handleSend = async (message: string, files?: File[], searchEnabled?: boolean) => {
    if (!sessionId) return;

    const effectiveSearchEnabled = searchEnabled ?? true;

    // Add search instruction if enabled
    let finalMessage = message;
    if (effectiveSearchEnabled && message && !message.includes('SEARCH[')) {
      // Optionally prepend search hint to message
      // finalMessage = `${message}\n\n(Web search is enabled)`;
    }

    // Upload files first if any
    if (files && files.length > 0) {
      try {
        const uploadPromises = files.map(file => api.uploadFile(agentType, sessionId, file));
        await Promise.all(uploadPromises);

        // Add user message with file names
        const userMsg: Message = {
          role: 'user',
          content: message || '📎 Files attached',
          timestamp: new Date().toISOString(),
          files: files.map(f => f.name),
        };
        setMessages(prev => [...prev, userMsg]);
      } catch (error) {
        console.error('File upload failed:', error);
        alert('Failed to upload files');
        return;
      }
    } else {
      // Add user message
      const userMsg: Message = {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, userMsg]);
    }

    setLastUserMessage(finalMessage);
    setLastSearchEnabled(effectiveSearchEnabled);
    setLastErrorCode(null);

    // Send message to agent
    setLoading(true);
    try {
      const response = await api.sendMessage(agentType, sessionId, finalMessage, effectiveSearchEnabled);

      const text = response.response || '';
      const isRateLimitText =
        typeof text === 'string' &&
        text.includes('429') &&
        text.toLowerCase().includes('too many requests');

      if (response.usage) {
        setUsage(response.usage);
      }
      if (response.model) {
        setModelInfo(response.model);
      }

      if (isRateLimitText) {
        setLastErrorCode(429);

        const errorMsg: Message = {
          role: 'assistant',
          content:
            'Rate limit reached (429 Too Many Requests). You can retry the last message using the retry button below.',
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, errorMsg]);
      } else {
        setLastErrorCode(null);
        setLastUserMessage(null);

        const assistantMsg: Message = {
          role: 'assistant',
          content: text,
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, assistantMsg]);
      }
    } catch (error: any) {
      console.error('Send message failed:', error);
      const status = typeof error?.status === 'number' ? error.status : null;

      if (status === 429) {
        setLastErrorCode(429);

        const errorMsg: Message = {
          role: 'assistant',
          content: 'Rate limit reached (429 Too Many Requests). You can retry the last message using the retry button below.',
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, errorMsg]);
      } else {
        setLastErrorCode(status);

        const errorMsg: Message = {
          role: 'assistant',
          content: `Error: ${error.message || 'Failed to send message'}`,
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, errorMsg]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!sessionId || !lastUserMessage) return;

    setIsRetrying(true);
    setLoading(true);
    const maxAttempts = 5;
    const delayMs = 1500;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const response = await api.sendMessage(
          agentType,
          sessionId,
          lastUserMessage,
          lastSearchEnabled,
        );
        const text = response.response || '';
        const isRateLimitText =
          typeof text === 'string' &&
          text.includes('429') &&
          text.toLowerCase().includes('too many requests');

        if (response.usage) {
          setUsage(response.usage);
        }
        if (response.model) {
          setModelInfo(response.model);
        }

        if (isRateLimitText) {
          // считаем это всё ещё ошибкой 429 и пробуем дальше, не показывая сырое сообщение провайдера
          setLastErrorCode(429);

          if (attempt === maxAttempts - 1) {
            const errorMsg: Message = {
              role: 'assistant',
              content:
                'Provider is still rate-limited after several attempts (429). Please try again later or switch the model.',
              timestamp: new Date().toISOString(),
            };
            setMessages(prev => [...prev, errorMsg]);
          }

          if (attempt < maxAttempts - 1) {
            await new Promise(res => setTimeout(res, delayMs));
          }
        } else {
          // успешный ответ — удаляем сообщение об ошибке и показываем новый ответ
          const assistantMsg: Message = {
            role: 'assistant',
            content: text,
            timestamp: new Date().toISOString(),
          };

          // Удаляем последнее сообщение если оно было об ошибке 429
          setMessages(prev => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.role === 'assistant' &&
              (lastMsg.content.includes('429') ||
                lastMsg.content.includes('Rate limit') ||
                lastMsg.content.includes('rate-limited'))) {
              // Убираем сообщение об ошибке и добавляем успешный ответ
              return [...prev.slice(0, -1), assistantMsg];
            }
            // Просто добавляем ответ
            return [...prev, assistantMsg];
          });

          setLastErrorCode(null);
          setLastUserMessage(null);
        }

        break;
      } catch (err: any) {
        console.error('Retry send failed:', err);
        const status = typeof err?.status === 'number' ? err.status : null;

        if (status === 429) {
          setLastErrorCode(429);
          if (attempt < maxAttempts - 1) {
            await new Promise(res => setTimeout(res, delayMs));
            continue;
          }

          const errorMsg: Message = {
            role: 'assistant',
            content: 'Provider is still rate-limited after several attempts (429). Please try again later or switch the model.',
            timestamp: new Date().toISOString(),
          };
          setMessages(prev => [...prev, errorMsg]);
        } else {
          setLastErrorCode(status);
          const errorMsg: Message = {
            role: 'assistant',
            content: `Error during retry: ${err?.message || 'Unknown error'}`,
            timestamp: new Date().toISOString(),
          };
          setMessages(prev => [...prev, errorMsg]);
        }

        break;
      }
    }

    setIsRetrying(false);
    setLoading(false);
  };

  if (!sessionId) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center text-dark-muted">
          <p className="text-lg">No session selected</p>
          <p className="text-sm mt-2">Create a new session or select an existing one</p>
        </div>
      </div>
    );
  }

  if (loadingHistory) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center text-dark-muted">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-sm">Loading session history...</p>
        </div>
      </div>
    );
  }

  // Добавить временное сообщение "в процессе" если агент думает
  const displayMessages = loading
    ? [...messages]  // Не добавляем фейковое сообщение, используем TypingIndicator
    : messages;

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden">
      {modelInfo && (
        <div className="px-4 pt-3 pb-2 border-b border-dark-border text-center">
          <div className="text-xs text-dark-muted">
            {modelInfo.display_name} ({modelInfo.provider})
          </div>
          {usage && (
            <div className="mt-2">
              <div className="h-1.5 bg-dark-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500"
                  style={{ width: `${Math.min(100, ((usage.session_total_tokens || 0) / (usage.context_limit_tokens || 1)) * 100)}%` }}
                />
              </div>
              <div className="mt-1 text-[10px] text-dark-muted">
                {usage.session_total_tokens || 0} / {usage.context_limit_tokens || 0} tokens (session)
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4">
        <MessageList messages={displayMessages} />
        {/* Typing Indicator */}
        {loading && (
          <div className="mt-4">
            <TypingIndicator status="thinking" />
          </div>
        )}
      </div>
      {/* Retry UI - показывать только если есть сообщения и есть ошибка */}
      {lastErrorCode === 429 && lastUserMessage && messages.length > 0 && (
        <div className="px-4 py-2 border-t border-dark-border bg-dark-surface flex items-center justify-between text-xs text-dark-muted">
          <span>⚠️ Лимит запросов достигнут. Попробуйте другую модель или подождите.</span>
          <button
            onClick={handleRetry}
            disabled={isRetrying || loading}
            className="ml-2 px-3 py-1 rounded-md bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
          >
            {isRetrying ? '...' : '↻ Retry'}
          </button>
        </div>
      )}
      <MessageInput
        onSend={handleSend}
        disabled={loading || isRetrying}
      />
    </div>
  );
};

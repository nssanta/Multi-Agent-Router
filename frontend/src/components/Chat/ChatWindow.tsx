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
  const [agentStatus, setAgentStatus] = useState<string | null>(null);

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

  const handleStreamCallbacks = (isRetry: boolean) => ({
    onToken: (token: string) => {
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMsgIndex = newMessages.length - 1;
        const lastMsg = newMessages[lastMsgIndex];

        if (lastMsg && lastMsg.role === 'assistant') {
          // Immutable update to prevent Strict Mode duplication
          newMessages[lastMsgIndex] = {
            ...lastMsg,
            content: lastMsg.content + token
          };
        }
        return newMessages;
      });
    },
    onStatus: (status: string) => {
      setAgentStatus(status);
    },
    onUsage: (newUsage: any) => {
      setUsage(newUsage as ChatUsage);
    },
    onComplete: () => {
      setLoading(false);
      setIsRetrying(false);
      setAgentStatus(null);
      if (isRetry) {
        // Success! we can clear the error code.
        // We DO NOT clear lastUserMessage so the user can regenerate again if they want.
        setLastErrorCode(null);
      } else {
        // Normal completion
        setLastErrorCode(null);
      }
    },
    onError: (err: string) => {
      console.error("Stream error:", err);
      // Update last message with error
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMsgIndex = newMessages.length - 1;
        const lastMsg = newMessages[lastMsgIndex];

        // Format error text
        const errorText = `\n\n[Error: ${err}]`;

        if (lastMsg && lastMsg.role === 'assistant') {
          let newContent = lastMsg.content;

          // If content is empty or just "Thinking...", replace it
          if (lastMsg.content === '' || lastMsg.content === 'Thinking...') {
            newContent = errorText.trim();
          } else {
            newContent += errorText;
          }

          // Immutable update
          newMessages[lastMsgIndex] = {
            ...lastMsg,
            content: newContent
          };
        } else {
          // Fallback
          newMessages.push({
            role: 'assistant',
            content: errorText,
            timestamp: new Date().toISOString()
          });
        }
        return newMessages;
      });

      setLoading(false);
      setIsRetrying(false);
      setAgentStatus(null);

      // Always allow retry on error
      if (err.includes('429') || err.toLowerCase().includes('rate limit')) {
        setLastErrorCode(429);
      } else {
        setLastErrorCode(500);
      }
    }
  });

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

    // Create placeholder for assistant message
    const assistantMsg: Message = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, assistantMsg]);

    setLoading(true);
    setAgentStatus("Thinking...");

    await api.streamChat(
      agentType,
      sessionId,
      finalMessage,
      effectiveSearchEnabled,
      handleStreamCallbacks(false)
    );
  };

  const handleRetry = async () => {
    if (!sessionId || !lastUserMessage) return;

    setIsRetrying(true);
    setLoading(true);
    setAgentStatus("Retrying...");

    // Clear previous error content from the LAST message if it looks like an error
    setMessages(prev => {
      const newMessages = [...prev];
      const lastMsg = newMessages[newMessages.length - 1];
      if (lastMsg && lastMsg.role === 'assistant' && (
        lastMsg.content.includes('[Error') || lastMsg.content.includes('Rate limit')
      )) {
        newMessages[newMessages.length - 1] = {
          ...lastMsg,
          content: ''
        }; // Reset content for reuse
      } else {
        // Or add new placeholder if last wasn't assistant?
        // Usually it is.
      }
      return newMessages;
    });

    // Don't reset LastErrorCode yet, wait for success or new error
    // check if last message exists, if not add it (rare)

    await api.streamChat(
      agentType,
      sessionId,
      lastUserMessage,
      lastSearchEnabled,
      handleStreamCallbacks(true)
    );
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
        {/* Typing Indicator & Status */}
        {loading && (
          <div className="mt-4 px-4">
            <div className="flex items-center space-x-3">
              <TypingIndicator status="thinking" customText={agentStatus} />
            </div>
          </div>
        )}
      </div>
      {/* Retry / Regenerate UI */}
      {lastUserMessage && !loading && (
        <div className={`px-4 py-2 border-t border-dark-border flex items-center justify-between text-xs ${lastErrorCode ? 'bg-red-900/20 text-red-200' : 'bg-dark-surface text-dark-muted'}`}>
          <span>
            {lastErrorCode === 429
              ? '⚠️ Лимит запросов достигнут.'
              : lastErrorCode
                ? '⚠️ Ошибка генерации.'
                : 'Ответ завершен.'}
          </span>
          <div className="flex gap-2">
            <button
              onClick={handleRetry}
              disabled={isRetrying || loading}
              className={`px-3 py-1 rounded-md text-white transition-colors flex items-center gap-1 ${lastErrorCode
                ? 'bg-red-600 hover:bg-red-500'
                : 'bg-dark-surface border border-dark-border hover:bg-dark-border text-dark-text'
                }`}
            >
              {lastErrorCode ? '↻ Повторить' : '↻ Перегенерировать'}
            </button>
          </div>
        </div>
      )}
      <MessageInput
        onSend={handleSend}
        disabled={loading || isRetrying}
      />
    </div>
  );
};

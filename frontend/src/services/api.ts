import type {
  Session,
  SessionHistory,
  SessionFile,
  Agent,
  ModelInfo,
  ChatResponse,
} from '../types';

const API_BASE = '/api';

class ApiClient {
  private async request<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({ detail: 'Unknown error' }));
      const err: any = new Error(errorBody.detail || `HTTP error ${response.status}`);
      err.status = response.status;
      err.body = errorBody;
      throw err;
    }

    return response.json();
  }

  // Agents
  /** Получаем список агентов. */
  async getAgents(): Promise<{ agents: Agent[] }> {
    return this.request('/agents');
  }

  // Models
  /** Получаем список моделей. */
  async getModels(provider?: string): Promise<{ models: ModelInfo[] }> {
    const url = provider ? `/models?provider=${provider}` : '/models';
    return this.request(url);
  }

  /** Получаем динамический список бесплатных моделей от OpenRouter API. */
  async getOpenRouterFreeModels(): Promise<{ models: ModelInfo[]; cached: boolean; count?: number; error?: string }> {
    return this.request('/models/openrouter-free');
  }

  // Sessions
  /** Создаем сессию. */
  async createSession(
    agentType: string,
    userId = 'default',
    modelId?: string
  ): Promise<Session> {
    return this.request('/sessions', {
      method: 'POST',
      body: JSON.stringify({ agent_type: agentType, user_id: userId, model_id: modelId }),
    });
  }

  async listSessions(agentType?: string): Promise<{ sessions: Session[] }> {
    const url = agentType ? `/sessions?agent_type=${agentType}` : '/sessions';
    return this.request(url);
  }

  async getSession(agentType: string, sessionId: string): Promise<SessionHistory> {
    return this.request(`/sessions/${agentType}/${sessionId}`);
  }

  async deleteSession(agentType: string, sessionId: string): Promise<{ success: boolean }> {
    return this.request(`/sessions/${agentType}/${sessionId}`, { method: 'DELETE' });
  }

  async listSessionFiles(agentType: string, sessionId: string): Promise<{
    session_id: string;
    input_files: SessionFile[];
    workspace_files: SessionFile[];
  }> {
    return this.request(`/sessions/${agentType}/${sessionId}/files`);
  }

  async getSessionLogs(agentType: string, sessionId: string): Promise<{
    session_id: string;
    logs: any[];
  }> {
    return this.request(`/sessions/${agentType}/${sessionId}/logs`);
  }

  // Chat Streaming
  /** Реализуем потоковый чат. */
  async streamChat(
    agentType: string,
    sessionId: string,
    message: string,
    searchEnabled: boolean,
    callbacks: {
      onToken: (token: string) => void;
      onStatus: (status: string) => void;
      onUsage: (usage: any) => void;
      onComplete: () => void;
      onError: (error: string) => void;
    }
  ): Promise<void> {
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          agent_type: agentType,
          session_id: sessionId,
          message,
          search_enabled: searchEnabled
        }),
      });

      if (!response.ok) {
        // Try to read error body
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      if (!response.body) {
        throw new Error('Response body is empty');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Парсим SSE события из буфера
        // Ожидаемый формат: data: {...}\n\n
        const lines = buffer.split('\n\n');
        // Сохраняем последний кусок, если он неполный
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            if (dataStr === '[DONE]') {
              continue; // or break?
            }
            try {
              const event = JSON.parse(dataStr);
              if (event.type === 'token') {
                callbacks.onToken(event.content);
              } else if (event.type === 'status') {
                callbacks.onStatus(event.content);
              } else if (event.type === 'usage') {
                callbacks.onUsage(event.content);
              } else if (event.type === 'error') {
                callbacks.onError(event.content);
              } else if (event.type === 'system') {
                // Format system messages nicely
                const content = event.content || '';

                // Скрываем технические ошибки от пользователя, показываем дружелюбные сообщения
                if (content.includes('Tool execution error') || content.includes('error')) {
                  // Don't show raw errors - just show status update
                  callbacks.onStatus('Processing...');
                } else if (content.includes('written successfully')) {
                  callbacks.onToken(`\n\n✅ ${content}\n\n`);
                } else if (content.includes('File Content')) {
                  // Shorten file content display
                  const shortContent = content.length > 500
                    ? content.substring(0, 500) + '\n... (truncated)'
                    : content;
                  callbacks.onToken(`\n\n📄 ${shortContent}\n\n`);
                } else if (content.includes('Directory listing')) {
                  callbacks.onToken(`\n\n📁 ${content}\n\n`);
                } else if (content.includes('Execution Result')) {
                  callbacks.onToken(`\n\n▶️ ${content}\n\n`);
                } else if (content.includes('not valid JSON')) {
                  // JSON error - just show status
                  callbacks.onStatus('Retrying...');
                } else if (content.includes('Aborting turn')) {
                  callbacks.onToken(`\n\n⚠️ Agent stopped: too many attempts\n\n`);
                } else {
                  // Other system messages - show as-is but formatted
                  callbacks.onToken(`\n\n🔧 ${content}\n\n`);
                }
              } else if (event.type === 'log') {
                // Only log to console, don't show to user
                console.log('Agent Log:', event.content);
              }
            } catch (e) {
              console.error('Failed to parse SSE event:', dataStr, e);
            }
          }
        }
      }

      callbacks.onComplete();

    } catch (error: any) {
      callbacks.onError(error.message || 'Stream processing failed');
    }
  }

  // Legacy Chat (Deprecated, use streamChat)
  async sendMessage(
    agentType: string,
    sessionId: string,
    message: string,
    searchEnabled = true
  ): Promise<ChatResponse> {
    throw new Error("Use streamChat instead");
  }

  // File upload
  /** Загружаем файл. */
  async uploadFile(
    agentType: string,
    sessionId: string,
    file: File
  ): Promise<{ filename: string; path: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/upload/${agentType}/${sessionId}`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('File upload failed');
    }

    return response.json();
  }
}

export const api = new ApiClient();

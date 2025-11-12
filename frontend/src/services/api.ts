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
  async getAgents(): Promise<{ agents: Agent[] }> {
    return this.request('/agents');
  }

  // Models
  async getModels(provider?: string): Promise<{ models: ModelInfo[] }> {
    const url = provider ? `/models?provider=${provider}` : '/models';
    return this.request(url);
  }

  // Динамический список free моделей от OpenRouter API
  async getOpenRouterFreeModels(): Promise<{ models: ModelInfo[]; cached: boolean; count?: number; error?: string }> {
    return this.request('/models/openrouter-free');
  }

  // Sessions
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

  // Chat
  async sendMessage(
    agentType: string,
    sessionId: string,
    message: string,
    searchEnabled = true
  ): Promise<ChatResponse> {
    return this.request('/chat', {
      method: 'POST',
      body: JSON.stringify({
        agent_type: agentType,
        session_id: sessionId,
        message,
        search_enabled: searchEnabled
      }),
    });
  }

  // File upload
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

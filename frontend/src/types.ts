export interface Session {
  session_id: string;
  agent_type: string;
  created_at: string;
  message_count: number;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  files?: string[];
  isTemporary?: boolean; // Для временных статусных сообщений
}

export interface SessionHistory {
  session_id: string;
  agent_type: string;
  user_id: string;
  created_at: string;
  messages: Message[];
  state: Record<string, any>;
}

export interface SessionFile {
  name: string;
  size: number;
  modified: number;
  path: string;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
}

export interface ModelInfo {
  id: string;
  display_name: string;
  provider: string;
  group?: string;
  max_context_tokens?: number;
  overall_power?: number;
  tags?: string[];
  is_default?: boolean;
}

// Детальная информация об использовании токенов за ход и за сессию
export interface ChatUsage {
  session_prompt_tokens: number;
  session_completion_tokens: number;
  session_total_tokens: number;
  last_prompt_tokens: number;
  last_completion_tokens: number;
  last_total_tokens: number;
  context_limit_tokens: number;
  context_used_tokens: number;
  context_usage_percent: number;
}

// Информация о активно используемой модели для сессии
export interface ActiveModelInfo {
  id: string;
  display_name: string;
  provider: string;
  max_context_tokens: number;
}

export interface ChatResponse {
  response: string;
  usage?: ChatUsage;
  model?: ActiveModelInfo;
}

// Настройки Coder Agent
export interface CoderConfig {
  use_tree_of_thoughts: boolean;
  num_branches: number;
  use_verifier: boolean;
  verifier_model_id?: string;
}

export interface ToolCall {
  tool: string;
  params: Record<string, any>;
  result?: any;
}

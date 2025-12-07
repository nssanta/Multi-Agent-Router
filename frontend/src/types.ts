export interface Session {
  /** ID сессии */
  session_id: string;
  /** Тип агента */
  agent_type: string;
  /** Дата создания */
  created_at: string;
  /** Количество сообщений */
  message_count: number;
}

export interface Message {
  /** Роль отправителя */
  role: 'user' | 'assistant';
  /** Содержимое сообщения */
  content: string;
  /** Временная метка */
  timestamp: string;
  /** Прикрепленные файлы */
  files?: string[];
  /** Флаг временного сообщения */
  isTemporary?: boolean;
}

export interface SessionHistory {
  /** ID сессии */
  session_id: string;
  /** Тип агента */
  agent_type: string;
  /** ID пользователя */
  user_id: string;
  /** Дата создания */
  created_at: string;
  /** История сообщений */
  messages: Message[];
  /** Состояние сессии */
  state: Record<string, any>;
}

export interface SessionFile {
  /** Имя файла */
  name: string;
  /** Размер файла в байтах */
  size: number;
  /** Время последнего изменения */
  modified: number;
  /** Путь к файлу */
  path: string;
}

export interface Agent {
  /** ID агента */
  id: string;
  /** Имя агента */
  name: string;
  /** Описание агента */
  description: string;
}

export interface ModelInfo {
  /** ID модели */
  id: string;
  /** Отображаемое имя */
  display_name: string;
  /** Провайдер модели */
  provider: string;
  /** Группа моделей */
  group?: string;
  /** Максимальный контекст */
  max_context_tokens?: number;
  /** Оценка мощности */
  overall_power?: number;
  /** Теги */
  tags?: string[];
  /** Является ли дефолтной */
  is_default?: boolean;
}

/** Детальная информация об использовании токенов за ход и за сессию */
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

/** Информация о активно используемой модели для сессии */
export interface ActiveModelInfo {
  id: string;
  display_name: string;
  provider: string;
  max_context_tokens: number;
}

export interface ChatResponse {
  /** Текст ответа */
  response: string;
  /** Использование токенов */
  usage?: ChatUsage;
  /** Информация о модели */
  model?: ActiveModelInfo;
}

/** Настройки Coder Agent */
export interface CoderConfig {
  use_tree_of_thoughts: boolean;
  num_branches: number;
  use_verifier: boolean;
  verifier_model_id?: string;
}

export interface ToolCall {
  /** Имя инструмента */
  tool: string;
  /** Параметры вызова */
  params: Record<string, any>;
  /** Результат выполнения */
  result?: any;
}
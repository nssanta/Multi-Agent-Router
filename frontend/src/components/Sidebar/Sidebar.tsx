import React, { useState, useEffect } from 'react';
import { Plus, FolderOpen, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { SessionList } from './SessionList';
import { api } from '../../services/api';
import type { Session, Agent, ModelInfo, CoderConfig } from '../../types';
import { CoderSettings, defaultCoderConfig } from '../Chat/CoderSettings';

interface SidebarProps {
  activeSessionId: string | null;
  onSelectSession: (session: Session) => void;
  onCreateSession: (agentType: string, coderConfig?: CoderConfig) => void;
  isOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeSessionId,
  onSelectSession,
  onCreateSession,
  isOpen = true,
  onClose,
}) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('dialog');
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [coderConfig, setCoderConfig] = useState<CoderConfig>(defaultCoderConfig);

  // Загружаем сессии и агентов
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);

      // Загружаем все данные параллельно, включая динамические free модели
      const [sessionsData, agentsData, modelsData, openrouterFreeData] = await Promise.all([
        api.listSessions(),
        api.getAgents(),
        api.getModels(),
        api.getOpenRouterFreeModels().catch(() => ({ models: [] })), // Fallback при ошибке
      ]);

      setSessions(sessionsData.sessions);
      // Фильтруем нежелательных агентов (DS, MLE) пока что
      const allowedAgents = ['coder', 'dialog', 'crypto'];
      const filteredAgents = (agentsData.agents || []).filter((a: Agent) => allowedAgents.includes(a.id));
      setAgents(filteredAgents);

      // Объединяем статические модели (Gemini) + динамические free OpenRouter
      const staticModels = (modelsData.models || []).filter((m: ModelInfo) => {
        // Для статических моделей берём только Gemini или явно помеченные free
        if (m.provider === 'openrouter') {
          return false; // Пропускаем статические OpenRouter, используем динамические
        }
        return true; // Gemini и другие
      });

      // Динамические free модели от OpenRouter API
      const dynamicFreeModels = openrouterFreeData.models || [];

      // Объединяем: сначала Gemini, потом OpenRouter free
      const availableModels = [...staticModels, ...dynamicFreeModels];

      setModels(availableModels);

      if (availableModels.length > 0) {
        const defaultModel =
          availableModels.find((m) => m.is_default) ?? availableModels[0];
        setSelectedModelId(defaultModel.id);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSession = async () => {
    try {
      const newSession = await api.createSession(selectedAgent, 'default', selectedModelId);
      setSessions([newSession, ...sessions]);
      // Передаём coderConfig если это coder agent
      if (selectedAgent === 'coder') {
        onCreateSession(selectedAgent, coderConfig);
      } else {
        onCreateSession(selectedAgent);
      }
      onSelectSession(newSession);
    } catch (error) {
      console.error('Failed to create session:', error);
      alert('Failed to create session');
    }
  };

  const handleDeleteSession = async (session: Session) => {
    try {
      await api.deleteSession(session.agent_type, session.session_id);
      setSessions(sessions.filter(s => s.session_id !== session.session_id));
    } catch (error) {
      console.error('Failed to delete session:', error);
      alert('Failed to delete session');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="w-80 bg-dark-surface border-r border-dark-border flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-dark-border">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold">AI Agent System</h1>
          {onClose && (
            <button onClick={onClose} className="md:hidden text-dark-muted hover:text-white">
              <X size={24} />
            </button>
          )}
        </div>

        {/* Agent selector */}
        <select
          value={selectedAgent}
          onChange={(e) => setSelectedAgent(e.target.value)}
          className="input mb-3"
          disabled={loading}
        >
          {agents.map(agent => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>

        {/* Model selector */}
        <select
          value={selectedModelId || ''}
          onChange={(e) => setSelectedModelId(e.target.value || undefined)}
          className="input mb-3"
          disabled={loading || models.length === 0}
        >
          {models.map(model => (
            <option key={model.id} value={model.id}>
              {model.display_name} ({model.provider})
            </option>
          ))}
        </select>

        {/* Coder Settings - показываем только для coder agent */}
        {selectedAgent === 'coder' && (
          <div className="mb-3">
            <CoderSettings
              settings={coderConfig}
              onChange={setCoderConfig}
              disabled={loading}
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={handleCreateSession}
            disabled={loading}
            className="btn-primary flex-1 flex items-center justify-center gap-2"
          >
            <Plus size={18} />
            New Session
          </button>

          <Link to="/browse" className="btn-secondary flex items-center justify-center">
            <FolderOpen size={18} />
          </Link>
        </div>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="text-center text-dark-muted py-8">Loading...</div>
        ) : (
          <SessionList
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelectSession={onSelectSession}
            onDeleteSession={handleDeleteSession}
          />
        )}
      </div>
    </div>
  );
};

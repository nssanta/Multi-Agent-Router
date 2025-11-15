import React from 'react';
import { SessionItem } from './SessionItem';
import type { Session } from '../../types';

interface SessionListProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (session: Session) => void;
  onDeleteSession: (session: Session) => void;
  agentType?: string;
}

export const SessionList: React.FC<SessionListProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  agentType,
}) => {
  // Filter by agent type if specified
  const filteredSessions = agentType
    ? sessions.filter(s => s.agent_type === agentType)
    : sessions;

  // Group by agent type
  const grouped = filteredSessions.reduce((acc, session) => {
    if (!acc[session.agent_type]) {
      acc[session.agent_type] = [];
    }
    acc[session.agent_type].push(session);
    return acc;
  }, {} as Record<string, Session[]>);

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([type, typeSessions]) => (
        <div key={type}>
          <h3 className="text-xs font-semibold text-dark-muted uppercase tracking-wider px-3 mb-2">
            {type} ({typeSessions.length})
          </h3>
          <div className="space-y-1">
            {typeSessions.map(session => (
              <SessionItem
                key={session.session_id}
                session={session}
                active={session.session_id === activeSessionId}
                onClick={() => onSelectSession(session)}
                onDelete={() => onDeleteSession(session)}
              />
            ))}
          </div>
        </div>
      ))}
      
      {filteredSessions.length === 0 && (
        <div className="text-center text-dark-muted py-8">
          <p className="text-sm">No sessions yet</p>
        </div>
      )}
    </div>
  );
};

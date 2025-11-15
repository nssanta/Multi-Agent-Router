import React, { useState, useEffect } from 'react';
import { Search, Loader } from 'lucide-react';
import { SessionCard } from './SessionCard';
import { api } from '../../services/api';
import type { Session } from '../../types';

export const FileBrowser: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [filesCache, setFilesCache] = useState<Record<string, any>>({});
  const [searchQuery, setSearchQuery] = useState('');
  const [filterAgent, setFilterAgent] = useState<string>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      setLoading(true);
      const data = await api.listSessions();
      setSessions(data.sessions);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSessionFiles = async (session: Session) => {
    const key = `${session.agent_type}/${session.session_id}`;
    if (filesCache[key]) return;

    try {
      const files = await api.listSessionFiles(session.agent_type, session.session_id);
      setFilesCache({ ...filesCache, [key]: files });
    } catch (error) {
      console.error('Failed to load files:', error);
    }
  };

  // Filter sessions
  const filteredSessions = sessions.filter(session => {
    const matchesSearch = session.session_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesAgent = filterAgent === 'all' || session.agent_type === filterAgent;
    return matchesSearch && matchesAgent;
  });

  // Group by agent type
  const agentTypes = Array.from(new Set(sessions.map(s => s.agent_type)));

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-dark-border">
        <h1 className="text-2xl font-bold mb-4">Browse Sessions</h1>
        
        <div className="flex gap-3">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-dark-muted" size={18} />
            <input
              type="text"
              placeholder="Search sessions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
            />
          </div>

          {/* Filter */}
          <select
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            className="input w-48"
          >
            <option value="all">All Agents</option>
            {agentTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>

        <div className="mt-3 text-sm text-dark-muted">
          {filteredSessions.length} session{filteredSessions.length !== 1 ? 's' : ''} found
        </div>
      </div>

      {/* Sessions grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader className="animate-spin text-blue-500" size={32} />
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="text-center text-dark-muted py-16">
            <p className="text-lg">No sessions found</p>
            <p className="text-sm mt-2">Try adjusting your filters</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredSessions.map(session => (
              <SessionCard
                key={session.session_id}
                session={session}
                files={filesCache[`${session.agent_type}/${session.session_id}`] || null}
                onLoadFiles={() => loadSessionFiles(session)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

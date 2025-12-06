import React, { useState } from 'react';
import { Menu } from 'lucide-react';
import { Sidebar } from '../components/Sidebar/Sidebar';
import { ChatWindow } from '../components/Chat/ChatWindow';
import type { Session } from '../types';

export const ChatPage: React.FC = () => {
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="h-screen flex overflow-hidden">
      {/* Menu button - Fixed position, always visible */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="fixed top-4 left-4 z-50 w-11 h-11 rounded-xl bg-dark-surface border border-dark-border hover:bg-dark-border text-white flex items-center justify-center shadow-lg transition-all"
        >
          <Menu size={24} />
        </button>
      )}

      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'block' : 'hidden'} md:block fixed md:relative z-40 h-full`}>
        <Sidebar
          activeSessionId={activeSession?.session_id || null}
          onSelectSession={(session) => {
            setActiveSession(session);
            setSidebarOpen(false); // Close sidebar on mobile after selecting
          }}
          onCreateSession={() => {}}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
      </div>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black bg-opacity-50 z-30"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Chat window */}
      <ChatWindow
        sessionId={activeSession?.session_id || null}
        agentType={activeSession?.agent_type || 'dialog'}
      />
    </div>
  );
};

import React from 'react';
import { MessageSquare, Trash2 } from 'lucide-react';
import type { Session } from '../../types';

interface SessionItemProps {
  session: Session;
  active?: boolean;
  onClick: () => void;
  onDelete: () => void;
}

export const SessionItem: React.FC<SessionItemProps> = ({ 
  session, 
  active, 
  onClick, 
  onDelete 
}) => {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this session?')) {
      onDelete();
    }
  };

  return (
    <div
      onClick={onClick}
      className={`group flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
        active ? 'bg-blue-600 text-white' : 'hover:bg-dark-surface'
      }`}
    >
      <MessageSquare size={18} className="flex-shrink-0" />
      
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">
          Session {session.session_id.substring(0, 8)}
        </p>
        <p className={`text-xs truncate ${active ? 'text-blue-100' : 'text-dark-muted'}`}>
          {session.message_count} messages • {new Date(session.created_at).toLocaleDateString()}
        </p>
      </div>

      <button
        onClick={handleDelete}
        className={`opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 
                    hover:text-red-500 ${active ? 'text-white' : 'text-dark-muted'}`}
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
};

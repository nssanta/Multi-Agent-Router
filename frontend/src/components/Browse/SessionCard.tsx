import React, { useState } from 'react';
import { Folder, File, Clock, ChevronDown, ChevronRight } from 'lucide-react';
import type { Session, SessionFile } from '../../types';

interface SessionCardProps {
  session: Session;
  files: { input_files: SessionFile[]; workspace_files: SessionFile[] } | null;
  onLoadFiles: () => void;
}

export const SessionCard: React.FC<SessionCardProps> = ({ session, files, onLoadFiles }) => {
  const [expanded, setExpanded] = useState(false);

  const toggleExpand = () => {
    if (!files && !expanded) {
      onLoadFiles();
    }
    setExpanded(!expanded);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <Folder className="text-blue-500" size={20} />
            <h3 className="font-semibold">
              {session.agent_type} / {session.session_id.substring(0, 8)}
            </h3>
          </div>
          
          <div className="flex items-center gap-4 text-sm text-dark-muted">
            <span className="flex items-center gap-1">
              <Clock size={14} />
              {new Date(session.created_at).toLocaleString()}
            </span>
            <span>{session.message_count} messages</span>
          </div>
        </div>

        <button
          onClick={toggleExpand}
          className="text-dark-muted hover:text-white transition-colors"
        >
          {expanded ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
        </button>
      </div>

      {/* Files list */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-dark-border space-y-3">
          {!files ? (
            <div className="text-sm text-dark-muted">Loading files...</div>
          ) : (
            <>
              {/* Input files */}
              {files.input_files.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Input Files</h4>
                  <div className="space-y-1">
                    {files.input_files.map((file, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-2 text-sm text-dark-text bg-dark-bg px-3 py-2 rounded"
                      >
                        <File size={14} className="text-blue-400" />
                        <span className="flex-1">{file.name}</span>
                        <span className="text-dark-muted">{formatSize(file.size)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Workspace files */}
              {files.workspace_files.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Workspace Files</h4>
                  <div className="space-y-1">
                    {files.workspace_files.map((file, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-2 text-sm text-dark-text bg-dark-bg px-3 py-2 rounded"
                      >
                        <File size={14} className="text-green-400" />
                        <span className="flex-1 font-mono text-xs">{file.path}</span>
                        <span className="text-dark-muted">{formatSize(file.size)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {files.input_files.length === 0 && files.workspace_files.length === 0 && (
                <div className="text-sm text-dark-muted">No files in this session</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

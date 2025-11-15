import React, { useState, useRef } from 'react';
import { Send, Paperclip, X, Search, SearchX } from 'lucide-react';

interface MessageInputProps {
  onSend: (message: string, files?: File[], searchEnabled?: boolean) => void;
  disabled?: boolean;
}

export const MessageInput: React.FC<MessageInputProps> = ({ onSend, disabled }) => {
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [searchEnabled, setSearchEnabled] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (message.trim() || files.length > 0) {
      onSend(message.trim(), files, searchEnabled);
      setMessage('');
      setFiles([]);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles([...files, ...Array.from(e.target.files)]);
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div className="sticky bottom-0 bg-dark-bg border-t border-dark-border p-3 md:p-4 safe-area-bottom">
      {/* Attached files preview */}
      {files.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {files.map((file, idx) => (
            <div
              key={idx}
              className="flex items-center gap-2 bg-dark-surface px-3 py-1.5 rounded-lg text-sm"
            >
              <Paperclip size={14} />
              <span className="max-w-[150px] truncate">{file.name}</span>
              <button
                onClick={() => removeFile(idx)}
                className="text-dark-muted hover:text-red-500 transition-colors"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="flex gap-2 items-end">
        {/* Web search toggle */}
        <button
          onClick={() => setSearchEnabled(!searchEnabled)}
          disabled={disabled}
          className={`flex-shrink-0 w-11 h-11 md:w-12 md:h-12 rounded-xl font-medium transition-all flex items-center justify-center ${
            searchEnabled 
              ? 'bg-green-600 hover:bg-green-700 text-white shadow-lg' 
              : 'bg-dark-surface hover:bg-dark-border text-dark-muted border border-dark-border'
          }`}
          title={searchEnabled ? "Web search enabled" : "Web search disabled"}
        >
          {searchEnabled ? <Search size={22} /> : <SearchX size={22} />}
        </button>

        {/* File attach button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          className="btn-secondary flex-shrink-0 w-11 h-11 md:w-12 md:h-12 rounded-xl flex items-center justify-center"
          title="Attach file"
        >
          <Paperclip size={22} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Message input */}
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={disabled}
          placeholder="Type your message..."
          className="input flex-1 resize-none rounded-xl"
          rows={1}
          style={{ minHeight: '44px', maxHeight: '120px' }}
        />

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={disabled || (!message.trim() && files.length === 0)}
          className="btn-primary flex-shrink-0 w-11 h-11 md:w-12 md:h-12 rounded-xl flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
        >
          <Send size={22} />
        </button>
      </div>
    </div>
  );
};

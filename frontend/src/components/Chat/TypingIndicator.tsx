import React from 'react';
import { Bot } from 'lucide-react';

interface TypingIndicatorProps {
    status?: 'thinking' | 'searching' | 'writing' | 'processing';
}

const statusConfig = {
    thinking: { emoji: '🧠', text: 'Анализирую запрос' },
    searching: { emoji: '🔍', text: 'Ищу информацию' },
    writing: { emoji: '✍️', text: 'Формирую ответ' },
    processing: { emoji: '⚙️', text: 'Обрабатываю' },
};

export const TypingIndicator: React.FC<TypingIndicatorProps> = ({
    status = 'thinking'
}) => {
    const config = statusConfig[status];

    return (
        <div className="flex gap-3">
            {/* Avatar */}
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-600 flex items-center justify-center">
                <Bot size={20} />
            </div>

            {/* Typing indicator */}
            <div className="flex flex-col items-start">
                <div className="bg-dark-surface rounded-lg p-4 flex items-center gap-3">
                    {/* Animated dots */}
                    <div className="flex gap-1">
                        <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>

                    {/* Status text */}
                    <span className="text-sm text-dark-muted">
                        {config.emoji} {config.text}
                        <span className="inline-block w-6 text-left typing-dots">...</span>
                    </span>
                </div>
            </div>

            {/* CSS for typing dots animation */}
            <style>{`
        @keyframes typing-dots {
          0%, 20% { content: '.'; }
          40% { content: '..'; }
          60%, 100% { content: '...'; }
        }
        .typing-dots {
          animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
        </div>
    );
};

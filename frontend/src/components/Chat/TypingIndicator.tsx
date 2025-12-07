import React from 'react';
import { Bot } from 'lucide-react';

interface TypingIndicatorProps {
    status?: 'thinking' | 'searching' | 'writing' | 'processing';
}

const statusConfig = {
    thinking: { emoji: '🧠', text: 'Думаю' },
    searching: { emoji: '🔍', text: 'Ищу информацию' },
    writing: { emoji: '✍️', text: 'Пишу код' },
    processing: { emoji: '⚙️', text: 'Обрабатываю' },
    running: { emoji: '▶️', text: 'Выполняю инструмент' },
    retrying: { emoji: '🔄', text: 'Повторяю попытку' },
};

// Умное определение статуса из текста
const getStatusFromText = (text: string): keyof typeof statusConfig => {
    const lower = text.toLowerCase();
    if (lower.includes('retry') || lower.includes('retrying')) return 'retrying';
    if (lower.includes('running') || lower.includes('tool') || lower.includes('executing')) return 'running';
    if (lower.includes('writing') || lower.includes('file')) return 'writing';
    if (lower.includes('search')) return 'searching';
    if (lower.includes('processing')) return 'processing';
    return 'thinking';
};

export const TypingIndicator: React.FC<TypingIndicatorProps & { customText?: string | null }> = ({
    status = 'thinking',
    customText
}) => {
    // Автоопределение статуса из customText
    const effectiveStatus = customText ? getStatusFromText(customText) : status;
    const config = statusConfig[effectiveStatus];
    const displayText = customText || config.text;

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
                    <span className="text-sm text-dark-muted flex items-center gap-2">
                        {config.emoji} {displayText}
                        {!customText && <span className="inline-block w-6 text-left typing-dots">...</span>}
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

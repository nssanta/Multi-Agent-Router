import React, { useEffect, useRef } from 'react';
import { Message } from './Message';
import type { Message as MessageType } from '../../types';

interface MessageListProps {
  messages: MessageType[];
}

export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 pt-16 md:pt-4 space-y-6">
      {messages.length === 0 ? (
        <div className="h-full flex items-center justify-center">
          <div className="text-center text-dark-muted">
            <p className="text-lg">No messages yet</p>
            <p className="text-sm mt-2">Start a conversation with the AI agent</p>
          </div>
        </div>
      ) : (
        <>
          {messages.map((msg, idx) => (
            <Message key={idx} message={msg} />
          ))}
          <div ref={endRef} />
        </>
      )}
    </div>
  );
};

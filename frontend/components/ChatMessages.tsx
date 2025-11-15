import React from 'react';

interface ChatMessagesProps {
  messages: Array<{ id: string; role: 'user' | 'assistant'; content: string }>;
}

export default function ChatMessages({ messages }: ChatMessagesProps) {
  if (!messages.length) {
    return <div className="rounded border p-4 text-sm text-gray-500">No messages yet.</div>;
  }

  return (
    <div className="space-y-2">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`rounded border p-3 ${
            message.role === 'assistant' ? 'bg-gray-100' : 'bg-white'
          }`}
        >
          <strong className="capitalize">{message.role}:</strong> {message.content}
        </div>
      ))}
    </div>
  );
}

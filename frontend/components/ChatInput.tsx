'use client';

import React, { useState } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
}

export default function ChatInput({ onSend }: ChatInputProps) {
  const [message, setMessage] = useState('');

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!message.trim()) {
      return;
    }
    onSend(message);
    setMessage('');
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="Type a message"
        className="flex-1 rounded border px-3 py-2"
      />
      <button type="submit" className="rounded bg-blue-600 px-3 py-2 text-white">
        Send
      </button>
    </form>
  );
}

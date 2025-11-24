/**
 * WebSocket Client for Real-Time Updates
 */
import React from 'react';
import { getApiUrl } from './api-client';

export type WebSocketEventType = 
  | 'activity'
  | 'notification'
  | 'task_update'
  | 'connection'
  | 'pong'
  | 'error';

export interface WebSocketMessage {
  type: WebSocketEventType;
  [key: string]: any;
}

export type WebSocketEventHandler = (message: WebSocketMessage) => void;

class WebSocketManager {
  private ws: WebSocket | null = null;
  private userId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private eventHandlers: Map<WebSocketEventType, Set<WebSocketEventHandler>> = new Map();
  private isConnecting = false;

  connect(userId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        if (this.userId === userId) {
          resolve();
          return;
        }
        this.disconnect();
      }

      if (this.isConnecting) {
        reject(new Error('Connection already in progress'));
        return;
      }

      this.userId = userId;
      this.isConnecting = true;

      const apiUrl = getApiUrl();
      const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
      const wsUrl = `${wsProtocol}://${apiUrl.replace(/^https?:\/\//, '')}/api/ws?user_id=${userId}`;

      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (e) {
            console.error('Error parsing WebSocket message:', e);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.isConnecting = false;
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('WebSocket disconnected');
          this.isConnecting = false;
          this.ws = null;

          // Attempt to reconnect if not manually disconnected
          if (this.userId) {
            this.attemptReconnect();
          }
        };
      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.userId = null;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff

    setTimeout(() => {
      if (this.userId) {
        console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.connect(this.userId).catch((error) => {
          console.error('Reconnection failed:', error);
        });
      }
    }, delay);
  }

  private handleMessage(message: WebSocketMessage): void {
    // Call handlers for this event type
    const handlers = this.eventHandlers.get(message.type);
    if (handlers) {
      handlers.forEach(handler => handler(message));
    }

    // Also call handlers for 'all' events
    const allHandlers = this.eventHandlers.get('*' as WebSocketEventType);
    if (allHandlers) {
      allHandlers.forEach(handler => handler(message));
    }
  }

  on(eventType: WebSocketEventType | '*', handler: WebSocketEventHandler): () => void {
    if (!this.eventHandlers.has(eventType as WebSocketEventType)) {
      this.eventHandlers.set(eventType as WebSocketEventType, new Set());
    }
    this.eventHandlers.get(eventType as WebSocketEventType)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.eventHandlers.get(eventType as WebSocketEventType);
      if (handlers) {
        handlers.delete(handler);
      }
    };
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not open. Message not sent.');
    }
  }

  ping(): void {
    this.send({
      type: 'ping',
      timestamp: Date.now()
    });
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Singleton instance
export const wsManager = new WebSocketManager();

// React hook for using WebSocket
export function useWebSocket(userId: string | null) {
  const [isConnected, setIsConnected] = React.useState(false);
  const [lastMessage, setLastMessage] = React.useState<WebSocketMessage | null>(null);

  React.useEffect(() => {
    if (!userId) {
      wsManager.disconnect();
      setIsConnected(false);
      return;
    }

    wsManager.connect(userId)
      .then(() => setIsConnected(true))
      .catch(() => setIsConnected(false));

    const unsubscribe = wsManager.on('*', (message) => {
      setLastMessage(message);
    });

    return () => {
      unsubscribe();
      // Don't disconnect on unmount - keep connection alive
    };
  }, [userId]);

  // Update isConnected when connection state changes
  React.useEffect(() => {
    const checkInterval = setInterval(() => {
      setIsConnected(wsManager.isConnected);
    }, 1000);

    return () => clearInterval(checkInterval);
  }, []);

  return {
    isConnected,
    lastMessage,
    send: wsManager.send.bind(wsManager),
    ping: wsManager.ping.bind(wsManager),
  };
}


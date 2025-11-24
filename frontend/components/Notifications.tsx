'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type Notification = {
  id: string;
  type: 'high_fit' | 'follow_up_overdue' | 'messages_ready' | 'top_prospects' | 'weekly_insights';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  link?: string;
  priority: 'high' | 'medium' | 'low';
};

type NotificationProps = {
  userId?: string;
};

export default function Notifications({ userId = 'dev-user' }: NotificationProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadNotifications();
    // Poll for new notifications every 30 seconds
    const interval = setInterval(loadNotifications, 30000);
    return () => clearInterval(interval);
  }, [userId]);

  const loadNotifications = async () => {
    if (!API_URL) {
      setLoading(false);
      return;
    }

    try {
      // TODO: Replace with actual API endpoint
      // For now, use mock notifications
      const mockNotifications: Notification[] = [
        {
          id: '1',
          type: 'high_fit',
          title: '🚨 High-Fit Prospect Detected',
          message: 'Sarah Johnson (TechEd Solutions) has a 92% fit score',
          timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          read: false,
          link: '/prospects',
          priority: 'high',
        },
        {
          id: '2',
          type: 'follow_up_overdue',
          title: '🔥 Follow-Up Overdue',
          message: 'Emily Rodriguez - Check-in was due yesterday',
          timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
          read: false,
          link: '/calendar',
          priority: 'high',
        },
        {
          id: '3',
          type: 'messages_ready',
          title: '📩 Outreach Messages Ready',
          message: '5 DM variants generated for Michael Chen',
          timestamp: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
          read: false,
          link: '/outreach/2',
          priority: 'medium',
        },
        {
          id: '4',
          type: 'top_prospects',
          title: '⭐ Top Prospects This Week',
          message: 'Your top 5 prospects are ready for review',
          timestamp: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
          read: true,
          link: '/prospects',
          priority: 'medium',
        },
        {
          id: '5',
          type: 'weekly_insights',
          title: '📊 Weekly Insights Ready',
          message: 'Your weekly performance report is available',
          timestamp: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
          read: true,
          link: '/campaigns',
          priority: 'low',
        },
      ];

      setNotifications(mockNotifications);
    } catch (err) {
      console.error('Failed to load notifications:', err);
    } finally {
      setLoading(false);
    }
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  const markAsRead = (id: string) => {
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'low':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="relative">
      {/* Bell Icon */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 block h-5 w-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center font-bold">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          {/* Panel */}
          <div className="absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-lg border border-gray-200 z-50 max-h-[600px] flex flex-col">
            {/* Header */}
            <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-4 py-3 flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">Notifications</h3>
              <div className="flex items-center space-x-2">
                {unreadCount > 0 && (
                  <button
                    onClick={markAllAsRead}
                    className="text-xs text-blue-100 hover:text-white transition-colors"
                  >
                    Mark all read
                  </button>
                )}
                <button
                  onClick={() => setIsOpen(false)}
                  className="text-white hover:text-blue-100"
                >
                  ×
                </button>
              </div>
            </div>

            {/* Notifications List */}
            <div className="overflow-y-auto flex-1">
              {loading ? (
                <div className="p-4 text-center text-gray-500">Loading...</div>
              ) : notifications.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <div className="text-4xl mb-2">🔔</div>
                  <p>No notifications</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {notifications.map(notification => (
                    <div
                      key={notification.id}
                      className={`p-4 hover:bg-gray-50 transition-colors cursor-pointer ${
                        !notification.read ? 'bg-blue-50/50' : ''
                      }`}
                      onClick={() => {
                        markAsRead(notification.id);
                        setIsOpen(false);
                      }}
                    >
                      {notification.link ? (
                        <Link href={notification.link} className="block">
                          <div className="flex items-start justify-between mb-1">
                            <h4 className={`text-sm font-semibold ${!notification.read ? 'text-gray-900' : 'text-gray-700'}`}>
                              {notification.title}
                            </h4>
                            {!notification.read && (
                              <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1 ml-2" />
                            )}
                          </div>
                          <p className="text-sm text-gray-600 mb-2">{notification.message}</p>
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-gray-500">{formatTimestamp(notification.timestamp)}</span>
                            <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getPriorityColor(notification.priority)}`}>
                              {notification.priority}
                            </span>
                          </div>
                        </Link>
                      ) : (
                        <div>
                          <div className="flex items-start justify-between mb-1">
                            <h4 className={`text-sm font-semibold ${!notification.read ? 'text-gray-900' : 'text-gray-700'}`}>
                              {notification.title}
                            </h4>
                            {!notification.read && (
                              <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1 ml-2" />
                            )}
                          </div>
                          <p className="text-sm text-gray-600 mb-2">{notification.message}</p>
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-gray-500">{formatTimestamp(notification.timestamp)}</span>
                            <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getPriorityColor(notification.priority)}`}>
                              {notification.priority}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="border-t border-gray-200 px-4 py-3 bg-gray-50">
              <Link
                href="/notifications"
                className="text-sm text-blue-600 hover:text-blue-800 text-center block"
                onClick={() => setIsOpen(false)}
              >
                View all notifications →
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
}


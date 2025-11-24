'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getApiUrl } from '@/lib/api-client';

type FollowUpEvent = {
  id: string;
  prospect_id: string;
  prospect_name: string;
  company?: string;
  scheduled_date: string; // ISO date string
  type: 'initial' | 'follow_up' | 'check_in' | 'nurture';
  status: 'pending' | 'completed' | 'overdue';
  notes?: string;
  last_contact?: string;
  suggested_message?: string;
};

type CalendarDay = {
  date: Date;
  events: FollowUpEvent[];
  isToday: boolean;
  isCurrentMonth: boolean;
};

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [events, setEvents] = useState<FollowUpEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<FollowUpEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'month' | 'week'>('month');

  useEffect(() => {
    loadEvents();
  }, [currentDate]);

  const loadEvents = async () => {
    if (!API_URL) {
      setError('API URL not configured');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      
      // Calculate date range for current month view
      const year = currentDate.getFullYear();
      const month = currentDate.getMonth();
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      const startDate = firstDay.toISOString().split('T')[0];
      const endDate = lastDay.toISOString().split('T')[0];

      const params = new URLSearchParams({
        user_id: 'dev-user',
        start_date: startDate,
        end_date: endDate,
        limit: '500',
      });

      const response = await fetch(`${API_URL}/api/calendar/?${params.toString()}`);
      
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.events) {
          setEvents(data.events.map((e: any) => ({
            id: e.id,
            prospect_id: e.prospect_id,
            prospect_name: e.prospect_name || 'Unknown',
            company: e.company,
            scheduled_date: e.scheduled_date,
            type: e.type,
            status: e.status,
            notes: e.notes,
            last_contact: e.last_contact,
            suggested_message: e.suggested_message,
          })));
          setError(null);
          return;
        }
      }
      
      // Fallback to mock data if API fails or returns no data
      const mockEvents: FollowUpEvent[] = [
        {
          id: '1',
          prospect_id: '1',
          prospect_name: 'Sarah Johnson',
          company: 'TechEd Solutions',
          scheduled_date: new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          type: 'follow_up',
          status: 'pending',
          last_contact: '2 days ago',
          suggested_message: 'Following up on our conversation about AI tools for K-12...',
        },
        {
          id: '2',
          prospect_id: '3',
          prospect_name: 'Emily Rodriguez',
          company: 'Future Schools Inc',
          scheduled_date: new Date().toISOString().split('T')[0],
          type: 'check_in',
          status: 'overdue',
          last_contact: '5 days ago',
          suggested_message: 'Quick check-in to see how things are going...',
        },
        {
          id: '3',
          prospect_id: '2',
          prospect_name: 'Michael Chen',
          company: 'InnovateEd',
          scheduled_date: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          type: 'nurture',
          status: 'pending',
          last_contact: '1 week ago',
        },
      ];

      setEvents(mockEvents);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events');
    } finally {
      setLoading(false);
    }
  };

  const getDaysInMonth = (date: Date): CalendarDay[] => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    const days: CalendarDay[] = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Add previous month's trailing days
    for (let i = 0; i < startingDayOfWeek; i++) {
      const date = new Date(year, month, -i);
      days.unshift({
        date,
        events: [],
        isToday: false,
        isCurrentMonth: false,
      });
    }

    // Add current month's days
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day);
      const dateStr = date.toISOString().split('T')[0];
      const dayEvents = events.filter(e => e.scheduled_date === dateStr);
      
      const dayObj: CalendarDay = {
        date,
        events: dayEvents,
        isToday: date.getTime() === today.getTime(),
        isCurrentMonth: true,
      };
      days.push(dayObj);
    }

    // Fill remaining days to complete the grid (42 days = 6 weeks)
    const remainingDays = 42 - days.length;
    for (let day = 1; day <= remainingDays; day++) {
      const date = new Date(year, month + 1, day);
      days.push({
        date,
        events: [],
        isToday: false,
        isCurrentMonth: false,
      });
    }

    return days;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'overdue':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'initial':
        return '👋';
      case 'follow_up':
        return '📧';
      case 'check_in':
        return '💬';
      case 'nurture':
        return '🌱';
      default:
        return '📅';
    }
  };

  const navigateMonth = (direction: 'prev' | 'next') => {
    setCurrentDate(prev => {
      const newDate = new Date(prev);
      newDate.setMonth(prev.getMonth() + (direction === 'next' ? 1 : -1));
      return newDate;
    });
  };

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const calendarDays = getDaysInMonth(currentDate);

  const overdueCount = events.filter(e => e.status === 'overdue').length;
  const todayCount = events.filter(e => {
    const today = new Date().toISOString().split('T')[0];
    return e.scheduled_date === today && e.status === 'pending';
  }).length;

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <Link href="/" className="text-blue-600 hover:underline text-sm mb-2 inline-block">
              ← Back to Home
            </Link>
            <h1 className="text-3xl font-bold text-gray-900">Follow-Up Calendar</h1>
            <p className="text-gray-600 mt-1">Schedule and track your outreach follow-ups</p>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={() => setViewMode('month')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                viewMode === 'month'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              Month
            </button>
            <button
              onClick={() => setViewMode('week')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                viewMode === 'week'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              Week
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-gray-900">{todayCount}</div>
                <div className="text-sm text-gray-600">Due Today</div>
              </div>
              <div className="text-3xl">📅</div>
            </div>
          </div>
          <div className="bg-red-50 rounded-lg border border-red-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-red-600">{overdueCount}</div>
                <div className="text-sm text-red-600">Overdue</div>
              </div>
              <div className="text-3xl">🚨</div>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-gray-900">{events.length}</div>
                <div className="text-sm text-gray-600">Total Scheduled</div>
              </div>
              <div className="text-3xl">📋</div>
            </div>
          </div>
        </div>

        {/* Calendar */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          {/* Calendar Header */}
          <div className="bg-gray-50 border-b border-gray-200 px-6 py-4 flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => navigateMonth('prev')}
                className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
              >
                ←
              </button>
              <h2 className="text-xl font-semibold text-gray-900">
                {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
              </h2>
              <button
                onClick={() => navigateMonth('next')}
                className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
              >
                →
              </button>
              <button
                onClick={() => setCurrentDate(new Date())}
                className="text-sm text-blue-600 hover:underline"
              >
                Today
              </button>
            </div>
          </div>

          {/* Calendar Grid */}
          <div className="p-6">
            {/* Weekday Headers */}
            <div className="grid grid-cols-7 gap-2 mb-2">
              {weekDays.map(day => (
                <div key={day} className="text-center text-sm font-medium text-gray-600 py-2">
                  {day}
                </div>
              ))}
            </div>

            {/* Calendar Days */}
            <div className="grid grid-cols-7 gap-2">
              {calendarDays.map((day, idx) => (
                <div
                  key={idx}
                  className={`min-h-[100px] border rounded-lg p-2 ${
                    day.isCurrentMonth ? 'bg-white' : 'bg-gray-50'
                  } ${
                    day.isToday ? 'ring-2 ring-blue-500' : ''
                  } ${
                    day.events.length > 0 ? 'cursor-pointer hover:bg-gray-50' : ''
                  }`}
                  onClick={() => day.events.length > 0 && setSelectedEvent(day.events[0])}
                >
                  <div
                    className={`text-sm font-medium mb-1 ${
                      day.isCurrentMonth ? 'text-gray-900' : 'text-gray-400'
                    } ${day.isToday ? 'text-blue-600' : ''}`}
                  >
                    {day.date.getDate()}
                  </div>
                  <div className="space-y-1">
                    {day.events.slice(0, 2).map(event => (
                      <div
                        key={event.id}
                        className={`text-xs p-1 rounded border ${getStatusColor(event.status)} truncate`}
                        title={`${event.prospect_name} - ${event.type}`}
                      >
                        <span className="mr-1">{getTypeIcon(event.type)}</span>
                        {event.prospect_name}
                      </div>
                    ))}
                    {day.events.length > 2 && (
                      <div className="text-xs text-gray-500">
                        +{day.events.length - 2} more
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Event Detail Modal */}
        {selectedEvent && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-4 flex items-center justify-between">
                <h3 className="text-xl font-bold text-white">Follow-Up Details</h3>
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="text-white hover:text-blue-100 text-2xl"
                >
                  ×
                </button>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700">Prospect</label>
                  <p className="text-lg font-semibold text-gray-900">{selectedEvent.prospect_name}</p>
                  {selectedEvent.company && (
                    <p className="text-sm text-gray-600">{selectedEvent.company}</p>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700">Scheduled Date</label>
                    <p className="text-gray-900">{new Date(selectedEvent.scheduled_date).toLocaleDateString()}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Type</label>
                    <p className="text-gray-900 capitalize">{selectedEvent.type.replace('_', ' ')}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Status</label>
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(selectedEvent.status)}`}>
                      {selectedEvent.status}
                    </span>
                  </div>
                  {selectedEvent.last_contact && (
                    <div>
                      <label className="text-sm font-medium text-gray-700">Last Contact</label>
                      <p className="text-gray-900">{selectedEvent.last_contact}</p>
                    </div>
                  )}
                </div>
                {selectedEvent.suggested_message && (
                  <div>
                    <label className="text-sm font-medium text-gray-700">Suggested Message</label>
                    <div className="mt-1 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-sm text-gray-700">{selectedEvent.suggested_message}</p>
                    </div>
                  </div>
                )}
                <div className="flex space-x-2 pt-4 border-t">
                  <Link
                    href={`/outreach/${selectedEvent.prospect_id}`}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-center transition-colors"
                  >
                    Generate Follow-Up Message
                  </Link>
                  <button
                    onClick={() => {
                      // TODO: Mark as completed
                      alert('Mark as completed (functionality coming soon)');
                    }}
                    className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                  >
                    Mark Completed
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}
      </div>
    </main>
  );
}


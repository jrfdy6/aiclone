'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { outreachAPI, type WeeklyCadenceEntry } from '@/lib/api';
import { format, startOfWeek, addDays, isSameDay } from 'date-fns';

export default function SchedulerPage() {
  const [user_id] = useState('demo-user-123'); // TODO: Get from auth
  const [targetConnections, setTargetConnections] = useState(40);
  const [targetFollowups, setTargetFollowups] = useState(30);
  const [selectedDate, setSelectedDate] = useState(new Date());

  // Generate weekly cadence
  const { data: cadenceData, isLoading, refetch } = useQuery({
    queryKey: ['weekly-cadence', user_id],
    queryFn: () => outreachAPI.weeklyCadence(user_id, targetConnections, targetFollowups),
    enabled: !!user_id,
  });

  const entries = cadenceData?.entries || [];
  const weekStart = cadenceData?.week_start ? new Date(cadenceData.week_start) : startOfWeek(new Date());
  const weekEnd = cadenceData?.week_end ? new Date(cadenceData.week_end) : addDays(weekStart, 6);

  // Group entries by day
  const entriesByDay: Record<string, WeeklyCadenceEntry[]> = {};
  entries.forEach((entry) => {
    if (!entriesByDay[entry.date]) {
      entriesByDay[entry.date] = [];
    }
    entriesByDay[entry.date].push(entry);
  });

  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  const getEntriesForDay = (date: Date) => {
    const dateStr = format(date, 'yyyy-MM-dd');
    return entriesByDay[dateStr] || [];
  };

  const getUrgentEntries = () => {
    const today = new Date();
    return entries.filter((entry) => {
      const entryDate = new Date(entry.date);
      return entryDate <= today;
    });
  };

  const urgentEntries = getUrgentEntries();

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Follow-Up Scheduler</h1>
            <p className="mt-1 text-sm text-gray-500">
              Weekly outreach cadence and follow-up tracking
            </p>
          </div>
          <div className="flex space-x-3">
            <div className="flex items-center space-x-2">
              <label className="text-sm text-gray-600">Target Connections:</label>
              <input
                type="number"
                value={targetConnections}
                onChange={(e) => setTargetConnections(Number(e.target.value))}
                className="w-20 rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <div className="flex items-center space-x-2">
              <label className="text-sm text-gray-600">Target Follow-ups:</label>
              <input
                type="number"
                value={targetFollowups}
                onChange={(e) => setTargetFollowups(Number(e.target.value))}
                className="w-20 rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={() => refetch()}
              disabled={isLoading}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Generating...' : 'Generate Weekly Cadence'}
            </button>
          </div>
        </div>

        {/* Urgent Alerts */}
        {urgentEntries.length > 0 && (
          <div className="mb-6 rounded-lg border-l-4 border-red-500 bg-red-50 p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-red-900">
                  ⚠️ {urgentEntries.length} Urgent Follow-ups Needed
                </h3>
                <p className="text-sm text-red-700">
                  These prospects need immediate attention - scheduled dates have passed
                </p>
              </div>
              <button className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700">
                View All Urgent
              </button>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">Total Outreach</div>
            <div className="text-2xl font-bold text-gray-900">{entries.length}</div>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">Connection Requests</div>
            <div className="text-2xl font-bold text-blue-600">
              {entries.filter((e) => e.outreach_type === 'connection_request').length}
            </div>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">Follow-ups</div>
            <div className="text-2xl font-bold text-purple-600">
              {entries.filter((e) => e.outreach_type !== 'connection_request').length}
            </div>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">Week Range</div>
            <div className="text-sm font-medium text-gray-900">
              {format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d')}
            </div>
          </div>
        </div>

        {/* Weekly Calendar */}
        <div className="rounded-lg bg-white shadow">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {weekDays.map((day) => (
                    <th
                      key={day.toISOString()}
                      className={`px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 ${
                        isSameDay(day, new Date()) ? 'bg-blue-50' : ''
                      }`}
                    >
                      <div>{format(day, 'EEE')}</div>
                      <div className="text-sm font-normal text-gray-900">{format(day, 'MMM d')}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {/* Time slots */}
                {['9:00 AM', '12:00 PM', '2:00 PM', '4:00 PM'].map((time) => (
                  <tr key={time}>
                    {weekDays.map((day) => {
                      const dayEntries = getEntriesForDay(day);
                      const timeEntries = dayEntries.filter((e) => e.time === time);

                      return (
                        <td
                          key={`${day.toISOString()}-${time}`}
                          className="h-32 border-r border-gray-200 px-4 py-2 align-top"
                        >
                          {timeEntries.length > 0 && (
                            <div className="space-y-2">
                              {timeEntries.map((entry) => (
                                <div
                                  key={entry.prospect_id}
                                  className={`rounded-lg border-l-4 p-2 text-xs ${
                                    entry.outreach_type === 'connection_request'
                                      ? 'border-blue-500 bg-blue-50'
                                      : 'border-purple-500 bg-purple-50'
                                  }`}
                                >
                                  <div className="font-medium text-gray-900">{entry.prospect_name}</div>
                                  <div className="text-gray-600">
                                    {entry.outreach_type === 'connection_request' ? '🔗 Connect' : '💬 Follow-up'}
                                  </div>
                                  <div className="text-gray-500">{entry.segment}</div>
                                  <button className="mt-1 text-blue-600 hover:underline">
                                    View →
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Distribution Stats */}
        {cadenceData?.distribution && (
          <div className="mt-6 rounded-lg bg-white p-6 shadow">
            <h3 className="mb-4 text-lg font-semibold text-gray-900">Segment Distribution</h3>
            <div className="grid grid-cols-3 gap-4">
              {Object.entries(cadenceData.distribution).map(([segment, count]) => (
                <div key={segment} className="rounded-lg bg-gray-50 p-4">
                  <div className="text-sm text-gray-500">{segment.replace('_', ' ')}</div>
                  <div className="text-2xl font-bold text-gray-900">{count}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


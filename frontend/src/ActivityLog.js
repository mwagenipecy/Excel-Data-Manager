import React, { useState, useEffect, useCallback } from 'react';
import { ScrollText, RefreshCw } from 'lucide-react';
import { authFetch } from './api';

const ACTION_LABELS = {
  login: 'Signed in',
  logout: 'Signed out',
  upload_document: 'Uploaded document',
  send_email: 'Sent emails',
  login_requested: 'Requested login',
  login_approved: 'Approved login',
  login_denied: 'Denied login',
  session_ended: 'Session ended',
};

const ActivityLog = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch('/auth/activity-log?limit=200');
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch (err) {
      console.error('Failed to load activity log:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const formatTime = (iso) => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <ScrollText className="h-6 w-6 text-red-600" />
          <h2 className="text-lg font-semibold text-gray-900">User Activity Log</h2>
        </div>
        <button
          type="button"
          onClick={fetchLogs}
          disabled={loading}
          className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {loading && logs.length === 0 ? (
        <p className="text-gray-500 text-center py-8">Loading activity log…</p>
      ) : logs.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No activity recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Time</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">User</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Action</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.map((entry, idx) => (
                <tr key={`${entry.timestamp}-${idx}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-gray-600">
                    {formatTime(entry.timestamp)}
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900">{entry.email}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-800">
                      {ACTION_LABELS[entry.action] || entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 max-w-md truncate">
                    {entry.details && Object.keys(entry.details).length > 0
                      ? JSON.stringify(entry.details)
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ActivityLog;

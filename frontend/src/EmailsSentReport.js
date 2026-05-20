import React, { useState, useEffect, useCallback } from 'react';
import { Mail, RefreshCw, CheckCircle, Calendar } from 'lucide-react';
import { authFetch } from './api';

const EmailsSentReport = () => {
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState(null);
  const [filterMode, setFilterMode] = useState('all');
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedMonth, setSelectedMonth] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const buildQuery = useCallback(() => {
    const params = new URLSearchParams();
    if (filterMode === 'day' && selectedDate) {
      params.set('date', selectedDate);
    } else if (filterMode === 'month' && selectedMonth) {
      params.set('month', selectedMonth);
    } else if (filterMode === 'range') {
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
    }
    const qs = params.toString();
    return qs ? `?${qs}` : '';
  }, [filterMode, selectedDate, selectedMonth, dateFrom, dateTo]);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`/email/sent-report${buildQuery()}`);
      if (res.ok) {
        setReport(await res.json());
      }
    } catch (err) {
      console.error('Failed to load sent report:', err);
    } finally {
      setLoading(false);
    }
  }, [buildQuery]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const formatTime = (iso) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  const groups = report?.groups || [];
  const dates = report?.dates || [];
  const months = report?.months || [];
  const hasSends = (report?.total_sent || 0) > 0;
  const hasAnyHistory = dates.length > 0 || months.length > 0;

  const handleModeChange = (mode) => {
    setFilterMode(mode);
    if (mode === 'all') {
      setSelectedDate('');
      setSelectedMonth('');
      setDateFrom('');
      setDateTo('');
    }
  };

  const applyRange = () => {
    if (dateFrom && dateTo && dateFrom > dateTo) {
      alert('Start date must be on or before end date.');
      return;
    }
    if (!dateFrom && !dateTo) {
      alert('Select at least a start or end date.');
      return;
    }
    setFilterMode('range');
    fetchReport();
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-2">
            <Mail className="h-6 w-6 text-red-600" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Emails Sent Report</h2>
              <p className="text-sm text-gray-600">
                Subscribers who received CRM data emails, grouped by date sent.
                {report?.filter_label && (
                  <span className="block mt-1 text-red-700 font-medium">Showing: {report.filter_label}</span>
                )}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={fetchReport}
            disabled={loading}
            className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {hasAnyHistory && (
          <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-4">
            <label className="block text-sm font-medium text-gray-700">Filter sends</label>

            <div className="flex flex-wrap gap-2">
              {[
                { id: 'all', label: 'All dates' },
                { id: 'month', label: 'By month' },
                { id: 'range', label: 'Date range' },
                { id: 'day', label: 'Single day' },
              ].map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => handleModeChange(id)}
                  className={`px-3 py-1.5 rounded-lg text-sm border ${
                    filterMode === id
                      ? 'bg-red-600 text-white border-red-600'
                      : 'bg-white border-gray-300 hover:border-red-400'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {filterMode === 'month' && (
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Month</label>
                  <input
                    type="month"
                    value={selectedMonth}
                    onChange={(e) => setSelectedMonth(e.target.value)}
                    className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-red-500"
                  />
                </div>
                {months.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {months.map((m) => (
                      <button
                        key={m.value}
                        type="button"
                        onClick={() => setSelectedMonth(m.value)}
                        className={`px-2 py-1 rounded text-xs border ${
                          selectedMonth === m.value
                            ? 'bg-red-100 border-red-400 text-red-800'
                            : 'bg-white border-gray-300 text-gray-700'
                        }`}
                      >
                        {m.label} ({m.sent_count})
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {filterMode === 'range' && (
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">From</label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-red-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">To</label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-red-500"
                  />
                </div>
                <button
                  type="button"
                  onClick={applyRange}
                  className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700"
                >
                  Apply range
                </button>
              </div>
            )}

            {filterMode === 'day' && (
              <div className="flex flex-wrap gap-2">
                {dates.map((d) => (
                  <button
                    key={d.value}
                    type="button"
                    onClick={() => setSelectedDate(d.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm border ${
                      selectedDate === d.value
                        ? 'bg-red-600 text-white border-red-600'
                        : 'bg-white border-gray-300 hover:border-red-400'
                    }`}
                  >
                    {d.label}
                    <span className={`ml-1.5 text-xs ${selectedDate === d.value ? 'text-red-100' : 'text-gray-500'}`}>
                      ({d.sent_count})
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {report && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-green-800">
                <CheckCircle className="h-5 w-5" />
                <span className="text-sm font-medium">Emails in view</span>
              </div>
              <p className="text-2xl font-bold text-green-900 mt-1">{report.total_sent}</p>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-blue-800">
                <Calendar className="h-5 w-5" />
                <span className="text-sm font-medium">Send days in view</span>
              </div>
              <p className="text-2xl font-bold text-blue-900 mt-1">{groups.length}</p>
            </div>
          </div>
        )}

        {loading && !report ? (
          <p className="text-center py-12 text-gray-500">Loading report…</p>
        ) : !hasSends ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
            <Mail className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-600 font-medium">
              {hasAnyHistory ? 'No emails match this filter' : 'No emails sent yet'}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              {hasAnyHistory
                ? 'Try a different month or date range.'
                : 'Send emails from Dashboard → Email Distribution. Reports appear here after sending.'}
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {groups.map((group) => (
              <div key={group.date} className="border rounded-lg overflow-hidden">
                <h3 className="px-4 py-3 bg-gray-50 border-b text-sm font-semibold text-gray-900 flex items-center justify-between">
                  <span>{group.date_label}</span>
                  <span className="text-gray-500 font-normal">
                    {group.sent_count} subscriber{group.sent_count !== 1 ? 's' : ''}
                  </span>
                </h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Subscriber</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Recipient email</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Users in export</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Sent at</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Sent by</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {group.records.map((row) => (
                        <tr
                          key={`${group.date}-${row.subscriber_name}-${row.sent_at}`}
                          className="hover:bg-gray-50"
                        >
                          <td
                            className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate"
                            title={row.subscriber_name}
                          >
                            {row.subscriber_name}
                          </td>
                          <td className="px-4 py-3 text-gray-700">{row.recipient_email || '—'}</td>
                          <td className="px-4 py-3 text-gray-600">{row.user_count ?? '—'}</td>
                          <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                            {formatTime(row.sent_at)}
                          </td>
                          <td className="px-4 py-3 text-gray-600">{row.sent_by || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default EmailsSentReport;

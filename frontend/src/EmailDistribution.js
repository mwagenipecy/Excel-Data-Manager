import React, { useState, useCallback, useImperativeHandle, forwardRef, useRef } from 'react';
import { Mail, Save, Send, Download, RefreshCw, CheckCircle, XCircle, AlertTriangle, Upload, Plus, Trash2 } from 'lucide-react';
import { API_BASE_URL, authFetch } from './api';

const EmailDistribution = forwardRef(({ hasData, onDataUploaded }, ref) => {
  const [subscribers, setSubscribers] = useState([]);
  const [ccRecipients, setCcRecipients] = useState([]);
  const [emailStatus, setEmailStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResults, setSendResults] = useState(null);
  const [selectedSubscribers, setSelectedSubscribers] = useState(new Set());
  const [emailSubject, setEmailSubject] = useState('CRM User Data & Deactivation Form');
  const [emailMessage, setEmailMessage] = useState('');
  const [newCcEmail, setNewCcEmail] = useState('');
  const [ccSaving, setCcSaving] = useState(false);
  const [uploadingEmails, setUploadingEmails] = useState(false);
  const [downloadingList, setDownloadingList] = useState(false);
  const [emailPage, setEmailPage] = useState(1);
  const [emailPageSize, setEmailPageSize] = useState(5);
  const uploadInputRef = useRef(null);

  const fetchCcRecipients = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/email/cc-recipients`);
      if (response.ok) {
        const result = await response.json();
        setCcRecipients(result.cc_recipients || []);
      }
    } catch (error) {
      console.error('Error fetching CC recipients:', error);
    }
  }, []);

  const fetchEmailStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/email/status`);
      if (response.ok) {
        const result = await response.json();
        setEmailStatus(result);
        setCcRecipients(result.cc_recipients || []);
      }
    } catch (error) {
      console.error('Error fetching email status:', error);
    }
  }, []);

  const fetchSubscribers = useCallback(async () => {
    if (!hasData) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/email/subscribers`);
      if (response.ok) {
        const result = await response.json();
        setSubscribers(result.subscribers || []);
        setCcRecipients(result.cc_recipients || []);
        setSelectedSubscribers(new Set());
        setEmailPage(1);
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to load subscribers');
      }
    } catch (error) {
      console.error('Error fetching subscribers:', error);
      alert('Failed to load subscribers. Is the backend running on port 8000?');
    } finally {
      setLoading(false);
    }
  }, [hasData]);

  React.useEffect(() => {
    fetchEmailStatus();
    fetchCcRecipients();
    fetchSubscribers();
  }, [hasData, onDataUploaded, fetchEmailStatus, fetchCcRecipients, fetchSubscribers]);

  const handleDownloadSubscriberList = async () => {
    if (!hasData) {
      alert('Upload an Excel file first.');
      return;
    }
    setDownloadingList(true);
    try {
      const response = await fetch(`${API_BASE_URL}/email/download-subscriber-list`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const disposition = response.headers.get('Content-Disposition');
        let filename = 'subscriber_email_list.xlsx';
        if (disposition) {
          const match = disposition.match(/filename="?([^"]+)"?/);
          if (match) filename = match[1];
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        const error = await response.json();
        alert(error.detail || 'Download failed');
      }
    } catch (error) {
      alert('Failed to download subscriber list');
    } finally {
      setDownloadingList(false);
    }
  };

  const handleUploadSubscriberEmails = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploadingEmails(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/email/upload-subscriber-emails`, {
        method: 'POST',
        body: formData,
      });
      const result = await response.json();
      if (response.ok) {
        const report = result.report || {};
        let msg = `Merged emails: ${result.added_subscribers || 0} added, ${result.updated_subscribers || 0} updated.`;
        if (result.removed_subscribers) msg += ` ${result.removed_subscribers} removed (no longer in data).`;
        if (report.skipped_empty) msg += ` Skipped ${report.skipped_empty} empty row(s).`;
        if (report.not_found?.length) msg += ` ${report.not_found.length} name(s) not matched.`;
        if (report.invalid_email?.length) msg += ` ${report.invalid_email.length} invalid email(s).`;
        alert(msg);
        await fetchSubscribers();
      } else {
        alert(result.detail || 'Upload failed');
      }
    } catch (error) {
      alert('Failed to upload subscriber emails');
    } finally {
      setUploadingEmails(false);
      event.target.value = '';
    }
  };

  const handleAddCc = async () => {
    const email = newCcEmail.trim();
    if (!email) return;
    setCcSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/email/cc-recipients`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const result = await response.json();
      if (response.ok) {
        setCcRecipients(result.cc_recipients || []);
        setNewCcEmail('');
      } else {
        alert(result.detail || 'Failed to add CC recipient');
      }
    } catch (error) {
      alert('Failed to add CC recipient');
    } finally {
      setCcSaving(false);
    }
  };

  const handleRemoveCc = async (email) => {
    if (!window.confirm(`Remove ${email} from CC list?`)) return;
    setCcSaving(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/email/cc-recipients?email=${encodeURIComponent(email)}`,
        { method: 'DELETE' }
      );
      const result = await response.json();
      if (response.ok) {
        setCcRecipients(result.cc_recipients || []);
      } else {
        alert(result.detail || 'Failed to remove CC recipient');
      }
    } catch (error) {
      alert('Failed to remove CC recipient');
    } finally {
      setCcSaving(false);
    }
  };

  const handleEmailChange = (subscriberName, email) => {
    setSubscribers(prev =>
      prev.map(sub =>
        sub.name === subscriberName ? { ...sub, email, has_email: Boolean(email.trim()) } : sub
      )
    );
  };

  const handleSaveEmails = async () => {
    if (!hasData) {
      alert('Upload an Excel file first.');
      return;
    }
    setSaving(true);
    try {
      const mappings = subscribers.map(sub => ({
        subscriber_name: sub.name,
        email: sub.email || '',
      }));
      const response = await fetch(`${API_BASE_URL}/email/subscriber-emails`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mappings }),
      });
      if (response.ok) {
        const result = await response.json();
        alert(`Saved ${result.saved_count} subscriber email(s)`);
        await fetchSubscribers();
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to save emails');
      }
    } catch (error) {
      alert('Failed to save subscriber emails');
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadZip = async (subscriberName) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/email/download-subscriber-zip/${encodeURIComponent(subscriberName)}`
      );
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${subscriberName.replace(/[^a-z0-9]/gi, '_')}_data.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        const error = await response.json();
        alert(error.detail || 'Download failed');
      }
    } catch (error) {
      alert('Download failed');
    }
  };

  const toggleSubscriber = (name) => {
    setSelectedSubscribers(prev => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  const totalEmailPages = Math.max(1, Math.ceil(subscribers.length / emailPageSize));
  const emailPageStart = (emailPage - 1) * emailPageSize;
  const paginatedSubscribers = subscribers.slice(emailPageStart, emailPageStart + emailPageSize);
  const paginatedWithEmail = paginatedSubscribers.filter(s => s.email?.trim());
  const allPageSelected =
    paginatedWithEmail.length > 0 &&
    paginatedWithEmail.every(s => selectedSubscribers.has(s.name));

  React.useEffect(() => {
    if (emailPage > totalEmailPages) {
      setEmailPage(totalEmailPages);
    }
  }, [emailPage, totalEmailPages]);

  const toggleSelectAllOnPage = () => {
    setSelectedSubscribers(prev => {
      const next = new Set(prev);
      if (allPageSelected) {
        paginatedWithEmail.forEach(s => next.delete(s.name));
      } else {
        paginatedWithEmail.forEach(s => next.add(s.name));
      }
      return next;
    });
  };

  const handleSendEmails = async (sendAll = false) => {
    if (!hasData) {
      alert('Upload an Excel file first.');
      return;
    }

    const targets = sendAll
      ? subscribers.filter(s => s.email?.trim()).map(s => s.name)
      : Array.from(selectedSubscribers).filter(name => {
          const sub = subscribers.find(s => s.name === name);
          return sub?.email?.trim();
        });

    if (targets.length === 0) {
      alert('Add and save recipient emails for at least one subscriber before sending.');
      return;
    }

    if (!window.confirm(`Send emails to ${targets.length} subscriber(s)? All emails will CC the configured team members.`)) {
      return;
    }

    setSending(true);
    setSendResults(null);
    try {
      const response = await authFetch('/email/send', {
        method: 'POST',
        body: JSON.stringify({
          subscriber_names: targets,
          subject: emailSubject || undefined,
          message: emailMessage
            ? `<p>${emailMessage.replace(/\n/g, '<br>')}</p>`
            : undefined,
        }),
      });
      const result = await response.json();
      if (response.ok) {
        setSendResults(result);
        await fetchSubscribers();
        document.getElementById('email-send-results')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        alert(result.detail || 'Failed to send emails');
      }
    } catch (error) {
      alert('Failed to send emails. Check backend logs.');
    } finally {
      setSending(false);
    }
  };

  useImperativeHandle(ref, () => ({
    sendAll: () => handleSendEmails(true),
    sendSelected: () => handleSendEmails(false),
    saveEmails: handleSaveEmails,
    refresh: fetchSubscribers,
    getSelectedCount: () => selectedSubscribers.size,
    getWithEmailCount: () => subscribers.filter(s => s.email?.trim()).length,
  }));

  const subscribersWithEmail = subscribers.filter(s => s.email?.trim()).length;

  return (
    <div id="email-distribution" className="bg-white rounded-lg shadow-md p-6 mb-8 border-2 border-red-100">
      <h2 className="text-lg font-semibold text-gray-900 mb-1 flex items-center">
        <Mail className="mr-2 h-5 w-5 text-red-600" />
        Email Distribution
      </h2>
      <p className="text-sm text-gray-600 mb-4">
        Assign an email per subscriber, save, then send. Each email includes the subscriber ZIP (Excel export)
        and the <strong>User De-activation Request Form</strong> (PDF). View send history under{' '}
        <strong>Emails Sent</strong> in the navigation.
      </p>


      {emailStatus && (
        <div
          className={`rounded-lg p-4 mb-4 border ${
            emailStatus.configured && emailStatus.send_email_enabled
              ? 'bg-green-50 border-green-200'
              : 'bg-yellow-50 border-yellow-200'
          }`}
        >
          <div className="flex items-start">
            {emailStatus.configured && emailStatus.send_email_enabled ? (
              <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 mr-2 flex-shrink-0" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5 mr-2 flex-shrink-0" />
            )}
            <div className="text-sm">
              <p className="font-medium text-gray-800">
                Email: {emailStatus.send_email_enabled ? 'Enabled' : 'Disabled'} | Mailer: {emailStatus.mailer}
              </p>
              <p className="text-gray-600">From: {emailStatus.from_name} &lt;{emailStatus.from_email}&gt;</p>
            </div>
          </div>
        </div>
      )}

      <div className="mb-6 p-4 bg-slate-50 border border-slate-200 rounded-lg">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">CC Recipients (copied on every email)</h3>
        <div className="flex flex-wrap gap-2 mb-3">
          {ccRecipients.length === 0 ? (
            <span className="text-sm text-gray-500">No CC recipients configured.</span>
          ) : (
            ccRecipients.map((email) => (
              <span
                key={email}
                className="inline-flex items-center gap-1 px-3 py-1 bg-white border border-gray-300 rounded-full text-sm text-gray-800"
              >
                {email}
                <button
                  type="button"
                  onClick={() => handleRemoveCc(email)}
                  disabled={ccSaving}
                  className="text-red-500 hover:text-red-700 disabled:opacity-50"
                  title="Remove from CC"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </span>
            ))
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            type="email"
            value={newCcEmail}
            onChange={(e) => setNewCcEmail(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddCc()}
            placeholder="Add CC email..."
            className="flex-1 min-w-[200px] border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
          />
          <button
            type="button"
            onClick={handleAddCc}
            disabled={ccSaving || !newCcEmail.trim()}
            className="flex items-center px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-800 disabled:opacity-50"
          >
            <Plus className="mr-1 h-4 w-4" />
            Add CC
          </button>
        </div>
      </div>

      {!hasData && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-sm text-amber-900">
          Upload an Excel file above to load subscribers and enable sending.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email Subject</label>
          <input
            type="text"
            value={emailSubject}
            onChange={(e) => setEmailSubject(e.target.value)}
            disabled={!hasData}
            className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:bg-gray-100"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Custom Message (optional)</label>
          <textarea
            value={emailMessage}
            onChange={(e) => setEmailMessage(e.target.value)}
            rows={2}
            disabled={!hasData}
            placeholder="Leave empty for default message..."
            className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:bg-gray-100"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
        <button
          type="button"
          onClick={handleDownloadSubscriberList}
          disabled={downloadingList || !hasData}
          className="flex items-center px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Download className="mr-2 h-4 w-4" />
          {downloadingList ? 'Downloading...' : 'Download Email List'}
        </button>
        <label className={`flex items-center px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 ${!hasData || uploadingEmails ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
          <Upload className="mr-2 h-4 w-4" />
          {uploadingEmails ? 'Uploading...' : 'Upload Email List'}
          <input
            ref={uploadInputRef}
            type="file"
            className="hidden"
            accept=".xlsx,.xls,.csv"
            onChange={handleUploadSubscriberEmails}
            disabled={uploadingEmails || !hasData}
          />
        </label>
        <button
          type="button"
          onClick={fetchSubscribers}
          disabled={loading || !hasData}
          className="flex items-center px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh List
        </button>
        <button
          type="button"
          onClick={handleSaveEmails}
          disabled={saving || !hasData || subscribers.length === 0}
          className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Save className="mr-2 h-4 w-4" />
          {saving ? 'Saving...' : 'Save Emails'}
        </button>
        <button
          type="button"
          onClick={() => handleSendEmails(true)}
          disabled={sending || !hasData || subscribersWithEmail === 0}
          className="flex items-center px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          title={subscribersWithEmail === 0 ? 'Add recipient emails first' : 'Send to all subscribers with emails'}
        >
          <Send className="mr-2 h-4 w-4" />
          {sending ? 'Sending...' : `Send All Subscribers (${subscribersWithEmail})`}
        </button>
        <button
          type="button"
          onClick={() => handleSendEmails(false)}
          disabled={sending || !hasData || selectedSubscribers.size === 0}
          className="flex items-center px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
          title={selectedSubscribers.size === 0 ? 'Select subscribers with emails' : 'Send to selected subscribers only'}
        >
          <Send className="mr-2 h-4 w-4" />
          {sending ? 'Sending...' : `Send Selected (${selectedSubscribers.size})`}
        </button>
      </div>

      <p className="text-xs text-gray-600 mb-3">
        <strong>Main Excel upload</strong> replaces CRM data; subscriber emails are kept and synced (removed if subscriber no longer exists).
        <strong> Download Email List</strong> / <strong>Upload Email List</strong> merges emails (adds new, updates existing).
        Columns: Subscriber Name, Email. Every send includes the deactivation form PDF.
      </p>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="h-6 w-6 animate-spin text-red-500" />
          <span className="ml-2 text-gray-600">Loading subscribers...</span>
        </div>
      ) : hasData ? (
        <div className="border rounded-lg overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-gray-50 border-b border-gray-200">
            <p className="text-sm text-gray-700">
              {subscribers.length} subscriber{subscribers.length !== 1 ? 's' : ''}
              {subscribersWithEmail > 0 && (
                <span className="text-gray-500"> · {subscribersWithEmail} with email</span>
              )}
            </p>
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">Rows per page</label>
              <select
                value={emailPageSize}
                onChange={(e) => {
                  setEmailPageSize(Number(e.target.value));
                  setEmailPage(1);
                }}
                className="border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value={10}>10</option>
                <option value={5}>5</option>

                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={toggleSelectAllOnPage}
                    disabled={paginatedWithEmail.length === 0}
                    title="Select all on this page (with email)"
                    className="rounded border-gray-300"
                  />
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Subscriber</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Records</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Recipient Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last sent</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ZIP</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {paginatedSubscribers.map((sub) => (
                <tr key={sub.name} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedSubscribers.has(sub.name)}
                      onChange={() => toggleSubscriber(sub.name)}
                      disabled={!sub.email?.trim()}
                      className="rounded border-gray-300"
                    />
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 max-w-xs truncate" title={sub.name}>
                    {sub.name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{sub.record_count}</td>
                  <td className="px-4 py-3">
                    <input
                      type="email"
                      value={sub.email || ''}
                      onChange={(e) => handleEmailChange(sub.name, e.target.value)}
                      placeholder="subscriber@example.com"
                      className="w-full min-w-[200px] border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {sub.last_sent_at
                      ? new Date(sub.last_sent_at).toLocaleString()
                      : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleDownloadZip(sub.name)}
                      className="text-blue-600 hover:text-blue-800"
                      title="Download ZIP preview"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {subscribers.length === 0 && (
            <p className="text-center py-6 text-gray-500 text-sm">
              No active subscribers found. Click Refresh List.
            </p>
          )}
          </div>

          {subscribers.length > 0 && (
            <div className="bg-white px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-gray-200">
              <p className="text-sm text-gray-700">
                Showing <span className="font-medium">{emailPageStart + 1}</span> to{' '}
                <span className="font-medium">{Math.min(emailPageStart + emailPageSize, subscribers.length)}</span> of{' '}
                <span className="font-medium">{subscribers.length}</span>
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setEmailPage(p => Math.max(1, p - 1))}
                  disabled={emailPage <= 1}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-600 px-2">
                  Page {emailPage} of {totalEmailPages}
                </span>
                <button
                  type="button"
                  onClick={() => setEmailPage(p => Math.min(totalEmailPages, p + 1))}
                  disabled={emailPage >= totalEmailPages}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {sendResults && (
        <div id="email-send-results" className="mt-6 border rounded-lg p-4 bg-gray-50">
          <h3 className="font-semibold text-gray-900 mb-2">Send Results</h3>
          <p className="text-sm text-gray-700 mb-3">
            Sent: {sendResults.sent} | Failed: {sendResults.failed} | Skipped: {sendResults.skipped}
          </p>
          <div className="max-h-48 overflow-y-auto space-y-1">
            {sendResults.results?.map((r, i) => (
              <div key={i} className="flex items-center text-sm">
                {r.status === 'sent' ? (
                  <CheckCircle className="h-4 w-4 text-green-500 mr-2 flex-shrink-0" />
                ) : r.status === 'failed' ? (
                  <XCircle className="h-4 w-4 text-red-500 mr-2 flex-shrink-0" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-yellow-500 mr-2 flex-shrink-0" />
                )}
                <span>
                  <strong>{r.subscriber_name}</strong>: {r.status}
                  {r.to && ` → ${r.to}`}
                  {r.error && ` (${r.error})`}
                  {r.reason && ` (${r.reason})`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

EmailDistribution.displayName = 'EmailDistribution';

export default EmailDistribution;

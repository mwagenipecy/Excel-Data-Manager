import React, { useState, useEffect, useCallback } from 'react';
import { Upload, Download, Filter, RefreshCw, Users, Building, Archive, Info, LogOut, ScrollText, LayoutDashboard, UserCheck, UserX, Mail } from 'lucide-react';
import EmailDistribution from './EmailDistribution';
import LoginPanel from './LoginPanel';
import ActivityLog from './ActivityLog';
import EmailsSentReport from './EmailsSentReport';
import { API_BASE_URL, authFetch, getAuthToken, setAuthToken } from './api';

const ExcelManager = () => {
  const [authToken, setAuthTokenState] = useState(() => getAuthToken());
  const [userEmail, setUserEmail] = useState('');
  const [authChecking, setAuthChecking] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [pendingRequests, setPendingRequests] = useState([]);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [downloading, setDownloading] = useState('');
  const [stats, setStats] = useState(null);
  const [filterOptions, setFilterOptions] = useState({});
  const [pagination, setPagination] = useState({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [selectedSubscriber, setSelectedSubscriber] = useState('');
  const [dataVersion, setDataVersion] = useState(0);
  const hasDataLoaded = Boolean(stats?.total_records) || (pagination?.total_records > 0);
  
  // Filter states
  const [filters, setFilters] = useState({
    subscriber_name: '',
    name: '',
    username: '',
    email: '',
    is_open: '',
    branch_name: '',
    position: '',
    needs_password_change: ''
  });

  const fetchData = useCallback(async (page = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        ...Object.fromEntries(Object.entries(filters).filter(([_, v]) => v))
      });
      
      const response = await fetch(`${API_BASE_URL}/data?${params}`);
      if (response.ok) {
        const result = await response.json();
        setData(result.data);
        setPagination(result);
        setCurrentPage(page);
      } else {
        console.error('Failed to fetch data');
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [filters, pageSize]);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/stats`);
      if (response.ok) {
        const result = await response.json();
        setStats(result);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchFilterOptions = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/filter-options`);
      if (response.ok) {
        const result = await response.json();
        setFilterOptions(result);
      }
    } catch (error) {
      console.error('Error fetching filter options:', error);
    }
  };

  const handleAuthenticated = (token, email) => {
    setAuthToken(token);
    setAuthTokenState(token);
    setUserEmail(email);
    setActiveTab('dashboard');
  };

  const handleLogout = async () => {
    try {
      if (getAuthToken()) {
        await authFetch('/auth/logout', { method: 'POST' });
      }
    } catch {
      /* ignore */
    }
    setAuthToken(null);
    setAuthTokenState(null);
    setUserEmail('');
    setPendingRequests([]);
  };

  const fetchSession = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setAuthChecking(false);
      return;
    }
    try {
      const res = await authFetch('/auth/me');
      if (res.ok) {
        const data = await res.json();
        setUserEmail(data.email);
        setAuthTokenState(token);
        setPendingRequests(data.pending_requests || []);
      } else {
        setAuthToken(null);
        setAuthTokenState(null);
      }
    } catch {
      setAuthToken(null);
      setAuthTokenState(null);
    } finally {
      setAuthChecking(false);
    }
  }, []);

  useEffect(() => {
    fetchSession();
    const onLogout = () => {
      setAuthTokenState(null);
      setUserEmail('');
    };
    window.addEventListener('auth:logout', onLogout);
    return () => window.removeEventListener('auth:logout', onLogout);
  }, [fetchSession]);

  useEffect(() => {
    if (!authToken) return undefined;
    fetchData(1);
    fetchStats();
    fetchFilterOptions();
    const interval = setInterval(async () => {
      try {
        const res = await authFetch('/auth/me');
        if (res.ok) {
          const data = await res.json();
          setPendingRequests(data.pending_requests || []);
        }
      } catch {
        /* ignore */
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [authToken]);

  const handleApproveLogin = async (requestId) => {
    try {
      const res = await authFetch('/auth/approve-login', {
        method: 'POST',
        body: JSON.stringify({ request_id: requestId }),
      });
      if (res.ok) {
        alert('Login approved. You have been signed out.');
        await handleLogout();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to approve');
      }
    } catch {
      alert('Failed to approve login');
    }
  };

  const handleDenyLogin = async (requestId) => {
    try {
      const res = await authFetch('/auth/deny-login', {
        method: 'POST',
        body: JSON.stringify({ request_id: requestId }),
      });
      if (res.ok) {
        setPendingRequests((prev) => prev.filter((r) => r.id !== requestId));
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to deny');
      }
    } catch {
      alert('Failed to deny login');
    }
  };

  useEffect(() => {
    fetchData(1);
  }, [filters]);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await authFetch('/upload-excel', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        await fetchData(1);
        await fetchStats();
        await fetchFilterOptions();
        setDataVersion(v => v + 1);
        alert('File uploaded successfully!');
      } else {
        const error = await response.json();
        alert(`Upload failed: ${error.detail}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleDownload = async (type = 'filtered') => {
    setDownloading(type);
    try {
      let url = '';
      let params = '';
      let isZipFile = false;
      
      switch (type) {
        case 'all':
          // This downloads a ZIP file with separate Excel files for each subscriber
          url = `${API_BASE_URL}/download-all-by-subscribers-zip`;
          isZipFile = true;
          break;
        case 'subscriber':
          if (!selectedSubscriber) {
            alert('Please select a subscriber first');
            return;
          }
          url = `${API_BASE_URL}/download-by-subscriber?subscriber=${encodeURIComponent(selectedSubscriber)}`;
          break;
        case 'all-subscribers':
          // Same as 'all' - keeping for backward compatibility
          url = `${API_BASE_URL}/download-all-by-subscribers-zip`;
          isZipFile = true;
          break;
        default:
          params = new URLSearchParams(
            Object.fromEntries(Object.entries(filters).filter(([_, v]) => v))
          );
          url = `${API_BASE_URL}/download-excel?${params}`;
      }
      
      console.log(`Downloading from: ${url}, isZipFile: ${isZipFile}`);
      
      const response = await fetch(url);
      if (response.ok) {
        const blob = await response.blob();
        console.log(`Response blob type: ${blob.type}, size: ${blob.size}`);
        
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        
        // Get filename from response headers or create default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = '';
        
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          if (filenameMatch) {
            filename = filenameMatch[1].replace(/['"]/g, '');
            console.log(`Filename from header: ${filename}`);
          }
        }
        
        // If no filename from headers, create default based on type
        if (!filename) {
          const timestamp = new Date().toISOString().split('T')[0];
          if (isZipFile) {
            filename = `all_subscribers_data_${timestamp}.zip`;
          } else {
            filename = `data_${timestamp}.xlsx`;
          }
          console.log(`Default filename: ${filename}`);
        }
        
        // Ensure correct file extension
        if (isZipFile && !filename.endsWith('.zip')) {
          filename = filename.replace(/\.[^.]+$/, '.zip');
          console.log(`Corrected filename for ZIP: ${filename}`);
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(a);
        
        console.log(`Download initiated: ${filename}`);
      } else {
        const error = await response.json();
        alert(`Download failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Download error:', error);
      alert('Download failed. Please try again.');
    } finally {
      setDownloading('');
    }
  };


  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({
      subscriber_name: '',
      name: '',
      username: '',
      email: '',
      is_open: '',
      branch_name: '',
      position: '',
      needs_password_change: ''
    });
  };

  const StatCard = ({ title, value, icon: Icon, color = 'blue' }) => (
    <div className={`bg-white rounded-lg shadow-md p-6 border-l-4 border-${color}-500`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className={`text-2xl font-bold text-${color}-600`}>{value}</p>
        </div>
        <Icon className={`h-8 w-8 text-${color}-500`} />
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-gradient-to-r from-red-600 to-black text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <img src="/creditinfo_logo.png" alt="Logo" className="h-10 rounded-lg mr-2" />
              <h1 className="text-xl font-bold">Excel Data Manager</h1>
            </div>
            <div className="flex items-center space-x-4">
              {authToken && (
                <>
                  <nav className="flex rounded-lg overflow-hidden border border-white/30 text-sm">
                    <button
                      type="button"
                      onClick={() => setActiveTab('dashboard')}
                      className={`flex items-center gap-1 px-3 py-1.5 ${activeTab === 'dashboard' ? 'bg-white text-red-700' : 'hover:bg-white/10'}`}
                    >
                      <LayoutDashboard className="h-4 w-4" />
                      Dashboard
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveTab('emails-sent')}
                      className={`flex items-center gap-1 px-3 py-1.5 ${activeTab === 'emails-sent' ? 'bg-white text-red-700' : 'hover:bg-white/10'}`}
                    >
                      <Mail className="h-4 w-4" />
                      Emails Sent
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveTab('activity-log')}
                      className={`flex items-center gap-1 px-3 py-1.5 ${activeTab === 'activity-log' ? 'bg-white text-red-700' : 'hover:bg-white/10'}`}
                    >
                      <ScrollText className="h-4 w-4" />
                      Activity Log
                    </button>
                  </nav>
                  <span className="text-sm text-white/90 hidden sm:inline">{userEmail}</span>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex items-center gap-1 text-sm bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg"
                  >
                    <LogOut className="h-4 w-4" />
                    Logout
                  </button>
                </>
              )}
              <div className="flex items-center text-sm">
                <span className="mr-2">Powered by</span>
                <span className="bg-gray-500 px-2 py-1 rounded text-xs">CreditInfo Tanzania</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {authChecking ? (
        <div className="max-w-7xl mx-auto px-4 py-16 text-center text-gray-500">Loading…</div>
      ) : !authToken ? (
        <LoginPanel onAuthenticated={handleAuthenticated} />
      ) : (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {pendingRequests.length > 0 && (
          <div className="mb-6 bg-amber-50 border border-amber-300 rounded-lg p-4">
            <p className="font-medium text-amber-900 mb-3">
              Another user wants to sign in. Approve to let them in (you will be signed out).
            </p>
            {pendingRequests.map((req) => (
              <div key={req.id} className="flex flex-wrap items-center gap-3 justify-between bg-white rounded-lg p-3 border border-amber-200 mb-2 last:mb-0">
                <span className="text-sm text-gray-800">
                  <strong>{req.email}</strong> requested access at{' '}
                  {new Date(req.requested_at).toLocaleString()}
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleApproveLogin(req.id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700"
                  >
                    <UserCheck className="h-4 w-4" />
                    Allow login
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDenyLogin(req.id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-600 text-white text-sm rounded-lg hover:bg-gray-700"
                  >
                    <UserX className="h-4 w-4" />
                    Deny
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'activity-log' ? (
          <ActivityLog />
        ) : activeTab === 'emails-sent' ? (
          <EmailsSentReport />
        ) : (
        <>
        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Excel File</h2>
          <div className="flex items-center space-x-4">
            <label className="flex items-center px-4 py-2 bg-red-600 text-white rounded-lg cursor-pointer hover:bg-red-700 transition-colors">
              <Upload className="mr-2 h-4 w-4" />
              {uploading ? 'Uploading...' : 'Choose File'}
              <input
                type="file"
                className="hidden"
                accept=".xlsx,.xls,.csv"
                onChange={handleFileUpload}
                disabled={uploading}
              />
            </label>
            <p className="text-sm text-gray-600">
              Supports Excel (.xlsx, .xls) and CSV files. This will replace the current data.
            </p>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <StatCard title="Total Records" value={stats.total_records} icon={Users} color="blue" />
            <StatCard title="Active Users" value={stats.active_users} icon={Users} color="green" />
            <StatCard title="Unique Subscribers" value={stats.unique_subscribers} icon={Building} color="purple" />
            <StatCard title="Download All Records" value={stats.download_all_records} icon={Download} color="orange" />
          </div>
        )}

        <EmailDistribution
          hasData={hasDataLoaded}
          onDataUploaded={dataVersion}
        />

        {/* Download Options */}
        <div className="bg-white rounded-lg shadow-md p-4 sm:p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Download className="mr-2 h-5 w-5 flex-shrink-0" />
            Download Options
          </h2>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4 mb-4">
            <div className="flex items-start gap-2 sm:gap-3">
              <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-blue-800 min-w-0">
                <p className="font-medium mb-1">Download All Information</p>
                <ul className="space-y-1 text-xs sm:text-sm">
                  <li>• Separate Excel per subscriber ({stats?.download_all_subscribers || 0} subscribers)</li>
                  <li>• Active users only (Is Open = Yes)</li>
                  <li>• {stats?.download_all_records || 0} records</li>
                  <li>• Excludes: Is Open, Position, Expiry Date, Needs Password Change</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:gap-4">
            <button
              type="button"
              onClick={() => handleDownload('all')}
              disabled={downloading === 'all'}
              className="w-full flex items-center justify-center px-4 py-3 sm:py-2.5 bg-blue-600 text-white text-sm sm:text-base rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Archive className="mr-2 h-4 w-4 flex-shrink-0" />
              <span className="text-center">{downloading === 'all' ? 'Creating ZIP...' : 'Download All by Subscribers'}</span>
            </button>

            <button
              type="button"
              onClick={() => handleDownload('filtered')}
              disabled={downloading === 'filtered'}
              className="w-full flex items-center justify-center px-4 py-3 sm:py-2.5 bg-green-600 text-white text-sm sm:text-base rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Download className="mr-2 h-4 w-4 flex-shrink-0" />
              <span className="text-center">{downloading === 'filtered' ? 'Downloading...' : 'Download Filtered Data'}</span>
            </button>

            <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 w-full">
              <select
                value={selectedSubscriber}
                onChange={(e) => setSelectedSubscriber(e.target.value)}
                className="w-full min-w-0 flex-1 border border-gray-300 rounded-lg px-3 py-3 sm:py-2 text-sm sm:text-base focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="">Select Subscriber</option>
                {filterOptions.subscriber_names?.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => handleDownload('subscriber')}
                disabled={downloading === 'subscriber' || !selectedSubscriber}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-3 sm:py-2 bg-purple-600 text-white text-sm sm:text-base rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
              >
                <Download className="h-4 w-4" />
                <span>Download</span>
              </button>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <Filter className="mr-2 h-5 w-5" />
              Filters
            </h2>
            <button
              onClick={clearFilters}
              className="text-sm text-red-600 hover:text-red-800 underline"
            >
              Clear All Filters
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subscriber Name</label>
              <select
                value={filters.subscriber_name}
                onChange={(e) => handleFilterChange('subscriber_name', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="">All Subscribers</option>
                {filterOptions.subscriber_names?.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Branch Name</label>
              <select
                value={filters.branch_name}
                onChange={(e) => handleFilterChange('branch_name', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="">All Branches</option>
                {filterOptions.branch_names?.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Position</label>
              <select
                value={filters.position}
                onChange={(e) => handleFilterChange('position', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="">All Positions</option>
                {filterOptions.positions?.map(position => (
                  <option key={position} value={position}>{position}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Account Status</label>
              <select
                value={filters.is_open}
                onChange={(e) => handleFilterChange('is_open', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="">All Status</option>
                {filterOptions.is_open_options?.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={filters.name}
                onChange={(e) => handleFilterChange('name', e.target.value)}
                placeholder="Search by name..."
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <input
                type="text"
                value={filters.username}
                onChange={(e) => handleFilterChange('username', e.target.value)}
                placeholder="Search by username..."
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="text"
                value={filters.email}
                onChange={(e) => handleFilterChange('email', e.target.value)}
                placeholder="Search by email..."
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password Change</label>
              <select
                value={filters.needs_password_change}
                onChange={(e) => handleFilterChange('needs_password_change', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="">All</option>
                {filterOptions.password_change_options?.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Table Actions */}
        <div className="bg-white rounded-lg shadow-md p-4 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => fetchData(currentPage)}
                disabled={loading}
                className="flex items-center px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value={25}>25 per page</option>
                <option value={50}>50 per page</option>
                <option value={100}>100 per page</option>
                <option value={200}>200 per page</option>
              </select>
            </div>
          </div>
        </div>

        {/* Data Table */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-red-500" />
              <span className="ml-2 text-gray-600">Loading data...</span>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User Id</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User Name</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Is Open</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscriber Name</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Branch Name</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Position</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Expiry Date</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Phone</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Needs Password Change</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {data.map((row, index) => (
                      <tr key={row['User ID'] || index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {row['User ID']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row['Username']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row['Name']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row['Email']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                            row['Is Open'] === 'Yes' 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {row['Is Open']}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                          {row['Subscriber Name']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row['Branch Name']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row['Position']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row['Expiry Date']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row['Phone']}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                            row['Needs To Change Password'] === 'Yes' 
                              ? 'bg-yellow-100 text-yellow-800' 
                              : 'bg-gray-100 text-gray-800'
                          }`}>
                            {row['Needs To Change Password']}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {pagination.total_pages > 1 && (
                <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
                  <div className="flex-1 flex justify-between sm:hidden">
                    <button
                      onClick={() => fetchData(currentPage - 1)}
                      disabled={!pagination.has_previous}
                      className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => fetchData(currentPage + 1)}
                      disabled={!pagination.has_next}
                      className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </div>
                  <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm text-gray-700">
                        Showing{' '}
                        <span className="font-medium">
                          {((currentPage - 1) * pageSize) + 1}
                        </span>{' '}
                        to{' '}
                        <span className="font-medium">
                          {Math.min(currentPage * pageSize, pagination.total_records)}
                        </span>{' '}
                        of{' '}
                        <span className="font-medium">{pagination.total_records}</span>{' '}
                        results
                      </p>
                    </div>
                    <div>
                      <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                        <button
                          onClick={() => fetchData(currentPage - 1)}
                          disabled={!pagination.has_previous}
                          className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Previous
                        </button>
                        
                        {/* Page Numbers */}
                        {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                          let pageNum;
                          if (pagination.total_pages <= 5) {
                            pageNum = i + 1;
                          } else if (currentPage <= 3) {
                            pageNum = i + 1;
                          } else if (currentPage >= pagination.total_pages - 2) {
                            pageNum = pagination.total_pages - 4 + i;
                          } else {
                            pageNum = currentPage - 2 + i;
                          }
                          
                          return (
                            <button
                              key={pageNum}
                              onClick={() => fetchData(pageNum)}
                              className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                                pageNum === currentPage
                                  ? 'z-10 bg-red-50 border-red-500 text-red-600'
                                  : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                              }`}
                            >
                              {pageNum}
                            </button>
                          );
                        })}
                        
                        <button
                          onClick={() => fetchData(currentPage + 1)}
                          disabled={!pagination.has_next}
                          className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Next
                        </button>
                      </nav>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        </>
        )}

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Excel Data Manager - Built with React & FastAPI Python</p>
          {stats?.filename && (
            <p className="mt-1">Current file: <span className="font-medium">{stats.filename}</span></p>
          )}
          {stats && (
            <p className="mt-1 text-xs">
              Download All Stats: {stats.download_all_records} records from {stats.download_all_subscribers} subscribers (Active users only)
            </p>
          )}
        </div>
      </div>
      )}
    </div>
  );
};

export default ExcelManager;
import React, { useState, useEffect, useRef } from 'react';
import { Mail, KeyRound, LogIn, Clock } from 'lucide-react';
import { API_BASE_URL } from './api';

const LoginPanel = ({ onAuthenticated }) => {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [step, setStep] = useState('email');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [devCode, setDevCode] = useState('');
  const [activeUser, setActiveUser] = useState('');
  const pollRef = useRef(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startPolling = (requestId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/auth/login-request-status?request_id=${encodeURIComponent(requestId)}`
        );
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === 'approved' && data.token) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          onAuthenticated(data.token, data.email);
        } else if (data.status === 'denied') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setStep('otp');
          setError('Your login request was denied by the current user.');
        }
      } catch {
        /* ignore poll errors */
      }
    }, 3000);
  };

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setDevCode('');
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/request-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send OTP');
      setStep('otp');
      setInfo(data.message);
      if (data.dev_code) setDevCode(data.dev_code);
    } catch (err) {
      setError(err.message || 'Failed to send OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Invalid OTP');

      if (data.status === 'pending_approval') {
        setActiveUser(data.active_user);
        setStep('waiting');
        setInfo(data.message);
        startPolling(data.request_id);
        return;
      }

      onAuthenticated(data.token, data.email);
    } catch (err) {
      setError(err.message || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow-lg p-8 w-full max-w-md border border-gray-200">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-red-100 mb-3">
            <LogIn className="h-7 w-7 text-red-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Sign in to continue</h2>
          <p className="text-sm text-gray-500 mt-1">
            Enter your email. We will send a one-time code. Only one user can be logged in at a time.
          </p>
        </div>

        {step === 'email' && (
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500"
                  placeholder="you@company.com"
                />
              </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 disabled:opacity-50"
            >
              {loading ? 'Sending…' : 'Send login code'}
            </button>
          </form>
        )}

        {step === 'otp' && (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <p className="text-sm text-gray-600">Code sent to <strong>{email}</strong></p>
            {devCode && (
              <p className="text-xs bg-amber-50 border border-amber-200 text-amber-800 p-2 rounded">
                Dev mode — your code: <strong>{devCode}</strong>
              </p>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">6-digit code</label>
              <div className="relative">
                <KeyRound className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg tracking-widest text-lg focus:ring-2 focus:ring-red-500"
                  placeholder="000000"
                />
              </div>
            </div>
            {info && <p className="text-sm text-green-600">{info}</p>}
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading || code.length !== 6}
              className="w-full py-2.5 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 disabled:opacity-50"
            >
              {loading ? 'Verifying…' : 'Verify & sign in'}
            </button>
            <button
              type="button"
              onClick={() => { setStep('email'); setCode(''); setError(''); }}
              className="w-full text-sm text-gray-500 hover:text-gray-700"
            >
              Use a different email
            </button>
          </form>
        )}

        {step === 'waiting' && (
          <div className="text-center space-y-4">
            <Clock className="h-12 w-12 text-amber-500 mx-auto animate-pulse" />
            <p className="text-gray-700">{info}</p>
            <p className="text-sm text-gray-500">
              <strong>{activeUser}</strong> must approve your login request.
            </p>
            <p className="text-xs text-gray-400">Checking automatically…</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginPanel;

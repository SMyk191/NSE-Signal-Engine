import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import api from '../services/api';

function UpstoxCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('loading'); // loading | success | error
  const [message, setMessage] = useState('Connecting to Upstox...');

  useEffect(() => {
    const code = searchParams.get('code');
    if (!code) {
      setStatus('error');
      setMessage('No authorization code received from Upstox.');
      return;
    }

    api
      .get(`/auth/upstox/callback`, { params: { code } })
      .then(() => {
        setStatus('success');
        setMessage('Upstox connected successfully!');
        setTimeout(() => navigate('/admin'), 2000);
      })
      .catch((err) => {
        setStatus('error');
        setMessage(
          err.response?.data?.detail ||
            'Failed to connect Upstox. Please try again.'
        );
      });
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen bg-[#0c1220] flex items-center justify-center">
      <div className="bg-[#111827] border border-[#1f2937] rounded-xl p-8 max-w-sm w-full mx-4 shadow-2xl text-center">
        {status === 'loading' && (
          <>
            <Loader2 className="w-10 h-10 text-[#3b82f6] animate-spin mx-auto mb-4" />
            <p className="text-sm text-[#94a3b8]">{message}</p>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircle2 className="w-10 h-10 text-[#22c55e] mx-auto mb-4" />
            <p className="text-sm font-medium text-[#22c55e] mb-2">{message}</p>
            <p className="text-xs text-[#64748b]">Redirecting to dashboard...</p>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle className="w-10 h-10 text-[#ef4444] mx-auto mb-4" />
            <p className="text-sm font-medium text-[#fca5a5] mb-3">{message}</p>
            <button
              onClick={() => navigate('/admin')}
              className="px-4 py-2 rounded-lg text-sm font-medium text-[#94a3b8] bg-[#1f2937] hover:bg-[#374151] border border-[#374151] transition-colors"
            >
              Go to Admin
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default UpstoxCallback;

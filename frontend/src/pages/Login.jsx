import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import useAuthStore from '../stores/authStore';

function Login() {
  const [activeTab, setActiveTab] = useState('signin');
  const navigate = useNavigate();
  const { login, signup } = useAuthStore();

  // Sign In state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [showLoginPass, setShowLoginPass] = useState(false);

  // Sign Up state
  const [signupName, setSignupName] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [signupConfirm, setSignupConfirm] = useState('');
  const [signupError, setSignupError] = useState('');
  const [signupLoading, setSignupLoading] = useState(false);
  const [showSignupPass, setShowSignupPass] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');

    if (!loginEmail || !loginPassword) {
      setLoginError('Please fill in all fields');
      return;
    }

    setLoginLoading(true);
    try {
      await login(loginEmail, loginPassword);
      navigate('/');
    } catch (err) {
      setLoginError(err.message || 'Invalid email or password');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    setSignupError('');

    if (!signupName || !signupEmail || !signupPassword || !signupConfirm) {
      setSignupError('Please fill in all fields');
      return;
    }

    if (signupPassword.length < 6) {
      setSignupError('Password must be at least 6 characters');
      return;
    }

    if (signupPassword !== signupConfirm) {
      setSignupError('Passwords do not match');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(signupEmail)) {
      setSignupError('Please enter a valid email');
      return;
    }

    setSignupLoading(true);
    try {
      await signup(signupName, signupEmail, signupPassword);
      navigate('/');
    } catch (err) {
      setSignupError(err.message || 'Registration failed');
    } finally {
      setSignupLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0c1220] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden shadow-2xl">
          {/* Gradient accent bar */}
          <div className="h-1 bg-gradient-to-r from-[#3b82f6] via-[#6366f1] to-[#3b82f6]" />

          {/* Header */}
          <div className="px-8 pt-8 pb-2 text-center">
            <h1 className="text-xl font-semibold text-[#f1f5f9] tracking-tight">
              NSE Signal Engine
            </h1>
            <p className="mt-1 text-sm text-[#64748b]">
              Stock analysis powered by AI
            </p>
          </div>

          {/* Tabs */}
          <div className="flex mx-8 mt-6 bg-[#0c1220] rounded-lg p-1">
            <button
              onClick={() => setActiveTab('signin')}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                activeTab === 'signin'
                  ? 'bg-[#1f2937] text-[#f1f5f9] shadow-sm'
                  : 'text-[#64748b] hover:text-[#94a3b8]'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setActiveTab('signup')}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                activeTab === 'signup'
                  ? 'bg-[#1f2937] text-[#f1f5f9] shadow-sm'
                  : 'text-[#64748b] hover:text-[#94a3b8]'
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Sign In Form */}
          {activeTab === 'signin' && (
            <form onSubmit={handleLogin} className="px-8 pt-6 pb-8 space-y-4">
              {loginError && (
                <div className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {loginError}
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-[#94a3b8] mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full px-3 py-2.5 bg-[#0c1220] border border-[#1f2937] rounded-lg text-sm text-[#f1f5f9] placeholder-[#475569] focus:outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]/30 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#94a3b8] mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showLoginPass ? 'text' : 'password'}
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="w-full px-3 py-2.5 pr-10 bg-[#0c1220] border border-[#1f2937] rounded-lg text-sm text-[#f1f5f9] placeholder-[#475569] focus:outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]/30 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowLoginPass(!showLoginPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#475569] hover:text-[#94a3b8]"
                  >
                    {showLoginPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loginLoading}
                className="w-full py-2.5 bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors flex items-center justify-center gap-2"
              >
                {loginLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                {loginLoading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>
          )}

          {/* Sign Up Form */}
          {activeTab === 'signup' && (
            <form onSubmit={handleSignup} className="px-8 pt-6 pb-8 space-y-4">
              {signupError && (
                <div className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {signupError}
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-[#94a3b8] mb-1.5">
                  Name
                </label>
                <input
                  type="text"
                  value={signupName}
                  onChange={(e) => setSignupName(e.target.value)}
                  placeholder="Your full name"
                  className="w-full px-3 py-2.5 bg-[#0c1220] border border-[#1f2937] rounded-lg text-sm text-[#f1f5f9] placeholder-[#475569] focus:outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]/30 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#94a3b8] mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  value={signupEmail}
                  onChange={(e) => setSignupEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full px-3 py-2.5 bg-[#0c1220] border border-[#1f2937] rounded-lg text-sm text-[#f1f5f9] placeholder-[#475569] focus:outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]/30 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#94a3b8] mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showSignupPass ? 'text' : 'password'}
                    value={signupPassword}
                    onChange={(e) => setSignupPassword(e.target.value)}
                    placeholder="Min 6 characters"
                    className="w-full px-3 py-2.5 pr-10 bg-[#0c1220] border border-[#1f2937] rounded-lg text-sm text-[#f1f5f9] placeholder-[#475569] focus:outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]/30 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowSignupPass(!showSignupPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#475569] hover:text-[#94a3b8]"
                  >
                    {showSignupPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#94a3b8] mb-1.5">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={signupConfirm}
                  onChange={(e) => setSignupConfirm(e.target.value)}
                  placeholder="Re-enter password"
                  className="w-full px-3 py-2.5 bg-[#0c1220] border border-[#1f2937] rounded-lg text-sm text-[#f1f5f9] placeholder-[#475569] focus:outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]/30 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={signupLoading}
                className="w-full py-2.5 bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors flex items-center justify-center gap-2"
              >
                {signupLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                {signupLoading ? 'Creating account...' : 'Create Account'}
              </button>
            </form>
          )}
        </div>

        {/* Footer text */}
        <p className="text-center mt-6 text-xs text-[#475569]">
          For educational purposes only. Not financial advice.
        </p>
      </div>
    </div>
  );
}

export default Login;

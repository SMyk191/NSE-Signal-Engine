import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  LineChart,
  MessageSquare,
  BarChart3,
  Shield,
  ShieldCheck,
  Search,
  History,
  Menu,
  X,
  LogOut,
  User,
  Loader2,
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import SentimentAnalysis from './pages/SentimentAnalysis';
import EarningsPredictor from './pages/EarningsPredictor';
import PortfolioRisk from './pages/PortfolioRisk';
import Screener from './pages/Screener';
import BacktestResults from './pages/BacktestResults';
import TechnicalAnalysis from './pages/TechnicalAnalysis';
import Admin from './pages/Admin';
import Login from './pages/Login';
import UpstoxCallback from './pages/UpstoxCallback';
import DisclaimerFooter from './components/DisclaimerFooter';
import useAuthStore from './stores/authStore';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/technical', icon: LineChart, label: 'Technical' },
  { to: '/sentiment', icon: MessageSquare, label: 'Sentiment' },
  { to: '/earnings', icon: BarChart3, label: 'Earnings' },
  { to: '/portfolio', icon: Shield, label: 'Portfolio' },
  { to: '/screener', icon: Search, label: 'Screener' },
  { to: '/backtest', icon: History, label: 'Backtest' },
];

function Sidebar({ mobileOpen, onClose }) {
  const { user, logout } = useAuthStore();

  return (
    <>
      {/* Mobile backdrop overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden animate-fade-in"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed left-0 top-0 bottom-0 w-60 bg-[#0f1729] border-r border-[#1f2937] flex flex-col z-50 transition-transform duration-200 ease-out ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Logo area */}
        <div className="px-5 pt-6 pb-5 flex items-center justify-between">
          <div>
            <h1 className="text-[15px] font-semibold text-[#f1f5f9] tracking-[-0.01em]">
              NSE Signal Engine
            </h1>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1 rounded-md text-[#64748b] hover:text-[#94a3b8] transition-smooth"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                `relative flex items-center gap-3 px-3 py-1.5 rounded-md text-[13px] group transition-smooth ${
                  isActive
                    ? 'text-[#f1f5f9]'
                    : 'text-[#64748b] hover:text-[#94a3b8]'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* Active left border indicator */}
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-[#3b82f6] rounded-r-full" />
                  )}
                  <Icon
                    className={`w-[18px] h-[18px] flex-shrink-0 ${
                      isActive ? 'text-[#3b82f6]' : ''
                    }`}
                  />
                  <span className={isActive ? 'font-medium' : ''}>{label}</span>
                </>
              )}
            </NavLink>
          ))}

          {/* Admin nav — only for admin users */}
          {user?.role === 'admin' && (
            <>
              <div className="border-t border-[#1f2937] my-3 mx-1" />
              <NavLink
                to="/admin"
                onClick={onClose}
                className={({ isActive }) =>
                  `relative flex items-center gap-3 px-3 py-1.5 rounded-md text-[13px] group transition-smooth ${
                    isActive
                      ? 'text-[#f1f5f9]'
                      : 'text-[#64748b] hover:text-[#94a3b8]'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-[#a78bfa] rounded-r-full" />
                    )}
                    <ShieldCheck
                      className={`w-[18px] h-[18px] flex-shrink-0 ${
                        isActive ? 'text-[#a78bfa]' : ''
                      }`}
                    />
                    <span className={isActive ? 'font-medium' : ''}>Admin</span>
                  </>
                )}
              </NavLink>
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="px-4 py-4 border-t border-[#1f2937]">
          {user ? (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#3b82f6]/20 flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4 text-[#3b82f6]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-[#f1f5f9] truncate">
                  {user.name}
                </p>
                <p className="text-[10px] text-[#64748b] truncate">
                  {user.email}
                </p>
              </div>
              <button
                onClick={logout}
                title="Sign out"
                className="p-1.5 rounded-md text-[#64748b] hover:text-red-400 hover:bg-red-400/10 transition-all"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <span className="text-[11px] text-[#475569]">v1.0</span>
          )}
        </div>
      </aside>
    </>
  );
}

function AnimatedPage({ children }) {
  const location = useLocation();
  return (
    <div key={location.pathname} className="animate-fade-up">
      {children}
    </div>
  );
}

function ProtectedLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#0c1220]">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <main className="lg:ml-60 min-h-screen flex flex-col">
        {/* Mobile menu button */}
        <div className="lg:hidden sticky top-0 z-30 bg-[#0c1220]/80 backdrop-blur-md border-b border-[#1f2937]/60 px-4 py-3">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-md text-[#64748b] hover:text-[#94a3b8] hover:bg-[#1a2332] transition-smooth"
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>

        {/* Main content area */}
        <div className="flex-1 w-full max-w-[1440px] mx-auto p-8">
          <AnimatedPage>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/technical/:symbol?" element={<TechnicalAnalysis />} />
              <Route path="/sentiment/:symbol?" element={<SentimentAnalysis />} />
              <Route path="/earnings/:symbol?" element={<EarningsPredictor />} />
              <Route path="/portfolio" element={<PortfolioRisk />} />
              <Route path="/screener" element={<Screener />} />
              <Route path="/backtest" element={<BacktestResults />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AnimatedPage>
        </div>

        <DisclaimerFooter />
      </main>
    </div>
  );
}

function AuthGate() {
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const location = useLocation();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0c1220] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-[#3b82f6] animate-spin" />
      </div>
    );
  }

  return (
    <Routes>
      {/* Upstox OAuth callback — must work without login */}
      <Route path="/callback" element={<UpstoxCallback />} />
      <Route
        path="/login"
        element={
          isAuthenticated ? <Navigate to="/" replace /> : <Login />
        }
      />
      <Route
        path="/*"
        element={
          isAuthenticated ? (
            <ProtectedLayout />
          ) : (
            <Navigate to="/login" replace state={{ from: location }} />
          )
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthGate />
    </BrowserRouter>
  );
}

export default App;

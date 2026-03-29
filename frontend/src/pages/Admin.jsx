import { useState, useEffect, useCallback } from 'react';
import {
  Shield,
  Users,
  UserCheck,
  Clock,
  UserX,
  Search,
  Check,
  X,
  ChevronDown,
  Trash2,
  Loader2,
  Save,
  RefreshCw,
  AlertTriangle,
  ShieldAlert,
} from 'lucide-react';
import api from '../services/api';
import useAuthStore from '../stores/authStore';

const STATUS_STYLES = {
  active: { bg: 'bg-[#22c55e]/10', text: 'text-[#22c55e]', border: 'border-[#22c55e]/20', label: 'Active' },
  pending: { bg: 'bg-[#f59e0b]/10', text: 'text-[#f59e0b]', border: 'border-[#f59e0b]/20', label: 'Pending' },
  suspended: { bg: 'bg-[#ef4444]/10', text: 'text-[#ef4444]', border: 'border-[#ef4444]/20', label: 'Suspended' },
  banned: { bg: 'bg-[#991b1b]/10', text: 'text-[#fca5a5]', border: 'border-[#991b1b]/20', label: 'Banned' },
};

const ROLE_STYLES = {
  admin: { bg: 'bg-[#a78bfa]/10', text: 'text-[#a78bfa]', border: 'border-[#a78bfa]/20', label: 'Admin' },
  premium: { bg: 'bg-[#3b82f6]/10', text: 'text-[#3b82f6]', border: 'border-[#3b82f6]/20', label: 'Premium' },
  user: { bg: 'bg-[#64748b]/10', text: 'text-[#94a3b8]', border: 'border-[#64748b]/20', label: 'User' },
};

const ACTION_COLORS = {
  login: 'text-[#3b82f6]',
  logout: 'text-[#64748b]',
  view_stock: 'text-[#22c55e]',
  run_screener: 'text-[#a78bfa]',
  run_backtest: 'text-[#f59e0b]',
  signup: 'text-[#6366f1]',
  view_sentiment: 'text-[#ec4899]',
  view_earnings: 'text-[#14b8a6]',
  view_portfolio: 'text-[#f97316]',
};

function Badge({ type, map }) {
  const style = map[type] || map.user || { bg: 'bg-[#64748b]/10', text: 'text-[#94a3b8]', border: 'border-[#64748b]/20', label: type };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium border ${style.bg} ${style.text} ${style.border}`}>
      {style.label}
    </span>
  );
}

function StatCard({ icon: Icon, label, value, color, loading }) {
  const colorMap = {
    blue: { bg: 'bg-[#3b82f6]/10', text: 'text-[#3b82f6]', icon: 'text-[#3b82f6]' },
    green: { bg: 'bg-[#22c55e]/10', text: 'text-[#22c55e]', icon: 'text-[#22c55e]' },
    amber: { bg: 'bg-[#f59e0b]/10', text: 'text-[#f59e0b]', icon: 'text-[#f59e0b]' },
    red: { bg: 'bg-[#ef4444]/10', text: 'text-[#ef4444]', icon: 'text-[#ef4444]' },
  };
  const c = colorMap[color];
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[12px] font-medium text-[#64748b] uppercase tracking-wide">{label}</p>
          {loading ? (
            <Loader2 className="w-5 h-5 text-[#64748b] animate-spin mt-2" />
          ) : (
            <p className={`text-2xl font-bold mt-1 font-mono ${c.text}`}>{value ?? '—'}</p>
          )}
        </div>
        <div className={`w-10 h-10 rounded-lg ${c.bg} flex items-center justify-center`}>
          <Icon className={`w-5 h-5 ${c.icon}`} />
        </div>
      </div>
    </div>
  );
}

function ActionsDropdown({ user, currentUserId, onAction }) {
  const [open, setOpen] = useState(false);
  const isSelf = user._id === currentUserId || user.id === currentUserId;

  if (isSelf) return <span className="text-[11px] text-[#475569]">You</span>;

  const statusActions = [
    user.status !== 'active' && { label: 'Activate', action: 'status', value: 'active' },
    user.status !== 'suspended' && { label: 'Suspend', action: 'status', value: 'suspended' },
    user.status !== 'banned' && { label: 'Ban', action: 'status', value: 'banned' },
  ].filter(Boolean);

  const roleActions = [
    user.role !== 'admin' && { label: 'Make Admin', action: 'role', value: 'admin' },
    user.role !== 'premium' && { label: 'Make Premium', action: 'role', value: 'premium' },
    user.role !== 'user' && { label: 'Make User', action: 'role', value: 'user' },
  ].filter(Boolean);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[12px] font-medium text-[#94a3b8] bg-[#1f2937] hover:bg-[#374151] border border-[#374151] transition-all"
      >
        Actions <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 w-44 bg-[#1a2332] border border-[#1f2937] rounded-lg shadow-xl z-50 py-1 overflow-hidden">
            <div className="px-2 py-1.5 text-[10px] font-semibold text-[#475569] uppercase tracking-wider">Status</div>
            {statusActions.map((a) => (
              <button
                key={a.value}
                onClick={() => { onAction(user, a.action, a.value); setOpen(false); }}
                className="w-full text-left px-3 py-1.5 text-[12px] text-[#94a3b8] hover:bg-[#111827] hover:text-[#f1f5f9] transition-colors"
              >
                {a.label}
              </button>
            ))}
            <div className="border-t border-[#1f2937] my-1" />
            <div className="px-2 py-1.5 text-[10px] font-semibold text-[#475569] uppercase tracking-wider">Role</div>
            {roleActions.map((a) => (
              <button
                key={a.value}
                onClick={() => { onAction(user, a.action, a.value); setOpen(false); }}
                className="w-full text-left px-3 py-1.5 text-[12px] text-[#94a3b8] hover:bg-[#111827] hover:text-[#f1f5f9] transition-colors"
              >
                {a.label}
              </button>
            ))}
            <div className="border-t border-[#1f2937] my-1" />
            <button
              onClick={() => { onAction(user, 'delete'); setOpen(false); }}
              className="w-full text-left px-3 py-1.5 text-[12px] text-red-400 hover:bg-red-500/10 transition-colors flex items-center gap-2"
            >
              <Trash2 className="w-3 h-3" /> Delete User
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Admin() {
  const { user: currentUser } = useAuthStore();

  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [activity, setActivity] = useState([]);
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState({ stats: true, users: true, activity: true, settings: true });
  const [searchQuery, setSearchQuery] = useState('');
  const [activityFilter, setActivityFilter] = useState('all');
  const [savingSettings, setSavingSettings] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/admin/stats');
      setStats(res.data);
    } catch {
      // silent
    } finally {
      setLoading((p) => ({ ...p, stats: false }));
    }
  }, []);

  const fetchUsers = useCallback(async () => {
    try {
      const res = await api.get('/admin/users');
      setUsers(res.data);
    } catch {
      // silent
    } finally {
      setLoading((p) => ({ ...p, users: false }));
    }
  }, []);

  const fetchActivity = useCallback(async () => {
    try {
      const res = await api.get('/admin/activity', { params: { limit: 50 } });
      setActivity(res.data);
    } catch {
      // silent
    } finally {
      setLoading((p) => ({ ...p, activity: false }));
    }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await api.get('/admin/settings');
      setSettings(res.data);
    } catch {
      // silent
    } finally {
      setLoading((p) => ({ ...p, settings: false }));
    }
  }, []);

  useEffect(() => {
    if (currentUser?.role === 'admin') {
      fetchStats();
      fetchUsers();
      fetchActivity();
      fetchSettings();
    }
  }, [currentUser, fetchStats, fetchUsers, fetchActivity, fetchSettings]);

  const handleUserAction = async (targetUser, action, value) => {
    const userId = targetUser._id || targetUser.id;

    if (action === 'delete') {
      setDeleteConfirm(targetUser);
      return;
    }

    setActionLoading(userId);
    try {
      if (action === 'status') {
        await api.put(`/admin/users/${userId}/status`, { status: value });
        showToast(`User ${targetUser.name} status changed to ${value}`);
      } else if (action === 'role') {
        await api.put(`/admin/users/${userId}/role`, { role: value });
        showToast(`User ${targetUser.name} role changed to ${value}`);
      }
      fetchUsers();
      fetchStats();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Action failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    const userId = deleteConfirm._id || deleteConfirm.id;
    setActionLoading(userId);
    try {
      await api.delete(`/admin/users/${userId}`);
      showToast(`User ${deleteConfirm.name} deleted`);
      setDeleteConfirm(null);
      fetchUsers();
      fetchStats();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Delete failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleApprove = async (targetUser) => {
    await handleUserAction(targetUser, 'status', 'active');
  };

  const handleReject = async (targetUser) => {
    await handleUserAction(targetUser, 'status', 'banned');
  };

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      for (const [key, value] of Object.entries(settings)) {
        await api.put('/admin/settings', { key, value });
      }
      showToast('Settings saved successfully');
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to save settings', 'error');
    } finally {
      setSavingSettings(false);
    }
  };

  const refreshAll = () => {
    setLoading({ stats: true, users: true, activity: true, settings: true });
    fetchStats();
    fetchUsers();
    fetchActivity();
    fetchSettings();
  };

  // Access control
  if (!currentUser || currentUser.role !== 'admin') {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full bg-[#ef4444]/10 flex items-center justify-center mx-auto mb-4">
            <ShieldAlert className="w-8 h-8 text-[#ef4444]" />
          </div>
          <h2 className="text-xl font-semibold text-[#f1f5f9] mb-2">Access Denied</h2>
          <p className="text-sm text-[#64748b]">You do not have permission to access the admin dashboard.</p>
        </div>
      </div>
    );
  }

  const pendingUsers = users.filter((u) => u.status === 'pending');
  const filteredUsers = users.filter((u) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
  });

  const filteredActivity = activity.filter((a) => {
    if (activityFilter === 'all') return true;
    return a.action === activityFilter;
  });

  const activityActions = [...new Set(activity.map((a) => a.action))].sort();

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const formatDateTime = (dateStr) => {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-6 right-6 z-[100] px-4 py-3 rounded-lg border shadow-xl text-sm font-medium animate-fade-in ${
          toast.type === 'error'
            ? 'bg-[#ef4444]/10 border-[#ef4444]/30 text-[#fca5a5]'
            : 'bg-[#22c55e]/10 border-[#22c55e]/30 text-[#22c55e]'
        }`}>
          {toast.message}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#111827] border border-[#1f2937] rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[#ef4444]/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-[#ef4444]" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#f1f5f9]">Delete User</h3>
                <p className="text-xs text-[#64748b]">This action cannot be undone</p>
              </div>
            </div>
            <p className="text-sm text-[#94a3b8] mb-5">
              Are you sure you want to permanently delete <span className="font-medium text-[#f1f5f9]">{deleteConfirm.name}</span> ({deleteConfirm.email})?
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 px-3 py-2 rounded-lg text-sm font-medium text-[#94a3b8] bg-[#1f2937] hover:bg-[#374151] border border-[#374151] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={actionLoading}
                className="flex-1 px-3 py-2 rounded-lg text-sm font-medium text-white bg-[#ef4444] hover:bg-[#dc2626] disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#a78bfa]/10 flex items-center justify-center">
            <Shield className="w-5 h-5 text-[#a78bfa]" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-[#f1f5f9] tracking-tight">Admin Dashboard</h1>
            <p className="text-xs text-[#64748b]">Manage users, settings, and monitor activity</p>
          </div>
        </div>
        <button
          onClick={refreshAll}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-[12px] font-medium text-[#94a3b8] bg-[#111827] hover:bg-[#1f2937] border border-[#1f2937] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Users} label="Total Users" value={stats?.total_users} color="blue" loading={loading.stats} />
        <StatCard icon={UserCheck} label="Active Users" value={stats?.active_users} color="green" loading={loading.stats} />
        <StatCard icon={Clock} label="Pending Approval" value={stats?.pending_users} color="amber" loading={loading.stats} />
        <StatCard icon={UserX} label="Suspended / Banned" value={stats?.suspended_users} color="red" loading={loading.stats} />
      </div>

      {/* Pending Approvals */}
      {pendingUsers.length > 0 && (
        <div className="bg-[#111827] border border-[#f59e0b]/20 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#1f2937] flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#f59e0b] animate-pulse" />
            <h2 className="text-sm font-semibold text-[#f1f5f9]">
              Pending Approvals
              <span className="ml-2 text-xs font-normal text-[#f59e0b]">({pendingUsers.length})</span>
            </h2>
          </div>
          <div className="divide-y divide-[#1f2937]">
            {pendingUsers.map((u) => {
              const uid = u._id || u.id;
              return (
                <div key={uid} className="px-5 py-3 flex items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#f1f5f9] truncate">{u.name}</p>
                    <p className="text-xs text-[#64748b] truncate">{u.email}</p>
                  </div>
                  <p className="text-xs text-[#64748b] hidden sm:block whitespace-nowrap">
                    Signed up {formatDate(u.created_at)}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleApprove(u)}
                      disabled={actionLoading === uid}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-white bg-[#22c55e] hover:bg-[#16a34a] disabled:opacity-50 transition-colors"
                    >
                      {actionLoading === uid ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                      Approve
                    </button>
                    <button
                      onClick={() => handleReject(u)}
                      disabled={actionLoading === uid}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-white bg-[#ef4444] hover:bg-[#dc2626] disabled:opacity-50 transition-colors"
                    >
                      {actionLoading === uid ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                      Reject
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Users Table */}
      <div className="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-[#1f2937] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-[#f1f5f9]">
            All Users
            <span className="ml-2 text-xs font-normal text-[#64748b]">({filteredUsers.length})</span>
          </h2>
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#475569]" />
            <input
              type="text"
              placeholder="Search by name or email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-[#0c1220] border border-[#1f2937] rounded-lg text-[12px] text-[#f1f5f9] placeholder-[#475569] focus:outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]/30 transition-all"
            />
          </div>
        </div>

        {loading.users ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-[#3b82f6] animate-spin" />
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="text-center py-12 text-sm text-[#64748b]">No users found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#1f2937]">
                  <th className="text-left px-5 py-3 text-[11px] font-semibold text-[#475569] uppercase tracking-wider">Name</th>
                  <th className="text-left px-5 py-3 text-[11px] font-semibold text-[#475569] uppercase tracking-wider">Email</th>
                  <th className="text-left px-5 py-3 text-[11px] font-semibold text-[#475569] uppercase tracking-wider">Role</th>
                  <th className="text-left px-5 py-3 text-[11px] font-semibold text-[#475569] uppercase tracking-wider">Status</th>
                  <th className="text-left px-5 py-3 text-[11px] font-semibold text-[#475569] uppercase tracking-wider hidden lg:table-cell">Last Login</th>
                  <th className="text-left px-5 py-3 text-[11px] font-semibold text-[#475569] uppercase tracking-wider hidden lg:table-cell">Logins</th>
                  <th className="text-right px-5 py-3 text-[11px] font-semibold text-[#475569] uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1f2937]/60">
                {filteredUsers.map((u) => {
                  const uid = u._id || u.id;
                  return (
                    <tr key={uid} className="hover:bg-[#0c1220]/50 transition-colors">
                      <td className="px-5 py-3">
                        <p className="text-sm font-medium text-[#f1f5f9] truncate max-w-[160px]">{u.name}</p>
                      </td>
                      <td className="px-5 py-3">
                        <p className="text-xs text-[#94a3b8] truncate max-w-[200px]">{u.email}</p>
                      </td>
                      <td className="px-5 py-3"><Badge type={u.role} map={ROLE_STYLES} /></td>
                      <td className="px-5 py-3"><Badge type={u.status} map={STATUS_STYLES} /></td>
                      <td className="px-5 py-3 hidden lg:table-cell">
                        <p className="text-xs text-[#64748b] font-mono">{formatDateTime(u.last_login)}</p>
                      </td>
                      <td className="px-5 py-3 hidden lg:table-cell">
                        <p className="text-xs text-[#94a3b8] font-mono">{u.login_count ?? '—'}</p>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <ActionsDropdown
                          user={u}
                          currentUserId={currentUser?._id || currentUser?.id}
                          onAction={handleUserAction}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Activity Log & Settings side by side */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Activity Log */}
        <div className="xl:col-span-2 bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#1f2937] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-[#f1f5f9]">Activity Log</h2>
            <select
              value={activityFilter}
              onChange={(e) => setActivityFilter(e.target.value)}
              className="bg-[#0c1220] border border-[#1f2937] rounded-lg text-[12px] text-[#94a3b8] px-3 py-1.5 focus:outline-none focus:border-[#3b82f6] transition-all"
            >
              <option value="all">All Actions</option>
              {activityActions.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>

          {loading.activity ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-[#3b82f6] animate-spin" />
            </div>
          ) : filteredActivity.length === 0 ? (
            <div className="text-center py-12 text-sm text-[#64748b]">No activity recorded</div>
          ) : (
            <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
              <table className="w-full">
                <thead className="sticky top-0 bg-[#111827]">
                  <tr className="border-b border-[#1f2937]">
                    <th className="text-left px-5 py-2.5 text-[11px] font-semibold text-[#475569] uppercase tracking-wider">Time</th>
                    <th className="text-left px-5 py-2.5 text-[11px] font-semibold text-[#475569] uppercase tracking-wider">User</th>
                    <th className="text-left px-5 py-2.5 text-[11px] font-semibold text-[#475569] uppercase tracking-wider">Action</th>
                    <th className="text-left px-5 py-2.5 text-[11px] font-semibold text-[#475569] uppercase tracking-wider hidden md:table-cell">Details</th>
                    <th className="text-left px-5 py-2.5 text-[11px] font-semibold text-[#475569] uppercase tracking-wider hidden lg:table-cell">IP</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1f2937]/60">
                  {filteredActivity.map((a, i) => (
                    <tr key={i} className="hover:bg-[#0c1220]/50 transition-colors">
                      <td className="px-5 py-2.5">
                        <p className="text-[11px] text-[#64748b] font-mono whitespace-nowrap">{formatDateTime(a.timestamp || a.time)}</p>
                      </td>
                      <td className="px-5 py-2.5">
                        <p className="text-xs text-[#94a3b8] truncate max-w-[120px]">{a.user_name || a.user || '—'}</p>
                      </td>
                      <td className="px-5 py-2.5">
                        <span className={`text-xs font-medium font-mono ${ACTION_COLORS[a.action] || 'text-[#94a3b8]'}`}>
                          {a.action}
                        </span>
                      </td>
                      <td className="px-5 py-2.5 hidden md:table-cell">
                        <p className="text-xs text-[#64748b] truncate max-w-[200px]">{a.details || '—'}</p>
                      </td>
                      <td className="px-5 py-2.5 hidden lg:table-cell">
                        <p className="text-[11px] text-[#475569] font-mono">{a.ip || '—'}</p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Settings Panel */}
        <div className="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden h-fit">
          <div className="px-5 py-4 border-b border-[#1f2937]">
            <h2 className="text-sm font-semibold text-[#f1f5f9]">Settings</h2>
          </div>

          {loading.settings ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-[#3b82f6] animate-spin" />
            </div>
          ) : (
            <div className="px-5 py-4 space-y-5">
              {/* Require Approval */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#f1f5f9]">Require Approval</p>
                  <p className="text-xs text-[#64748b] mt-0.5">New signups need admin approval</p>
                </div>
                <button
                  onClick={() => setSettings((s) => ({ ...s, require_approval: !s.require_approval }))}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    settings.require_approval ? 'bg-[#3b82f6]' : 'bg-[#374151]'
                  }`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                    settings.require_approval ? 'translate-x-5' : ''
                  }`} />
                </button>
              </div>

              {/* Allow Signups */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#f1f5f9]">Allow Signups</p>
                  <p className="text-xs text-[#64748b] mt-0.5">Enable new user registration</p>
                </div>
                <button
                  onClick={() => setSettings((s) => ({ ...s, allow_signups: !s.allow_signups }))}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    settings.allow_signups ? 'bg-[#3b82f6]' : 'bg-[#374151]'
                  }`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                    settings.allow_signups ? 'translate-x-5' : ''
                  }`} />
                </button>
              </div>

              {/* Max Users */}
              <div>
                <label className="block text-sm text-[#f1f5f9] mb-1.5">Max Users</label>
                <input
                  type="number"
                  value={settings.max_users ?? ''}
                  onChange={(e) => setSettings((s) => ({ ...s, max_users: parseInt(e.target.value) || 0 }))}
                  className="w-full px-3 py-2 bg-[#0c1220] border border-[#1f2937] rounded-lg text-sm text-[#f1f5f9] font-mono focus:outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]/30 transition-all"
                />
                <p className="text-xs text-[#64748b] mt-1">Maximum allowed registered users (0 = unlimited)</p>
              </div>

              <button
                onClick={handleSaveSettings}
                disabled={savingSettings}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-50 transition-colors"
              >
                {savingSettings ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {savingSettings ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Admin;

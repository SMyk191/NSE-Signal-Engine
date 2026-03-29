import { create } from 'zustand';
import api from '../services/api';

const TOKEN_KEY = 'nse_token';

const useAuthStore = create((set, get) => ({
  user: null,
  token: localStorage.getItem(TOKEN_KEY) || null,
  isAuthenticated: false,
  isLoading: true, // true until initial checkAuth completes

  login: async (email, password) => {
    try {
      const res = await api.post('/auth/login', { email, password });
      const { token, user } = res.data;
      localStorage.setItem(TOKEN_KEY, token);
      set({ user, token, isAuthenticated: true });
    } catch (err) {
      const message =
        err.response?.data?.detail || 'Invalid email or password';
      throw new Error(message);
    }
  },

  signup: async (name, email, password) => {
    try {
      const res = await api.post('/auth/signup', { email, password, name });
      const { token, user } = res.data;
      localStorage.setItem(TOKEN_KEY, token);
      set({ user, token, isAuthenticated: true });
    } catch (err) {
      const message =
        err.response?.data?.detail || 'Registration failed';
      throw new Error(message);
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    set({ user: null, token: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      set({ isLoading: false, isAuthenticated: false });
      return;
    }
    try {
      const res = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      set({
        user: res.data,
        token,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      set({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  },
}));

export default useAuthStore;

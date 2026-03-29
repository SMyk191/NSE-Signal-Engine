import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token to every request if present in localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('nse_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Stocks
export const fetchStocks = () => api.get('/stocks').then((res) => res.data);
export const fetchStock = (symbol) => api.get(`/stocks/${symbol}`).then((res) => res.data);
export const fetchOHLCV = (symbol, period = '1y', interval = '1d') =>
  api.get(`/stocks/${symbol}/ohlcv`, { params: { period, interval } }).then((res) => res.data);
export const fetchIndicators = (symbol, includeSeries = false) =>
  api.get(`/stocks/${symbol}/indicators`, { params: { include_series: includeSeries } }).then((res) => res.data);
export const fetchSignal = (symbol) =>
  api.get(`/stocks/${symbol}/signal`).then((res) => res.data);
export const fetchSentiment = (symbol) =>
  api.get(`/stocks/${symbol}/sentiment`).then((res) => res.data);
export const fetchEarnings = (symbol) =>
  api.get(`/stocks/${symbol}/earnings`).then((res) => res.data);
export const fetchRisk = (symbol) =>
  api.get(`/stocks/${symbol}/risk`).then((res) => res.data);

// Portfolio
export const analyzePortfolio = (stocks, weights) =>
  api.post('/portfolio/analyze', { stocks, weights }).then((res) => res.data);
export const fetchPortfolioRisk = () =>
  api.get('/portfolio/risk').then((res) => res.data);
export const fetchEfficientFrontier = () =>
  api.get('/portfolio/efficient-frontier').then((res) => res.data);
export const fetchMonteCarlo = () =>
  api.get('/portfolio/monte-carlo').then((res) => res.data);

// Screener
export const screenStocks = (filters) =>
  api.post('/screener', filters).then((res) => res.data);

// Backtest
export const runBacktest = (params) =>
  api.post('/backtest', params).then((res) => res.data);

// Alerts
export const fetchAlerts = () => api.get('/alerts').then((res) => res.data);

// Market
export const fetchMarketOverview = () =>
  api.get('/market/overview').then((res) => res.data);

export default api;

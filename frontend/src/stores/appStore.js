import { create } from 'zustand';

const useAppStore = create((set) => ({
  selectedStock: 'RELIANCE',
  portfolio: [],

  setSelectedStock: (symbol) => set({ selectedStock: symbol }),

  addToPortfolio: (symbol, weight = 0) =>
    set((state) => {
      if (state.portfolio.some((p) => p.symbol === symbol)) return state;
      return { portfolio: [...state.portfolio, { symbol, weight }] };
    }),

  removeFromPortfolio: (symbol) =>
    set((state) => ({
      portfolio: state.portfolio.filter((p) => p.symbol !== symbol),
    })),

  updateWeights: (symbol, weight) =>
    set((state) => ({
      portfolio: state.portfolio.map((p) =>
        p.symbol === symbol ? { ...p, weight } : p
      ),
    })),
}));

export default useAppStore;

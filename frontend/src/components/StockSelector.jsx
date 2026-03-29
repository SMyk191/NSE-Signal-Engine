import { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Search, Loader2 } from 'lucide-react';
import axios from 'axios';
import useAppStore from '../stores/appStore';

const API_BASE = '/api';

const NIFTY_50 = [
  { symbol: 'ADANIENT', name: 'Adani Enterprises' },
  { symbol: 'ADANIPORTS', name: 'Adani Ports & SEZ' },
  { symbol: 'APOLLOHOSP', name: 'Apollo Hospitals' },
  { symbol: 'ASIANPAINT', name: 'Asian Paints' },
  { symbol: 'AXISBANK', name: 'Axis Bank' },
  { symbol: 'BAJAJ-AUTO', name: 'Bajaj Auto' },
  { symbol: 'BAJFINANCE', name: 'Bajaj Finance' },
  { symbol: 'BAJAJFINSV', name: 'Bajaj Finserv' },
  { symbol: 'BHARTIARTL', name: 'Bharti Airtel' },
  { symbol: 'BPCL', name: 'Bharat Petroleum' },
  { symbol: 'BRITANNIA', name: 'Britannia Industries' },
  { symbol: 'CIPLA', name: 'Cipla' },
  { symbol: 'COALINDIA', name: 'Coal India' },
  { symbol: 'DIVISLAB', name: "Divi's Laboratories" },
  { symbol: 'DRREDDY', name: "Dr. Reddy's Labs" },
  { symbol: 'EICHERMOT', name: 'Eicher Motors' },
  { symbol: 'GRASIM', name: 'Grasim Industries' },
  { symbol: 'HCLTECH', name: 'HCL Technologies' },
  { symbol: 'HDFCBANK', name: 'HDFC Bank' },
  { symbol: 'HDFCLIFE', name: 'HDFC Life Insurance' },
  { symbol: 'HEROMOTOCO', name: 'Hero MotoCorp' },
  { symbol: 'HINDALCO', name: 'Hindalco Industries' },
  { symbol: 'HINDUNILVR', name: 'Hindustan Unilever' },
  { symbol: 'ICICIBANK', name: 'ICICI Bank' },
  { symbol: 'INDUSINDBK', name: 'IndusInd Bank' },
  { symbol: 'INFY', name: 'Infosys' },
  { symbol: 'ITC', name: 'ITC' },
  { symbol: 'JSWSTEEL', name: 'JSW Steel' },
  { symbol: 'KOTAKBANK', name: 'Kotak Mahindra Bank' },
  { symbol: 'LT', name: 'Larsen & Toubro' },
  { symbol: 'LTIM', name: 'LTIMindtree' },
  { symbol: 'M&M', name: 'Mahindra & Mahindra' },
  { symbol: 'MARUTI', name: 'Maruti Suzuki' },
  { symbol: 'NESTLEIND', name: 'Nestle India' },
  { symbol: 'NTPC', name: 'NTPC' },
  { symbol: 'ONGC', name: 'Oil & Natural Gas Corp' },
  { symbol: 'POWERGRID', name: 'Power Grid Corp' },
  { symbol: 'RELIANCE', name: 'Reliance Industries' },
  { symbol: 'SBILIFE', name: 'SBI Life Insurance' },
  { symbol: 'SBIN', name: 'State Bank of India' },
  { symbol: 'SUNPHARMA', name: 'Sun Pharmaceutical' },
  { symbol: 'TATACONSUM', name: 'Tata Consumer Products' },
  { symbol: 'TATAMOTORS', name: 'Tata Motors' },
  { symbol: 'TATASTEEL', name: 'Tata Steel' },
  { symbol: 'TCS', name: 'Tata Consultancy Services' },
  { symbol: 'TECHM', name: 'Tech Mahindra' },
  { symbol: 'TITAN', name: 'Titan Company' },
  { symbol: 'ULTRACEMCO', name: 'UltraTech Cement' },
  { symbol: 'UPL', name: 'UPL' },
  { symbol: 'WIPRO', name: 'Wipro' },
];

export { NIFTY_50 };

export default function StockSelector({ className = '' }) {
  const { selectedStock, setSelectedStock } = useAppStore();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [allStocks, setAllStocks] = useState(NIFTY_50); // starts with NIFTY 50, loads full list
  const [allLoaded, setAllLoaded] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  // Load ALL NSE stocks on first dropdown open
  useEffect(() => {
    if (!open || allLoaded) return;
    axios
      .get(`${API_BASE}/stocks/all`)
      .then((res) => {
        const stocks = (res.data?.stocks || []).map((s) => ({
          symbol: s.symbol,
          name: s.name || s.symbol,
        }));
        if (stocks.length > 0) {
          setAllStocks(stocks);
          setAllLoaded(true);
        }
      })
      .catch(() => {}); // silently keep NIFTY 50 as fallback
  }, [open, allLoaded]);

  // Local filter across ALL loaded stocks
  const localFiltered = search.length > 0
    ? allStocks.filter(
        (s) =>
          s.symbol.toLowerCase().includes(search.toLowerCase()) ||
          s.name.toLowerCase().includes(search.toLowerCase())
      ).slice(0, 30)
    : allStocks.slice(0, 50); // show first 50 when no search

  // Determine what to display
  let displayList;
  if (search.length === 0) {
    displayList = allStocks.slice(0, 50); // show NIFTY 50 or first 50
  } else if (searchResults.length > 0) {
    // Merge API results with local filter, dedup by symbol
    const seen = new Set();
    displayList = [];
    for (const item of [...searchResults, ...localFiltered]) {
      if (!seen.has(item.symbol)) {
        seen.add(item.symbol);
        displayList.push(item);
      }
    }
  } else {
    displayList = localFiltered;
  }
  const isSearchMode = search.length >= 2;

  const current = NIFTY_50.find((s) => s.symbol === selectedStock);

  // Debounced API search
  const searchAPI = useCallback((query) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (query.length < 2) {
      setSearchResults([]);
      setSearching(false);
      setSearchError(false);
      return;
    }

    setSearching(true);
    setSearchError(false);

    debounceRef.current = setTimeout(() => {
      axios
        .get(`${API_BASE}/stocks/search`, { params: { q: query } })
        .then((res) => {
          const raw = res.data?.results || res.data || [];
          const results = (Array.isArray(raw) ? raw : []).map((item) => {
            if (typeof item === 'string') return { symbol: item, name: '' };
            return { symbol: item.symbol, name: item.name || '' };
          });
          setSearchResults(results);
          setSearching(false);
        })
        .catch(() => {
          // Fallback: filter NIFTY 50 locally if API fails
          const fallback = NIFTY_50.filter(s =>
            s.symbol.toLowerCase().includes(query.toLowerCase()) ||
            s.name.toLowerCase().includes(query.toLowerCase())
          );
          setSearchResults(fallback);
          setSearching(false);
          setSearchError(true);
        });
    }, 300);
  }, []);

  // Trigger search on input change
  useEffect(() => {
    searchAPI(search);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search, searchAPI]);

  const buttonRef = useRef(null);
  const panelRef = useRef(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });

  // Position dropdown using button bounding rect
  useEffect(() => {
    if (open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + 6,
        left: Math.max(8, rect.right - 320),
      });
    }
  }, [open]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target) &&
        panelRef.current && !panelRef.current.contains(e.target)
      ) {
        setOpen(false);
        setSearch('');
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const dropdownContent = open ? (
    <div
      ref={panelRef}
      className="w-80 bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden"
      style={{
        position: 'fixed',
        top: dropdownPos.top,
        left: dropdownPos.left,
        zIndex: 99999,
        boxShadow: '0 12px 48px rgba(0, 0, 0, 0.6), 0 4px 12px rgba(0, 0, 0, 0.4)',
      }}
    >
          {/* Search input */}
          <div className="p-2.5 border-b border-[#1f2937]">
            <div className="flex items-center gap-2 px-2.5 py-2 bg-[#0c1220] rounded-md border border-[#1f2937]">
              {searching ? (
                <Loader2 className="w-3.5 h-3.5 text-[#3b82f6] flex-shrink-0 animate-spin" />
              ) : (
                <Search className="w-3.5 h-3.5 text-[#475569] flex-shrink-0" />
              )}
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search 2000+ NSE stocks..."
                className="bg-transparent text-[#f1f5f9] text-xs outline-none w-full placeholder:text-[#475569]"
              />
            </div>
          </div>

          {/* Section label */}
          <div className="px-3.5 py-1.5 border-b border-[#1f2937]/50">
            <span className="text-[9px] uppercase tracking-widest text-[#64748b] font-medium">
              {searching
                ? 'Searching...'
                : search.length === 0
                  ? (allLoaded ? `All NSE Stocks (${allStocks.length})` : 'NIFTY 50')
                  : `${displayList.length} result${displayList.length !== 1 ? 's' : ''}`}
            </span>
          </div>

          {/* Stock list */}
          <div className="max-h-64 overflow-y-auto">
            {searching ? (
              <div className="px-3 py-6 text-center">
                <Loader2 className="w-5 h-5 text-[#3b82f6] animate-spin mx-auto mb-2" />
                <span className="text-[#64748b] text-xs">Searching...</span>
              </div>
            ) : displayList.length === 0 ? (
              <div className="px-3 py-6 text-center text-[#475569] text-xs">
                {isSearchMode
                  ? 'No stocks found. Try a different symbol.'
                  : 'No stocks found'}
              </div>
            ) : (
              displayList.map((stock) => {
                const isActive = stock.symbol === selectedStock;
                return (
                  <button
                    key={stock.symbol}
                    onClick={() => {
                      setSelectedStock(stock.symbol);
                      setOpen(false);
                      setSearch('');
                    }}
                    className={`w-full flex items-center gap-3 px-3.5 py-2.5 text-left transition-colors
                      ${isActive
                        ? 'bg-blue-500/5 border-l-2 border-l-[#3b82f6]'
                        : 'border-l-2 border-l-transparent hover:bg-white/[0.03]'
                      }`}
                  >
                    <span
                      className={`text-sm font-medium min-w-[100px] ${
                        isActive ? 'text-[#3b82f6]' : 'text-[#f1f5f9]'
                      }`}
                    >
                      {stock.symbol}
                    </span>
                    <span className="text-xs text-[#64748b] truncate">
                      {stock.name}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
  ) : null;

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        ref={buttonRef}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#111827] border border-[#1f2937] rounded-lg
                   hover:border-[#374151] transition-colors min-w-[260px]"
      >
        <span className="text-[#3b82f6] font-semibold text-sm">
          {selectedStock}
        </span>
        {current && (
          <span className="text-[#64748b] text-xs truncate">
            {current.name}
          </span>
        )}
        <ChevronDown
          className={`w-4 h-4 text-[#475569] ml-auto transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>
      {createPortal(dropdownContent, document.body)}
    </div>
  );
}

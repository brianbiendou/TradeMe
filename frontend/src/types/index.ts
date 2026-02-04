// Types pour l'application TradeMe

export interface Agent {
  id: string;
  name: string;
  model: string;
  personality: string;
  initial_capital: number;
  current_capital: number;
  total_pnl: number;
  total_trades: number;
  win_rate: number;
  positions: Position[];
}

export interface Trade {
  id?: string;
  agent_id: string;
  decision: 'BUY' | 'SELL' | 'HOLD';
  symbol?: string;
  quantity?: number;
  price?: number;
  reasoning: string;
  confidence: number;
  timestamp: string;
  executed: boolean;
  pnl: number;
}

export interface Autocritique {
  agent_id: string;
  analysis: string;
  strengths: string[];
  improvements: string[];
  score: number;
  created_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  name: string;
  model: string;
  initial_capital: number;
  current_capital: number;
  performance_pct: number;
  total_profit: number;
  total_fees: number;
  trade_count: number;
  win_rate: number;
}

export interface MarketData {
  symbol: string;
  price: number;
  change_pct: number;
  volume: number;
}

export interface MarketHours {
  is_open: boolean;
  timestamp: string;
  next_open: string;
  next_close: string;
}

export interface Account {
  id: string;
  status: string;
  currency: string;
  cash: number;
  portfolio_value: number;
  buying_power: number;
  equity: number;
}

export interface Position {
  symbol: string;
  qty: number;
  market_value: number;
  cost_basis: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  current_price: number;
  avg_entry_price: number;
}

export interface Movers {
  gainers: MarketData[];
  losers: MarketData[];
  high_volume: MarketData[];
}

export type TimeFilter = '1h' | '24h' | '7d' | '30d' | '3m' | '6m' | '1y' | '5y';
export type TimeFilterOption = TimeFilter;

export interface PerformancePoint {
  timestamp: string;
  value: number;
  agent: string;
}

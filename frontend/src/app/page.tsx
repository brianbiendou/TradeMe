'use client';

import { useState, useEffect, useCallback } from 'react';
import AgentCard from '@/components/agents/AgentCard';
import TradingChart from '@/components/charts/TradingChart';
import TimeFilter from '@/components/ui/TimeFilter';
import Leaderboard from '@/components/leaderboard/Leaderboard';
import { api, Agent, TradingStatus, MarketHours, PerformanceData } from '@/lib/api';
import { wsClient, WSMessage } from '@/lib/websocket';
import { TimeFilterOption } from '@/types';
import { Activity, TrendingUp, DollarSign, Zap, Power, RefreshCw } from 'lucide-react';

export default function DashboardPage() {
  const [timeFilter, setTimeFilter] = useState<TimeFilterOption>('1h');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tradingStatus, setTradingStatus] = useState<TradingStatus | null>(null);
  const [marketHours, setMarketHours] = useState<MarketHours | null>(null);
  const [performanceData, setPerformanceData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Charger les données
  const fetchData = useCallback(async () => {
    try {
      const [agentsData, statusData, hoursData, perfData] = await Promise.all([
        api.getLeaderboard(),
        api.getTradingStatus(),
        api.getMarketHours(),
        api.getPerformance(timeFilter),
      ]);
      
      setAgents(agentsData);
      setTradingStatus(statusData);
      setMarketHours(hoursData);
      setPerformanceData(perfData);
      setError(null);
    } catch (err) {
      setError('Erreur de connexion au backend');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [timeFilter]);

  // Effet initial
  useEffect(() => {
    fetchData();

    // Connecter WebSocket
    wsClient.connect().catch(console.error);

    // Écouter les mises à jour
    const handleMessage = (msg: WSMessage) => {
      if (msg.type === 'refresh' || msg.type === 'initial_state') {
        if (msg.leaderboard) setAgents(msg.leaderboard);
        if (msg.trading_status) setTradingStatus(prev => ({ ...prev!, ...msg.trading_status }));
      }
      if (msg.type === 'trading_enabled' || msg.type === 'trading_disabled') {
        fetchData();
      }
      if (msg.type === 'trading_cycle') {
        fetchData();
      }
    };

    wsClient.on('*', handleMessage);

    // Rafraîchir toutes les 30 secondes
    const interval = setInterval(fetchData, 30000);

    return () => {
      wsClient.off('*', handleMessage);
      clearInterval(interval);
    };
  }, [fetchData]);

  // Toggle trading
  const handleToggleTrading = async () => {
    if (!tradingStatus) return;
    
    setToggling(true);
    try {
      const newStatus = await api.toggleTrading(!tradingStatus.active);
      setTradingStatus(newStatus);
    } catch (err) {
      console.error('Erreur toggle trading:', err);
    } finally {
      setToggling(false);
    }
  };

  // Calculs globaux
  const totalCapital = agents.reduce((sum, a) => sum + (a.current_capital || 0), 0);
  const totalPnL = agents.reduce((sum, a) => sum + (a.total_profit || 0), 0);
  const avgWinRate = agents.length > 0 
    ? agents.reduce((sum, a) => sum + (a.win_rate || 0), 0) / agents.length 
    : 0;
  const totalTrades = agents.reduce((sum, a) => sum + (a.trade_count || 0), 0);

  // Transformer les données de performance pour le graphe
  const chartData = performanceData?.data 
    ? Object.entries(performanceData.data).flatMap(([agent, points]) =>
        points.map(p => ({
          timestamp: p.time,
          agent,
          value: p.performance,
        }))
      )
    : [];

  if (loading) {
    return (
      <div className="p-8 bg-white min-h-screen flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Chargement des données...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 bg-white min-h-screen">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Vue d'ensemble des performances de trading</p>
        </div>

        {/* Bouton ON/OFF Trading */}
        <button
          onClick={handleToggleTrading}
          disabled={toggling}
          className={`flex items-center space-x-3 px-6 py-3 rounded-xl font-semibold transition-all ${
            tradingStatus?.active
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-green-500 hover:bg-green-600 text-white'
          } ${toggling ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <Power className={`w-5 h-5 ${tradingStatus?.active ? 'animate-pulse' : ''}`} />
          <span>{tradingStatus?.active ? 'Arrêter Trading' : 'Démarrer Trading'}</span>
        </button>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Status du marché & Trading */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Statut Marché */}
        <div className={`p-4 rounded-lg flex items-center justify-between ${
          marketHours?.is_open 
            ? 'bg-green-50 border border-green-200' 
            : 'bg-gray-100 border border-gray-200'
        }`}>
          <div className="flex items-center space-x-3">
            <div className={`w-3 h-3 rounded-full ${
              marketHours?.is_open ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
            }`} />
            <span className={`font-medium ${
              marketHours?.is_open ? 'text-green-700' : 'text-gray-600'
            }`}>
              {marketHours?.is_open ? 'Marché ouvert' : 'Marché fermé'}
            </span>
          </div>
        </div>

        {/* Statut Trading */}
        <div className={`p-4 rounded-lg flex items-center justify-between ${
          tradingStatus?.active 
            ? 'bg-blue-50 border border-blue-200' 
            : 'bg-gray-100 border border-gray-200'
        }`}>
          <div className="flex items-center space-x-3">
            <div className={`w-3 h-3 rounded-full ${
              tradingStatus?.active ? 'bg-blue-500 animate-pulse' : 'bg-gray-400'
            }`} />
            <span className={`font-medium ${
              tradingStatus?.active ? 'text-blue-700' : 'text-gray-600'
            }`}>
              {tradingStatus?.active ? 'Trading ACTIF' : 'Trading INACTIF'}
            </span>
          </div>
          <span className="text-sm text-gray-500">
            {tradingStatus?.total_trades || 0} trades cette session
          </span>
        </div>
      </div>

      {/* KPIs globaux */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Capital Total</p>
              <p className="text-2xl font-bold text-gray-900">
                ${totalCapital.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <DollarSign className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">P&L Total</p>
              <p className={`text-2xl font-bold ${totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {totalPnL >= 0 ? '+' : ''}${totalPnL.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
              totalPnL >= 0 ? 'bg-green-100' : 'bg-red-100'
            }`}>
              <TrendingUp className={`w-6 h-6 ${totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`} />
            </div>
          </div>
        </div>

        <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Win Rate Moyen</p>
              <p className="text-2xl font-bold text-gray-900">{avgWinRate.toFixed(1)}%</p>
            </div>
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <Activity className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>

        <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Trades</p>
              <p className="text-2xl font-bold text-gray-900">{totalTrades}</p>
            </div>
            <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
              <Zap className="w-6 h-6 text-amber-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Agents Cards */}
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Agents IA</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
        {agents.map((agent) => (
          <AgentCard key={agent.id || agent.name} agent={agent} />
        ))}
      </div>

      {/* Chart + Leaderboard */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Performance Chart - Style TradingView */}
        <div className="xl:col-span-2 rounded-xl shadow-sm overflow-hidden">
          <div className="bg-gray-900 px-6 py-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">Performance en temps réel</h2>
            <TimeFilter value={timeFilter} onChange={setTimeFilter} dark />
          </div>
          {performanceData?.data && (
            <TradingChart 
              performanceData={performanceData.data} 
              height={350}
            />
          )}
        </div>

        {/* Leaderboard */}
        <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Classement</h2>
          <Leaderboard entries={agents.map((a, i) => ({
            rank: i + 1,
            name: a.name,
            model: a.model,
            initial_capital: a.initial_capital,
            current_capital: a.current_capital,
            performance_pct: a.performance_pct,
            total_profit: a.total_profit,
            total_fees: a.total_fees,
            trade_count: a.trade_count,
            win_rate: a.win_rate,
          }))} />
        </div>
      </div>
    </div>
  );
}

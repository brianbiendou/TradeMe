'use client';

import { useState, useEffect } from 'react';
import Leaderboard from '@/components/leaderboard/Leaderboard';
import { api, Agent } from '@/lib/api';
import { Trophy, Medal, TrendingUp, Target, RefreshCw } from 'lucide-react';

export default function LeaderboardPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await api.getLeaderboard();
        setAgents(data);
      } catch (err) {
        console.error('Erreur fetch leaderboard:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="p-8 bg-white min-h-screen flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  // Trouver le meilleur agent
  const bestAgent = agents.length > 0 
    ? agents.reduce((best, current) => 
        current.total_profit > best.total_profit ? current : best
      )
    : null;

  // Stats du leaderboard
  const avgPerformance = agents.length > 0 
    ? agents.reduce((sum, e) => sum + e.performance_pct, 0) / agents.length 
    : 0;
  const totalCapital = agents.reduce((sum, e) => sum + e.current_capital, 0);

  // Convertir pour le composant Leaderboard
  const leaderboardEntries = agents.map(a => ({
    agent_name: a.name,
    performance_pct: a.performance_pct,
    current_capital: a.current_capital,
    total_pnl: a.total_profit,
    trade_count: a.trade_count,
    win_rate: a.win_rate,
  }));

  return (
    <div className="p-8 bg-white min-h-screen">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center space-x-3 mb-2">
          <Trophy className="w-8 h-8 text-yellow-500" />
          <h1 className="text-3xl font-bold text-gray-900">Classement</h1>
        </div>
        <p className="text-gray-500">Performance comparative des agents</p>
      </div>

      {/* Champion Card */}
      {bestAgent && (
        <div className="bg-gradient-to-r from-yellow-400 via-yellow-500 to-amber-500 rounded-2xl shadow-lg p-8 mb-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center space-x-2 mb-2">
                <Medal className="w-6 h-6" />
                <span className="text-yellow-100 font-medium">Champion actuel</span>
              </div>
              <h2 className="text-4xl font-bold mb-2">{bestAgent.name}</h2>
              <p className="text-yellow-100">{bestAgent.personality || 'Agent IA'}</p>
            </div>
            <div className="text-right">
              <p className="text-5xl font-bold">
                {bestAgent.performance_pct >= 0 ? '+' : ''}{bestAgent.performance_pct.toFixed(2)}%
              </p>
              <p className="text-yellow-100 mt-2">
                P&L: {bestAgent.total_profit >= 0 ? '+' : ''}${bestAgent.total_profit.toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stats globales */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Performance moyenne</p>
              <p className={`text-xl font-bold ${avgPerformance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {avgPerformance >= 0 ? '+' : ''}{avgPerformance.toFixed(2)}%
              </p>
            </div>
          </div>
        </div>

        <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Target className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Capital total géré</p>
              <p className="text-xl font-bold text-gray-900">
                ${totalCapital.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Trophy className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Agents en compétition</p>
              <p className="text-xl font-bold text-gray-900">{agents.length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Leaderboard complet */}
      <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">Classement complet</h2>
        <Leaderboard entries={leaderboardEntries} />
      </div>
    </div>
  );
}

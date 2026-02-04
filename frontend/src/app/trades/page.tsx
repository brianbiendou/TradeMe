'use client';

import { useState, useEffect, useCallback } from 'react';
import TradesTable from '@/components/trades/TradesTable';
import { api, Trade, Agent } from '@/lib/api';
import { ArrowRightLeft, Filter, RefreshCw } from 'lucide-react';

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentFilter, setAgentFilter] = useState<string>('all');
  const [decisionFilter, setDecisionFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [tradesData, agentsData] = await Promise.all([
        api.getTrades(100, agentFilter !== 'all' ? agentFilter : undefined),
        api.getAgents(),
      ]);
      setTrades(tradesData);
      setAgents(agentsData);
    } catch (err) {
      console.error('Erreur chargement trades:', err);
    } finally {
      setLoading(false);
    }
  }, [agentFilter]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  let filteredTrades = [...trades];
  
  if (decisionFilter !== 'all') {
    filteredTrades = filteredTrades.filter(t => t.decision === decisionFilter);
  }

  // Stats rapides
  const buyCount = trades.filter(t => t.decision === 'BUY').length;
  const sellCount = trades.filter(t => t.decision === 'SELL').length;
  const totalPnL = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);

  if (loading) {
    return (
      <div className="p-8 bg-white min-h-screen flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Chargement des trades...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 bg-white min-h-screen">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center space-x-3 mb-2">
          <ArrowRightLeft className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">Trades</h1>
        </div>
        <p className="text-gray-500">Historique complet des transactions (données réelles)</p>
      </div>

      {/* Stats rapides */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-50 rounded-lg shadow-sm p-4 border border-gray-100">
          <p className="text-sm text-gray-500">Total Trades</p>
          <p className="text-2xl font-bold text-gray-900">{trades.length}</p>
        </div>
        <div className="bg-green-50 rounded-lg shadow-sm p-4 border border-green-100">
          <p className="text-sm text-green-600">Achats (BUY)</p>
          <p className="text-2xl font-bold text-green-700">{buyCount}</p>
        </div>
        <div className="bg-red-50 rounded-lg shadow-sm p-4 border border-red-100">
          <p className="text-sm text-red-600">Ventes (SELL)</p>
          <p className="text-2xl font-bold text-red-700">{sellCount}</p>
        </div>
        <div className="bg-gray-50 rounded-lg shadow-sm p-4 border border-gray-100">
          <p className="text-sm text-gray-500">P&L Total</p>
          <p className={`text-2xl font-bold ${totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Filtres */}
      <div className="bg-gray-50 rounded-xl shadow-sm p-4 mb-6 border border-gray-100">
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-medium text-gray-700">Filtres:</span>
          </div>
          
          <div className="flex items-center space-x-2">
            <label className="text-sm text-gray-600">Agent:</label>
            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">Tous les agents</option>
              {agents.map((agent) => (
                <option key={agent.id || agent.name} value={agent.name}>{agent.name}</option>
              ))}
            </select>
          </div>
          
          <div className="flex items-center space-x-2">
            <label className="text-sm text-gray-600">Décision:</label>
            <select
              value={decisionFilter}
              onChange={(e) => setDecisionFilter(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">Toutes</option>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
              <option value="HOLD">HOLD</option>
            </select>
          </div>

          {(agentFilter !== 'all' || decisionFilter !== 'all') && (
            <button
              onClick={() => {
                setAgentFilter('all');
                setDecisionFilter('all');
              }}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              Réinitialiser
            </button>
          )}

          <button
            onClick={fetchData}
            className="ml-auto flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-800"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Actualiser</span>
          </button>
        </div>
      </div>

      {/* Table des trades */}
      {filteredTrades.length === 0 ? (
        <div className="bg-gray-50 rounded-xl p-12 text-center">
          <ArrowRightLeft className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">Aucun trade pour le moment</p>
          <p className="text-sm text-gray-400 mt-1">Les trades apparaîtront ici une fois le trading activé</p>
        </div>
      ) : (
        <TradesTable trades={filteredTrades.map(t => ({
          agent_id: t.agent_name || t.agent_id || '',
          decision: t.decision,
          symbol: t.symbol,
          quantity: t.quantity,
          price: t.price,
          reasoning: t.reasoning,
          confidence: t.confidence,
          timestamp: t.created_at,
          executed: t.executed,
          pnl: t.pnl || 0,
        }))} />
      )}
    </div>
  );
}

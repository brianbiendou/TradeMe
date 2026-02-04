'use client';

import { useState, useEffect, useCallback } from 'react';
import AgentCard from '@/components/agents/AgentCard';
import TradesTable from '@/components/trades/TradesTable';
import { api, Agent, Trade } from '@/lib/api';
import { Bot, Filter, RefreshCw } from 'lucide-react';

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [agentsData, tradesData] = await Promise.all([
        api.getAgents(),
        api.getTrades(100, selectedAgent || undefined),
      ]);
      setAgents(agentsData);
      setTrades(tradesData);
    } catch (err) {
      console.error('Erreur chargement agents:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedAgent]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const filteredTrades = selectedAgent
    ? trades.filter((t) => t.agent_name === selectedAgent)
    : trades;

  if (loading) {
    return (
      <div className="p-8 bg-white min-h-screen flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Chargement des agents...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 bg-white min-h-screen">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3 mb-2">
            <Bot className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-gray-900">Agents IA</h1>
          </div>
          <button
            onClick={fetchData}
            className="flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-800"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Actualiser</span>
          </button>
        </div>
        <p className="text-gray-500">Détails et performance de chaque agent (données réelles)</p>
      </div>

      {/* Agents Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
        {agents.map((agent) => (
          <div
            key={agent.id || agent.name}
            onClick={() => setSelectedAgent(
              selectedAgent === agent.name ? null : agent.name
            )}
            className={`cursor-pointer transition-transform ${
              selectedAgent === agent.name ? 'ring-2 ring-blue-500 rounded-xl' : ''
            }`}
          >
            <AgentCard agent={{
              id: agent.id || agent.name,
              name: agent.name,
              model: agent.model || 'N/A',
              personality: '',
              initial_capital: agent.initial_capital || 10000,
              current_capital: agent.current_capital,
              total_pnl: agent.current_capital - (agent.initial_capital || 10000),
              total_trades: agent.trade_count || 0,
              win_rate: agent.win_rate || 0,
              positions: [],
            }} />
          </div>
        ))}
      </div>

      {/* Filter indicator */}
      {selectedAgent && (
        <div className="mb-4 flex items-center space-x-2 text-sm text-gray-600">
          <Filter className="w-4 h-4" />
          <span>
            Filtré par: <strong>{selectedAgent}</strong>
          </span>
          <button
            onClick={() => setSelectedAgent(null)}
            className="text-blue-600 hover:underline"
          >
            Effacer
          </button>
        </div>
      )}

      {/* Trades Table */}
      <div className="bg-gray-50 rounded-xl shadow-sm border border-gray-100">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">
            Historique des Trades {selectedAgent && `- ${selectedAgent}`}
          </h2>
        </div>
        {filteredTrades.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">Aucun trade pour le moment</p>
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
    </div>
  );
}

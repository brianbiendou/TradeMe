'use client';

import { Agent } from '@/types';
import { TrendingUp, TrendingDown, DollarSign, Activity, Target } from 'lucide-react';

interface AgentCardProps {
  agent: Agent;
  gradient?: string;
}

export default function AgentCard({ agent, gradient }: AgentCardProps) {
  const totalPnl = agent.total_pnl ?? (agent.current_capital - agent.initial_capital) ?? 0;
  const isPositive = totalPnl >= 0;
  const performancePct = agent.initial_capital > 0 
    ? ((agent.current_capital - agent.initial_capital) / agent.initial_capital) * 100 
    : 0;
  
  // Déterminer le gradient selon l'agent
  const getGradient = () => {
    const name = agent.name.toLowerCase();
    if (name === 'grok') return 'gradient-grok';
    if (name === 'deepseek') return 'gradient-deepseek';
    if (name === 'gpt') return 'gradient-gpt';
    if (name === 'consortium') return 'gradient-consortium';
    return 'bg-gray-600';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden card-hover">
      {/* Header avec gradient */}
      <div className={`${gradient || getGradient()} px-6 py-4`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-white">{agent.name}</h3>
            <p className="text-sm text-white/80">{agent.model.split('/').pop()}</p>
          </div>
          <div className={`flex items-center px-3 py-1 rounded-full ${
            isPositive ? 'bg-white/20' : 'bg-red-500/30'
          }`}>
            {isPositive ? (
              <TrendingUp className="w-4 h-4 text-white mr-1" />
            ) : (
              <TrendingDown className="w-4 h-4 text-white mr-1" />
            )}
            <span className="text-sm font-bold text-white">
              {isPositive ? '+' : ''}{performancePct.toFixed(2)}%
            </span>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="p-6">
        <div className="grid grid-cols-2 gap-4">
          {/* Capital actuel */}
          <div className="flex items-start space-x-3">
            <div className="p-2 bg-primary-50 rounded-lg">
              <DollarSign className="w-4 h-4 text-primary-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500">Capital</p>
              <p className="text-lg font-semibold text-gray-900">
                ${agent.current_capital.toFixed(2)}
              </p>
            </div>
          </div>

          {/* Profit/Perte */}
          <div className="flex items-start space-x-3">
            <div className={`p-2 rounded-lg ${
              isPositive ? 'bg-success-50' : 'bg-danger-50'
            }`}>
              {isPositive ? (
                <TrendingUp className="w-4 h-4 text-success-600" />
              ) : (
                <TrendingDown className="w-4 h-4 text-danger-600" />
              )}
            </div>
            <div>
              <p className="text-xs text-gray-500">P&L</p>
              <p className={`text-lg font-semibold ${
                isPositive ? 'text-success-600' : 'text-danger-600'
              }`}>
                {isPositive ? '+' : ''}${totalPnl.toFixed(2)}
              </p>
            </div>
          </div>

          {/* Trades */}
          <div className="flex items-start space-x-3">
            <div className="p-2 bg-gray-100 rounded-lg">
              <Activity className="w-4 h-4 text-gray-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500">Trades</p>
              <p className="text-lg font-semibold text-gray-900">
                {agent.total_trades ?? 0}
              </p>
            </div>
          </div>

          {/* Win Rate */}
          <div className="flex items-start space-x-3">
            <div className="p-2 bg-warning-50 rounded-lg">
              <Target className="w-4 h-4 text-warning-500" />
            </div>
            <div>
              <p className="text-xs text-gray-500">Win Rate</p>
              <p className="text-lg font-semibold text-gray-900">
                {(agent.win_rate ?? 0).toFixed(1)}%
              </p>
            </div>
          </div>
        </div>

        {/* Positions */}
        {agent.positions && agent.positions.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-500 mb-2">Positions ouvertes</p>
            <div className="flex flex-wrap gap-2">
              {agent.positions.map((pos) => (
                <span
                  key={pos.symbol}
                  className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded-md ${
                    pos.unrealized_pl >= 0 
                      ? 'bg-success-50 text-success-700' 
                      : 'bg-danger-50 text-danger-700'
                  }`}
                >
                  {pos.symbol}: {pos.qty} @ ${pos.avg_entry_price.toFixed(2)}
                  <span className="ml-1">
                    ({pos.unrealized_pl >= 0 ? '+' : ''}{pos.unrealized_plpc.toFixed(1)}%)
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

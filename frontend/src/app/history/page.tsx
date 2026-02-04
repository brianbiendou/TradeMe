'use client';

import { useState, useEffect, useCallback } from 'react';
import PerformanceChart from '@/components/charts/PerformanceChart';
import TimeFilter from '@/components/ui/TimeFilter';
import { api, Agent, PerformanceData, Autocritique } from '@/lib/api';
import { TimeFilterOption } from '@/types';
import { History, Brain, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';

export default function HistoryPage() {
  const [timeFilter, setTimeFilter] = useState<TimeFilterOption>('24h');
  const [performance, setPerformance] = useState<PerformanceData[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [autocritiques, setAutocritiques] = useState<Autocritique[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [perfData, agentsData, autocritData] = await Promise.all([
        api.getPerformance(timeFilter),
        api.getAgents(),
        api.getAutocritiques(20),
      ]);
      setPerformance(perfData);
      setAgents(agentsData);
      setAutocritiques(autocritData);
    } catch (err) {
      console.error('Erreur chargement historique:', err);
    } finally {
      setLoading(false);
    }
  }, [timeFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getAgentName = (agentId: string) => {
    const agent = agents.find(a => a.id === agentId || a.name === agentId);
    return agent?.name || agentId;
  };

  const getAgentColor = (name: string) => {
    if (name.toLowerCase().includes('grok')) return { bg: 'bg-purple-100', text: 'text-purple-600' };
    if (name.toLowerCase().includes('deepseek')) return { bg: 'bg-pink-100', text: 'text-pink-600' };
    if (name.toLowerCase().includes('gpt')) return { bg: 'bg-blue-100', text: 'text-blue-600' };
    return { bg: 'bg-green-100', text: 'text-green-600' };
  };

  if (loading) {
    return (
      <div className="p-8 bg-white min-h-screen flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Chargement de l'historique...</p>
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
            <History className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-gray-900">Historique</h1>
          </div>
          <button
            onClick={fetchData}
            className="flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-800"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Actualiser</span>
          </button>
        </div>
        <p className="text-gray-500">Évolution des performances et autocritiques (données réelles)</p>
      </div>

      {/* Graphique de performance étendu */}
      <div className="bg-gray-50 rounded-xl shadow-sm p-6 mb-8 border border-gray-100">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">
            Évolution du capital
          </h2>
          <TimeFilter value={timeFilter} onChange={setTimeFilter} />
        </div>
        <div className="h-96">
          {performance.length > 0 ? (
            <PerformanceChart data={performance} timeFilter={timeFilter} />
          ) : (
            <div className="h-full flex items-center justify-center">
              <p className="text-gray-500">Aucune donnée de performance disponible</p>
            </div>
          )}
        </div>
      </div>

      {/* Autocritiques */}
      <div className="bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-100">
        <div className="flex items-center space-x-2 mb-6">
          <Brain className="w-5 h-5 text-purple-600" />
          <h2 className="text-xl font-semibold text-gray-900">Autocritiques des agents</h2>
        </div>
        
        {autocritiques.length === 0 ? (
          <div className="text-center py-12">
            <Brain className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">Aucune autocritique pour le moment</p>
            <p className="text-sm text-gray-400 mt-1">
              Les autocritiques seront générées après les premières sessions de trading
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {autocritiques.map((critique, index) => {
              const agentName = getAgentName(critique.agent_id);
              const colors = getAgentColor(agentName);
              
              return (
                <div
                  key={index}
                  className="bg-white border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colors.bg}`}>
                        <Brain className={`w-5 h-5 ${colors.text}`} />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900">{agentName}</h3>
                        <p className="text-sm text-gray-500">
                          {format(parseISO(critique.created_at), 'dd MMM yyyy HH:mm', { locale: fr })}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-gray-500">Score:</span>
                      <span className={`px-2 py-1 rounded-full text-sm font-medium ${
                        critique.score >= 7 ? 'bg-green-100 text-green-700' :
                        critique.score >= 4 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {critique.score}/10
                      </span>
                    </div>
                  </div>

                  <p className="text-gray-700 mb-4">{critique.analysis}</p>

                  {/* Points forts */}
                  {critique.strengths && critique.strengths.length > 0 && (
                    <div className="mb-3">
                      <h4 className="text-sm font-medium text-green-700 mb-2 flex items-center">
                        <CheckCircle className="w-4 h-4 mr-1" />
                        Points forts
                      </h4>
                      <ul className="space-y-1">
                        {critique.strengths.map((s, i) => (
                          <li key={i} className="text-sm text-gray-600 pl-5">• {s}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Points à améliorer */}
                  {critique.improvements && critique.improvements.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-red-700 mb-2 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" />
                        Points à améliorer
                      </h4>
                      <ul className="space-y-1">
                        {critique.improvements.map((w, i) => (
                          <li key={i} className="text-sm text-gray-600 pl-5">• {w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

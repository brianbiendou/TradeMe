'use client';

import { useState, useEffect } from 'react';
import {
  Eye,
  Brain,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Clock,
  Lightbulb,
  Target,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Zap,
  Search,
  Filter,
} from 'lucide-react';

interface WatchReport {
  id: string;
  agent_name: string;
  report_type: string;
  market_status: string;
  analysis_summary: string;
  key_insights: string[];
  opportunities: Opportunity[];
  risks: string[];
  watchlist: WatchlistItem[];
  planned_actions: PlannedAction[];
  confidence_level: number;
  questions_asked: string[];
  answers: Answer[];
  created_at: string;
  processing_time_ms: number;
}

interface Opportunity {
  symbol: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  opportunity_type: string;
  reasoning: string;
  entry_price?: number;
  target_price?: number;
  stop_loss?: number;
  confidence: number;
  timeframe?: string;
}

interface WatchlistItem {
  symbol: string;
  reason: string;
}

interface PlannedAction {
  action: string;
  symbol: string;
  condition: string;
  size_pct?: number;
  priority?: number;
}

interface Answer {
  question: string;
  answer: string;
}

interface PositionReview {
  id: string;
  symbol: string;
  position_type: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  decision: string;
  new_stop_loss?: number;
  new_target?: number;
  reasoning: string;
  confidence: number;
  created_at: string;
}

const agentColors: Record<string, string> = {
  Grok: 'from-orange-500 to-red-500',
  DeepSeek: 'from-blue-500 to-cyan-500',
  GPT: 'from-green-500 to-emerald-500',
  Consortium: 'from-purple-500 to-pink-500',
};

const agentBgColors: Record<string, string> = {
  Grok: 'bg-orange-50 border-orange-200',
  DeepSeek: 'bg-blue-50 border-blue-200',
  GPT: 'bg-green-50 border-green-200',
  Consortium: 'bg-purple-50 border-purple-200',
};

const agentEmojis: Record<string, string> = {
  Grok: '🔥',
  DeepSeek: '🔍',
  GPT: '🧠',
  Consortium: '🤝',
};

export default function VeillePage() {
  const [reports, setReports] = useState<WatchReport[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [positionReviews, setPositionReviews] = useState<PositionReview[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('all');
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningWatch, setRunningWatch] = useState(false);
  const [activeTab, setActiveTab] = useState<'reports' | 'opportunities' | 'reviews'>('reports');
  const [tokenUsage, setTokenUsage] = useState<{
    tokens: { prompt: number; completion: number; total: number };
    cost_usd: number;
    budget_usd: number;
    budget_used_pct: number;
  } | null>(null);

  const fetchTokenUsage = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/watch/usage');
      if (res.ok) {
        const data = await res.json();
        setTokenUsage(data.usage);
      }
    } catch (error) {
      console.error('Erreur fetch token usage:', error);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      // Construire les paramètres correctement
      const buildUrl = (base: string, params: Record<string, string | number>) => {
        const query = Object.entries(params)
          .filter(([_, v]) => v !== undefined && v !== null && v !== '')
          .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
          .join('&');
        return query ? `${base}?${query}` : base;
      };
      
      const agentFilter = selectedAgent !== 'all' ? selectedAgent : '';
      
      const [reportsRes, oppsRes, reviewsRes] = await Promise.all([
        fetch(buildUrl('http://localhost:8000/api/watch/reports', { agent: agentFilter, limit: 20 })),
        fetch(buildUrl('http://localhost:8000/api/watch/opportunities', { agent: agentFilter })),
        fetch(buildUrl('http://localhost:8000/api/watch/position-reviews', { agent: agentFilter, limit: 50 })),
      ]);

      if (reportsRes.ok) {
        const data = await reportsRes.json();
        setReports(data.reports || []);
      }

      if (oppsRes.ok) {
        const data = await oppsRes.json();
        setOpportunities(data.opportunities || []);
      }

      if (reviewsRes.ok) {
        const data = await reviewsRes.json();
        setPositionReviews(data.reviews || []);
      }
    } catch (error) {
      console.error('Erreur fetch veille:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    fetchTokenUsage();
    const interval = setInterval(fetchData, 60000); // Refresh toutes les minutes
    const usageInterval = setInterval(fetchTokenUsage, 30000); // Usage toutes les 30s
    return () => {
      clearInterval(interval);
      clearInterval(usageInterval);
    };
  }, [selectedAgent]);

  const triggerOptimizedWatch = async () => {
    setRunningWatch(true);
    try {
      const res = await fetch('http://localhost:8000/api/watch/optimized/run');
      if (res.ok) {
        await fetchData();
        await fetchTokenUsage();
      }
    } catch (error) {
      console.error('Erreur veille optimisée:', error);
    } finally {
      setRunningWatch(false);
    }
  };

  const triggerWatch = async (agent?: string) => {
    setRunningWatch(true);
    try {
      const url = agent 
        ? `http://localhost:8000/api/watch/run?agent=${agent}`
        : 'http://localhost:8000/api/watch/run';
      
      const res = await fetch(url, { method: 'POST' });
      if (res.ok) {
        await fetchData();
      }
    } catch (error) {
      console.error('Erreur trigger watch:', error);
    } finally {
      setRunningWatch(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getMarketStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      open: 'bg-green-100 text-green-800',
      closed: 'bg-gray-100 text-gray-800',
      pre_market: 'bg-yellow-100 text-yellow-800',
      after_hours: 'bg-blue-100 text-blue-800',
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 70) return 'text-green-600';
    if (confidence >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Token Usage Banner */}
      {tokenUsage && (
        <div className="mb-6 p-4 bg-gradient-to-r from-slate-50 to-blue-50 rounded-xl border border-slate-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div>
                <span className="text-xs text-gray-500 uppercase">Tokens Aujourd'hui</span>
                <p className="text-lg font-semibold text-gray-900">
                  {tokenUsage.tokens.total.toLocaleString()}
                </p>
              </div>
              <div>
                <span className="text-xs text-gray-500 uppercase">Coût</span>
                <p className="text-lg font-semibold text-green-600">
                  ${tokenUsage.cost_usd.toFixed(4)}
                </p>
              </div>
              <div>
                <span className="text-xs text-gray-500 uppercase">Budget</span>
                <div className="flex items-center gap-2">
                  <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all ${
                        tokenUsage.budget_used_pct > 80 ? 'bg-red-500' : 
                        tokenUsage.budget_used_pct > 50 ? 'bg-yellow-500' : 'bg-green-500'
                      }`}
                      style={{ width: `${Math.min(tokenUsage.budget_used_pct, 100)}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-600">
                    {tokenUsage.budget_used_pct.toFixed(1)}% / ${tokenUsage.budget_usd}
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={triggerOptimizedWatch}
              disabled={runningWatch}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
              title="Veille économique - ~$0.01 par exécution"
            >
              {runningWatch ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              <span>Veille Éco 💰</span>
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <Eye className="w-8 h-8 text-blue-600" />
            Veille IA
          </h1>
          <p className="text-gray-600 mt-1">
            Analyses et réflexions des agents - Préparation des trades
          </p>
        </div>

        <div className="flex items-center gap-4 mt-4 md:mt-0">
          {/* Filtre Agent */}
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-sm"
          >
            <option value="all">Tous les agents</option>
            <option value="Grok">🔥 Grok</option>
            <option value="DeepSeek">🔍 DeepSeek</option>
            <option value="GPT">🧠 GPT</option>
            <option value="Consortium">🤝 Consortium</option>
          </select>

          {/* Bouton Refresh */}
          <button
            onClick={() => fetchData()}
            disabled={loading}
            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>

          {/* Bouton Lancer Veille */}
          <button
            onClick={() => triggerWatch(selectedAgent !== 'all' ? selectedAgent : undefined)}
            disabled={runningWatch}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {runningWatch ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            <span>Lancer Veille</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('reports')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'reports'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Brain className="w-4 h-4 inline mr-2" />
          Rapports ({reports.length})
        </button>
        <button
          onClick={() => setActiveTab('opportunities')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'opportunities'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Target className="w-4 h-4 inline mr-2" />
          Opportunités ({opportunities.length})
        </button>
        <button
          onClick={() => setActiveTab('reviews')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'reviews'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Search className="w-4 h-4 inline mr-2" />
          Revues Positions ({positionReviews.length})
        </button>
      </div>

      {/* Content based on active tab */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
          <span className="ml-3 text-gray-600">Chargement des analyses...</span>
        </div>
      ) : (
        <>
          {/* Reports Tab */}
          {activeTab === 'reports' && (
            <div className="space-y-4">
              {reports.length === 0 ? (
                <div className="text-center py-20 bg-gray-50 rounded-xl">
                  <Brain className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 text-lg">Aucun rapport de veille</p>
                  <p className="text-gray-400 text-sm mt-1">
                    Cliquez sur "Lancer Veille" pour générer des analyses
                  </p>
                </div>
              ) : (
                reports.map((report) => (
                  <WatchReportCard
                    key={report.id}
                    report={report}
                    expanded={expandedReport === report.id}
                    onToggle={() =>
                      setExpandedReport(expandedReport === report.id ? null : report.id)
                    }
                  />
                ))
              )}
            </div>
          )}

          {/* Opportunities Tab */}
          {activeTab === 'opportunities' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {opportunities.length === 0 ? (
                <div className="col-span-full text-center py-20 bg-gray-50 rounded-xl">
                  <Target className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 text-lg">Aucune opportunité détectée</p>
                </div>
              ) : (
                opportunities.map((opp, index) => (
                  <OpportunityCard key={index} opportunity={opp} />
                ))
              )}
            </div>
          )}

          {/* Position Reviews Tab */}
          {activeTab === 'reviews' && (
            <div className="space-y-4">
              {positionReviews.length === 0 ? (
                <div className="text-center py-20 bg-gray-50 rounded-xl">
                  <Search className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 text-lg">Aucune revue de position</p>
                </div>
              ) : (
                positionReviews.map((review) => (
                  <PositionReviewCard key={review.id} review={review} />
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Composant pour afficher un rapport de veille
function WatchReportCard({
  report,
  expanded,
  onToggle,
}: {
  report: WatchReport;
  expanded: boolean;
  onToggle: () => void;
}) {
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className={`border rounded-xl overflow-hidden ${agentBgColors[report.agent_name] || 'bg-gray-50 border-gray-200'}`}>
      {/* Header */}
      <div
        className="p-4 cursor-pointer flex items-center justify-between"
        onClick={onToggle}
      >
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${agentColors[report.agent_name]} flex items-center justify-center text-white text-2xl`}>
            {agentEmojis[report.agent_name]}
          </div>
          <div>
            <h3 className="font-bold text-lg text-gray-900">
              {report.agent_name}
            </h3>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Clock className="w-4 h-4" />
              {formatDate(report.created_at)}
              <span className={`px-2 py-0.5 rounded-full text-xs ${
                report.market_status === 'open' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
              }`}>
                {report.market_status === 'open' ? '🟢 Marché Ouvert' : '⚫ Marché Fermé'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-sm text-gray-500">Confiance</div>
            <div className={`text-xl font-bold ${
              report.confidence_level >= 70 ? 'text-green-600' :
              report.confidence_level >= 50 ? 'text-yellow-600' : 'text-red-600'
            }`}>
              {report.confidence_level}%
            </div>
          </div>
          {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </div>
      </div>

      {/* Summary (always visible) */}
      <div className="px-4 pb-4">
        <p className="text-gray-700 line-clamp-2">{report.analysis_summary}</p>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-gray-200 bg-white p-4 space-y-6">
          {/* Key Insights */}
          {report.key_insights && report.key_insights.length > 0 && (
            <div>
              <h4 className="font-semibold text-gray-900 flex items-center gap-2 mb-3">
                <Lightbulb className="w-5 h-5 text-yellow-500" />
                Points Clés
              </h4>
              <ul className="space-y-2">
                {report.key_insights.map((insight, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-700">
                    <span className="text-blue-500 mt-1">•</span>
                    {insight}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Opportunities */}
          {report.opportunities && report.opportunities.length > 0 && (
            <div>
              <h4 className="font-semibold text-gray-900 flex items-center gap-2 mb-3">
                <Target className="w-5 h-5 text-green-500" />
                Opportunités Détectées
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {report.opportunities.map((opp, i) => (
                  <div key={i} className="bg-gray-50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold text-gray-900">{opp.symbol}</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        opp.direction === 'bullish' ? 'bg-green-100 text-green-800' :
                        opp.direction === 'bearish' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {opp.direction === 'bullish' ? '📈 Bullish' :
                         opp.direction === 'bearish' ? '📉 Bearish' : '➡️ Neutral'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{opp.reasoning}</p>
                    <div className="flex gap-4 text-xs text-gray-500">
                      {opp.entry_price && <span>Entrée: ${opp.entry_price}</span>}
                      {opp.target_price && <span>Cible: ${opp.target_price}</span>}
                      {opp.confidence && <span>Confiance: {opp.confidence}%</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Risks */}
          {report.risks && report.risks.length > 0 && (
            <div>
              <h4 className="font-semibold text-gray-900 flex items-center gap-2 mb-3">
                <AlertTriangle className="w-5 h-5 text-red-500" />
                Risques Identifiés
              </h4>
              <ul className="space-y-2">
                {report.risks.map((risk, i) => (
                  <li key={i} className="flex items-start gap-2 text-red-700 bg-red-50 p-2 rounded-lg">
                    <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    {risk}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Watchlist */}
          {report.watchlist && report.watchlist.length > 0 && (
            <div>
              <h4 className="font-semibold text-gray-900 flex items-center gap-2 mb-3">
                <Eye className="w-5 h-5 text-blue-500" />
                Watchlist
              </h4>
              <div className="flex flex-wrap gap-2">
                {report.watchlist.map((item, i) => (
                  <div key={i} className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
                    <span className="font-semibold text-blue-800">{item.symbol}</span>
                    <span className="text-blue-600 text-sm ml-2">{item.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Planned Actions */}
          {report.planned_actions && report.planned_actions.length > 0 && (
            <div>
              <h4 className="font-semibold text-gray-900 flex items-center gap-2 mb-3">
                <Zap className="w-5 h-5 text-purple-500" />
                Actions Planifiées
              </h4>
              <div className="space-y-2">
                {report.planned_actions.map((action, i) => (
                  <div key={i} className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        action.action === 'BUY' ? 'bg-green-500 text-white' :
                        action.action === 'SELL' ? 'bg-red-500 text-white' :
                        'bg-gray-500 text-white'
                      }`}>
                        {action.action}
                      </span>
                      <span className="font-semibold">{action.symbol}</span>
                      {action.priority && (
                        <span className="text-xs text-gray-500">Priorité: {action.priority}</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{action.condition}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Meta info */}
          <div className="pt-4 border-t border-gray-200 text-xs text-gray-500 flex justify-between">
            <span>Traitement: {report.processing_time_ms}ms</span>
            <span>Type: {report.report_type}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// Composant pour afficher une opportunité
function OpportunityCard({ opportunity }: { opportunity: Opportunity }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xl font-bold text-gray-900">{opportunity.symbol}</span>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
          opportunity.direction === 'bullish' ? 'bg-green-100 text-green-800' :
          opportunity.direction === 'bearish' ? 'bg-red-100 text-red-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {opportunity.direction === 'bullish' ? '📈 Bullish' :
           opportunity.direction === 'bearish' ? '📉 Bearish' : '➡️ Neutral'}
        </span>
      </div>

      <div className="mb-3">
        <span className="text-xs text-gray-500 uppercase">{opportunity.opportunity_type}</span>
        <p className="text-sm text-gray-700 mt-1">{opportunity.reasoning}</p>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        {opportunity.entry_price && (
          <div className="text-center bg-gray-50 rounded-lg p-2">
            <div className="text-xs text-gray-500">Entrée</div>
            <div className="font-semibold">${opportunity.entry_price}</div>
          </div>
        )}
        {opportunity.target_price && (
          <div className="text-center bg-green-50 rounded-lg p-2">
            <div className="text-xs text-green-600">Cible</div>
            <div className="font-semibold text-green-700">${opportunity.target_price}</div>
          </div>
        )}
        {opportunity.stop_loss && (
          <div className="text-center bg-red-50 rounded-lg p-2">
            <div className="text-xs text-red-600">Stop</div>
            <div className="font-semibold text-red-700">${opportunity.stop_loss}</div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">
          {opportunity.timeframe || 'Court terme'}
        </span>
        <span className={`font-semibold ${
          opportunity.confidence >= 70 ? 'text-green-600' :
          opportunity.confidence >= 50 ? 'text-yellow-600' : 'text-red-600'
        }`}>
          {opportunity.confidence}% confiance
        </span>
      </div>
    </div>
  );
}

// Composant pour afficher une revue de position
function PositionReviewCard({ review }: { review: PositionReview }) {
  const decisionColors: Record<string, string> = {
    hold: 'bg-blue-100 text-blue-800',
    add: 'bg-green-100 text-green-800',
    reduce: 'bg-yellow-100 text-yellow-800',
    close: 'bg-red-100 text-red-800',
    move_stop: 'bg-purple-100 text-purple-800',
  };

  const decisionLabels: Record<string, string> = {
    hold: '⏸️ Garder',
    add: '➕ Renforcer',
    reduce: '➖ Réduire',
    close: '❌ Fermer',
    move_stop: '🎯 Ajuster Stop',
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-gray-900">{review.symbol}</span>
          <span className={`px-2 py-1 rounded-lg text-sm ${
            review.unrealized_pnl >= 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            {review.unrealized_pnl >= 0 ? '+' : ''}${review.unrealized_pnl.toFixed(2)}
            <span className="ml-1 text-xs">
              ({review.unrealized_pnl_pct >= 0 ? '+' : ''}{review.unrealized_pnl_pct.toFixed(2)}%)
            </span>
          </span>
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${decisionColors[review.decision] || 'bg-gray-100'}`}>
          {decisionLabels[review.decision] || review.decision}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-2 mb-3 text-sm">
        <div className="text-center bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">Quantité</div>
          <div className="font-semibold">{review.quantity}</div>
        </div>
        <div className="text-center bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">Entrée</div>
          <div className="font-semibold">${review.entry_price.toFixed(2)}</div>
        </div>
        <div className="text-center bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">Actuel</div>
          <div className="font-semibold">${review.current_price.toFixed(2)}</div>
        </div>
        <div className="text-center bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">Confiance</div>
          <div className={`font-semibold ${
            review.confidence >= 70 ? 'text-green-600' :
            review.confidence >= 50 ? 'text-yellow-600' : 'text-red-600'
          }`}>{review.confidence}%</div>
        </div>
      </div>

      <p className="text-sm text-gray-700">{review.reasoning}</p>

      {(review.new_stop_loss || review.new_target) && (
        <div className="mt-3 flex gap-4 text-sm">
          {review.new_stop_loss && (
            <span className="text-red-600">Nouveau Stop: ${review.new_stop_loss.toFixed(2)}</span>
          )}
          {review.new_target && (
            <span className="text-green-600">Nouvelle Cible: ${review.new_target.toFixed(2)}</span>
          )}
        </div>
      )}

      <div className="mt-3 text-xs text-gray-500">
        {new Date(review.created_at).toLocaleString('fr-FR')}
      </div>
    </div>
  );
}

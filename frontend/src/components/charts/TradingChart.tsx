'use client';

import { useMemo } from 'react';
import {
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
} from 'recharts';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';

interface DataPoint {
  time: string;
  timestamp: number;
  Grok?: number;
  DeepSeek?: number;
  GPT?: number;
  Consortium?: number;
  'S&P 500'?: number;
  'Buffett'?: number;
  [key: string]: string | number | undefined;
}

interface TradingChartProps {
  performanceData: {
    [agent: string]: Array<{ time: string; capital: number; performance: number }>;
  };
  trades?: Array<{
    agent_name: string;
    decision: string;
    symbol: string;
    created_at: string;
  }>;
  height?: number;
  period?: string; // '1h', '24h', '7d', '30d', '3m', '6m', '1y', '5y'
}

// Couleurs des agents et benchmarks
const AGENT_COLORS: Record<string, string> = {
  Grok: '#a855f7',      // Violet
  DeepSeek: '#ec4899',  // Rose
  GPT: '#22c55e',       // Vert
  Consortium: '#f59e0b', // Orange
};

const BENCHMARK_COLORS: Record<string, string> = {
  'S&P 500': '#3b82f6', // Bleu
  'Buffett': '#ef4444', // Rouge
};

// Agents IA
const AI_AGENTS = ['Grok', 'DeepSeek', 'GPT', 'Consortium'];
// Benchmarks
const BENCHMARKS = ['S&P 500', 'Buffett'];

export default function TradingChart({ 
  performanceData, 
  trades = [], 
  height = 400,
  period = '1h'
}: TradingChartProps) {

  // Déterminer le format de l'axe X selon la période
  const getTimeFormat = (period: string): string => {
    switch (period) {
      case '1h':
      case '24h':
        return 'HH:mm';
      case '7d':
        return 'EEE HH:mm'; // Lun 14:00
      case '30d':
        return 'dd MMM'; // 05 Feb
      case '3m':
      case '6m':
        return 'dd MMM'; // 05 Feb
      case '1y':
        return 'MMM yyyy'; // Feb 2026
      case '5y':
        return 'MMM yyyy'; // Feb 2026
      default:
        return 'HH:mm';
    }
  };

  // Construire les données du graphique
  const chartData = useMemo(() => {
    // D'abord, collecter tous les timestamps des benchmarks (ils ont l'historique complet)
    const allTimestamps = new Set<number>();
    
    // Priorité aux benchmarks pour les timestamps
    BENCHMARKS.forEach(benchmark => {
      const data = performanceData[benchmark];
      if (data && data.length > 0) {
        data.forEach(point => {
          allTimestamps.add(new Date(point.time).getTime());
        });
      }
    });

    // Si pas de benchmarks, utiliser les données des agents
    if (allTimestamps.size === 0) {
      AI_AGENTS.forEach(agent => {
        const data = performanceData[agent];
        if (data && data.length > 0) {
          data.forEach(point => {
            allTimestamps.add(new Date(point.time).getTime());
          });
        }
      });
    }

    // Trier les timestamps
    const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

    if (sortedTimestamps.length === 0) {
      return [];
    }

    // Créer un map pour lookup rapide des performances
    const performanceMap: Record<string, Map<number, number>> = {};
    Object.entries(performanceData).forEach(([name, data]) => {
      performanceMap[name] = new Map();
      if (data) {
        data.forEach(point => {
          performanceMap[name].set(new Date(point.time).getTime(), point.performance);
        });
      }
    });

    // Construire les points de données
    return sortedTimestamps.map(timestamp => {
      const point: DataPoint = {
        time: new Date(timestamp).toISOString(),
        timestamp,
      };

      // Ajouter les benchmarks (interpoler si nécessaire)
      BENCHMARKS.forEach(benchmark => {
        const map = performanceMap[benchmark];
        if (map && map.has(timestamp)) {
          point[benchmark] = map.get(timestamp);
        }
      });

      // Ajouter les agents IA
      AI_AGENTS.forEach(agent => {
        const map = performanceMap[agent];
        if (map && map.size > 0) {
          // Si l'agent a des données pour ce timestamp, l'utiliser
          if (map.has(timestamp)) {
            point[agent] = map.get(timestamp);
          } else {
            // Sinon, l'agent est à 0% (pas encore de trades)
            point[agent] = 0;
          }
        } else {
          // Pas de données du tout = 0%
          point[agent] = 0;
        }
      });

      return point;
    });
  }, [performanceData]);

  // Format pour l'axe X
  const formatXAxis = (timestamp: number) => {
    try {
      return format(new Date(timestamp), getTimeFormat(period), { locale: fr });
    } catch {
      return '';
    }
  };

  // Format pour le tooltip
  const formatTooltipTime = (timestamp: number) => {
    try {
      // Format plus détaillé pour le tooltip
      switch (period) {
        case '1h':
        case '24h':
          return format(new Date(timestamp), 'dd MMM HH:mm', { locale: fr });
        case '7d':
        case '30d':
          return format(new Date(timestamp), 'EEEE dd MMM HH:mm', { locale: fr });
        default:
          return format(new Date(timestamp), 'dd MMMM yyyy', { locale: fr });
      }
    } catch {
      return '';
    }
  };

  // Tooltip personnalisé
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || payload.length === 0) return null;
    
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl">
        <p className="text-gray-400 text-xs mb-2">
          {formatTooltipTime(label)}
        </p>
        {payload
          .filter((entry: any) => entry.value !== undefined && entry.value !== null)
          .map((entry: any, index: number) => (
          <div key={index} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-2">
              <span 
                className="w-2 h-2 rounded-full" 
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-white text-sm">{entry.name}</span>
            </span>
            <span className={`text-sm font-mono ${
              entry.value >= 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {entry.value >= 0 ? '+' : ''}{entry.value?.toFixed(2)}%
            </span>
          </div>
        ))}
      </div>
    );
  };

  // Message si pas de données
  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 rounded-xl">
        <p className="text-gray-500">Chargement des données...</p>
      </div>
    );
  }

  // Calculer les bornes Y dynamiquement
  const allValues = chartData.flatMap(d => 
    [...AI_AGENTS, ...BENCHMARKS]
      .map(name => d[name] as number)
      .filter(v => v !== undefined && v !== null && !isNaN(v))
  );
  
  const dataMin = allValues.length > 0 ? Math.min(...allValues) : -1;
  const dataMax = allValues.length > 0 ? Math.max(...allValues) : 1;
  const padding = Math.max(Math.abs(dataMax - dataMin) * 0.1, 0.5);
  const minY = Math.min(dataMin - padding, -0.5);
  const maxY = Math.max(dataMax + padding, 0.5);

  // Calculer le nombre de ticks pour l'axe X selon la période
  const getTickCount = () => {
    switch (period) {
      case '1h': return 6;
      case '24h': return 8;
      case '7d': return 7;
      case '30d': return 10;
      case '3m': return 6;
      case '6m': return 6;
      case '1y': return 12;
      case '5y': return 10;
      default: return 8;
    }
  };

  return (
    <div className="bg-gray-900 rounded-xl p-4" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          {/* Ligne de référence à 0% */}
          <ReferenceLine y={0} stroke="#374151" strokeDasharray="3 3" />
          
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={formatXAxis}
            stroke="#4b5563"
            tick={{ fill: '#9ca3af', fontSize: 10 }}
            axisLine={{ stroke: '#374151' }}
            tickCount={getTickCount()}
            minTickGap={30}
          />
          <YAxis 
            tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
            stroke="#4b5563"
            tick={{ fill: '#9ca3af', fontSize: 10 }}
            axisLine={{ stroke: '#374151' }}
            domain={[minY, maxY]}
            width={60}
          />
          <Tooltip content={<CustomTooltip />} />
          
          {/* Lignes des benchmarks (en premier, en arrière-plan) */}
          {BENCHMARKS.map((benchmark) => (
            <Line
              key={benchmark}
              type="monotone"
              dataKey={benchmark}
              stroke={BENCHMARK_COLORS[benchmark]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: BENCHMARK_COLORS[benchmark], strokeWidth: 2, fill: '#111' }}
              connectNulls
              strokeDasharray="5 5"
            />
          ))}

          {/* Lignes des agents IA (au premier plan) */}
          {AI_AGENTS.map((agent) => (
            <Line
              key={agent}
              type="monotone"
              dataKey={agent}
              stroke={AGENT_COLORS[agent]}
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 5, stroke: AGENT_COLORS[agent], strokeWidth: 2, fill: '#111' }}
              connectNulls
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Légende */}
      <div className="flex flex-wrap items-center justify-center gap-4 mt-3">
        {/* Agents IA */}
        <div className="flex items-center gap-3">
          {AI_AGENTS.map((agent) => (
            <div key={agent} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: AGENT_COLORS[agent] }} />
              <span className="text-gray-300 text-xs">{agent}</span>
            </div>
          ))}
        </div>
        
        {/* Séparateur */}
        <div className="w-px h-4 bg-gray-700" />
        
        {/* Benchmarks */}
        <div className="flex items-center gap-3">
          {BENCHMARKS.map((benchmark) => (
            <div key={benchmark} className="flex items-center gap-1.5">
              <span 
                className="w-4 h-0.5" 
                style={{ 
                  backgroundColor: BENCHMARK_COLORS[benchmark],
                  backgroundImage: `repeating-linear-gradient(90deg, ${BENCHMARK_COLORS[benchmark]}, ${BENCHMARK_COLORS[benchmark]} 3px, transparent 3px, transparent 6px)`
                }} 
              />
              <span className="text-gray-400 text-xs">{benchmark}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

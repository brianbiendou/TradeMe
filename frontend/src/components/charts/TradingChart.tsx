'use client';

import { useEffect, useRef, useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Scatter,
  ComposedChart,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';

interface DataPoint {
  time: string;
  timestamp: number;
  Grok?: number;
  DeepSeek?: number;
  GPT?: number;
  Consortium?: number;
  [key: string]: string | number | undefined;
}

interface TradeMarker {
  time: number;
  value: number;
  agent: string;
  type: 'BUY' | 'SELL';
  symbol: string;
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
}

const AGENT_COLORS: Record<string, string> = {
  Grok: '#a855f7',      // Violet
  DeepSeek: '#ec4899',  // Rose
  GPT: '#22c55e',       // Vert
  Consortium: '#f59e0b', // Orange
};

export default function TradingChart({ performanceData, trades = [], height = 400 }: TradingChartProps) {
  // Stabiliser les données avec useMemo pour éviter les boucles infinies
  const performanceDataKey = useMemo(() => JSON.stringify(performanceData), [performanceData]);
  const tradesKey = useMemo(() => JSON.stringify(trades), [trades]);

  const chartData = useMemo(() => {
    // Fusionner les données de tous les agents par timestamp
    const timeMap = new Map<number, DataPoint>();

    Object.entries(performanceData).forEach(([agent, data]) => {
      data.forEach((point) => {
        const timestamp = new Date(point.time).getTime();
        const existing = timeMap.get(timestamp) || { 
          time: point.time, 
          timestamp 
        };
        existing[agent as keyof DataPoint] = point.performance;
        timeMap.set(timestamp, existing);
      });
    });

    // Trier par timestamp
    return Array.from(timeMap.values()).sort((a, b) => a.timestamp - b.timestamp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [performanceDataKey]);

  const tradeMarkers = useMemo(() => {
    if (trades.length === 0 || chartData.length === 0) return [];
    
    return trades
      .filter(t => t.decision === 'BUY' || t.decision === 'SELL')
      .map(t => {
        const tradeTime = new Date(t.created_at).getTime();
        // Trouver le point le plus proche
        const closest = chartData.reduce((prev, curr) => 
          Math.abs(curr.timestamp - tradeTime) < Math.abs(prev.timestamp - tradeTime) ? curr : prev
        );
        const agentKey = t.agent_name as keyof DataPoint;
        return {
          time: closest.timestamp,
          value: (closest[agentKey] as number) || 0,
          agent: t.agent_name,
          type: t.decision as 'BUY' | 'SELL',
          symbol: t.symbol || '',
        };
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tradesKey, chartData]);

  const formatXAxis = (timestamp: number) => {
    return format(new Date(timestamp), 'HH:mm', { locale: fr });
  };

  const formatTooltip = (value: number, name: string) => {
    return [`${value >= 0 ? '+' : ''}${value.toFixed(2)}%`, name];
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload) return null;
    
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl">
        <p className="text-gray-400 text-xs mb-2">
          {format(new Date(label), 'HH:mm:ss', { locale: fr })}
        </p>
        {payload.map((entry: any, index: number) => (
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

  // Marqueur personnalisé pour les trades
  const TradeMarker = ({ cx, cy, payload }: any) => {
    if (!payload || payload.type === undefined) return null;
    
    const isBuy = payload.type === 'BUY';
    const color = AGENT_COLORS[payload.agent] || '#fff';
    
    return (
      <g>
        <polygon
          points={isBuy 
            ? `${cx},${cy - 8} ${cx - 6},${cy + 4} ${cx + 6},${cy + 4}`  // Triangle haut
            : `${cx},${cy + 8} ${cx - 6},${cy - 4} ${cx + 6},${cy - 4}`  // Triangle bas
          }
          fill={isBuy ? '#22c55e' : '#ef4444'}
          stroke={color}
          strokeWidth={2}
        />
      </g>
    );
  };

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 rounded-xl">
        <p className="text-gray-500">Chargement des données...</p>
      </div>
    );
  }

  // Calculer les bornes Y
  const allValues = chartData.flatMap(d => 
    ['Grok', 'DeepSeek', 'GPT', 'Consortium']
      .map(agent => d[agent as keyof DataPoint] as number)
      .filter(v => v !== undefined)
  );
  const minY = Math.min(...allValues, 0) - 0.5;
  const maxY = Math.max(...allValues, 0) + 0.5;

  return (
    <div className="bg-gray-900 rounded-xl p-4" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
          {/* Ligne de référence à 0% */}
          <ReferenceLine y={0} stroke="#374151" strokeDasharray="3 3" />
          
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={formatXAxis}
            stroke="#4b5563"
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            axisLine={{ stroke: '#374151' }}
          />
          <YAxis 
            tickFormatter={(v) => `${v}%`}
            stroke="#4b5563"
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            axisLine={{ stroke: '#374151' }}
            domain={[minY, maxY]}
          />
          <Tooltip content={<CustomTooltip />} />
          
          {/* Lignes pour chaque agent */}
          {Object.entries(AGENT_COLORS).map(([agent, color]) => (
            <Line
              key={agent}
              type="monotone"
              dataKey={agent}
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: color, strokeWidth: 2, fill: '#111' }}
              connectNulls
            />
          ))}

          {/* Marqueurs de trades */}
          {tradeMarkers.length > 0 && (
            <Scatter
              data={tradeMarkers.map(m => ({ timestamp: m.time, y: m.value, ...m }))}
              dataKey="y"
              shape={<TradeMarker />}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Légende */}
      <div className="flex items-center justify-center gap-6 mt-4">
        {Object.entries(AGENT_COLORS).map(([agent, color]) => (
          <div key={agent} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-gray-300 text-sm">{agent}</span>
          </div>
        ))}
        <div className="flex items-center gap-2 ml-4">
          <span className="text-green-500">▲</span>
          <span className="text-gray-400 text-xs">BUY</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-red-500">▼</span>
          <span className="text-gray-400 text-xs">SELL</span>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { PerformancePoint, TimeFilter } from '@/types';
import { format, parseISO, subHours, subDays, subMonths, subYears } from 'date-fns';
import { fr } from 'date-fns/locale';

interface PerformanceChartProps {
  data: PerformancePoint[];
  timeFilter: TimeFilter;
}

const agentColors: Record<string, string> = {
  Grok: '#667eea',
  DeepSeek: '#f5576c',
  GPT: '#4facfe',
  Consortium: '#43e97b',
};

export default function PerformanceChart({ data, timeFilter }: PerformanceChartProps) {
  // Filtrer les données selon le filtre temporel
  const filteredData = useMemo(() => {
    const now = new Date();
    let startDate: Date;

    switch (timeFilter) {
      case '1h':
        startDate = subHours(now, 1);
        break;
      case '24h':
        startDate = subHours(now, 24);
        break;
      case '7d':
        startDate = subDays(now, 7);
        break;
      case '30d':
        startDate = subDays(now, 30);
        break;
      case '3m':
        startDate = subMonths(now, 3);
        break;
      case '6m':
        startDate = subMonths(now, 6);
        break;
      case '1y':
        startDate = subYears(now, 1);
        break;
      case '5y':
        startDate = subYears(now, 5);
        break;
      default:
        startDate = subDays(now, 30);
    }

    return data.filter((point) => {
      const pointDate = parseISO(point.timestamp);
      return pointDate >= startDate;
    });
  }, [data, timeFilter]);

  // Transformer les données pour Recharts (pivot par date)
  const chartData = useMemo(() => {
    const grouped: Record<string, any> = {};

    filteredData.forEach((point) => {
      const dateKey = point.timestamp.split('T')[0];
      if (!grouped[dateKey]) {
        grouped[dateKey] = { date: dateKey };
      }
      grouped[dateKey][point.agent] = point.value;
    });

    return Object.values(grouped).sort((a, b) => 
      new Date(a.date).getTime() - new Date(b.date).getTime()
    );
  }, [filteredData]);

  // Format de date selon le filtre
  const formatDate = (dateStr: string) => {
    const date = parseISO(dateStr);
    if (['1h', '24h'].includes(timeFilter)) {
      return format(date, 'HH:mm', { locale: fr });
    }
    if (['7d', '30d'].includes(timeFilter)) {
      return format(date, 'dd MMM', { locale: fr });
    }
    return format(date, 'MMM yyyy', { locale: fr });
  };

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="#9ca3af"
            fontSize={12}
          />
          <YAxis
            stroke="#9ca3af"
            fontSize={12}
            tickFormatter={(value) => `$${value}`}
            domain={['dataMin - 50', 'dataMax + 50']}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
            }}
            formatter={(value: number, name: string) => [
              `$${value.toFixed(2)}`,
              name,
            ]}
            labelFormatter={(label) => format(parseISO(label), 'dd MMMM yyyy', { locale: fr })}
          />
          <Legend />
          {Object.entries(agentColors).map(([agent, color]) => (
            <Line
              key={agent}
              type="monotone"
              dataKey={agent}
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

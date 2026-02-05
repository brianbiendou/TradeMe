'use client';

import { LeaderboardEntry } from '@/types';
import { Trophy, TrendingUp, TrendingDown } from 'lucide-react';

interface LeaderboardProps {
  entries: LeaderboardEntry[];
}

export default function Leaderboard({ entries }: LeaderboardProps) {
  const getRankIcon = (rank: number) => {
    if (rank === 1) return <Trophy className="w-5 h-5 text-yellow-500" />;
    if (rank === 2) return <Trophy className="w-5 h-5 text-gray-400" />;
    if (rank === 3) return <Trophy className="w-5 h-5 text-amber-600" />;
    return <span className="w-5 h-5 flex items-center justify-center text-gray-400 font-medium">{rank}</span>;
  };

  const getGradientClass = (name: string | undefined) => {
    if (!name) return 'border-l-4 border-l-gray-300';
    const lowercaseName = name.toLowerCase();
    if (lowercaseName === 'grok') return 'border-l-4 border-l-purple-500';
    if (lowercaseName === 'deepseek') return 'border-l-4 border-l-pink-500';
    if (lowercaseName === 'gpt') return 'border-l-4 border-l-blue-500';
    if (lowercaseName === 'consortium') return 'border-l-4 border-l-green-500';
    return 'border-l-4 border-l-gray-300';
  };

  return (
    <div className="space-y-3">
      {entries.filter(e => e && e.name).map((entry, index) => (
        <div
          key={entry.name || index}
          className={`bg-white rounded-lg shadow-sm p-4 ${getGradientClass(entry.name)} card-hover`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              {/* Rank */}
              <div className="flex items-center justify-center w-10 h-10 bg-gray-100 rounded-full">
                {getRankIcon(entry.rank || index + 1)}
              </div>
              
              {/* Info */}
              <div>
                <h3 className="font-semibold text-gray-900">{entry.name || 'Agent'}</h3>
                <p className="text-sm text-gray-500">
                  {entry.trade_count || 0} trades · {(entry.win_rate || 0).toFixed(1)}% win rate
                </p>
              </div>
            </div>

            {/* Performance */}
            <div className="text-right">
              <div className={`flex items-center justify-end ${
                (entry.performance_pct || 0) >= 0 ? 'text-success-600' : 'text-danger-600'
              }`}>
                {(entry.performance_pct || 0) >= 0 ? (
                  <TrendingUp className="w-4 h-4 mr-1" />
                ) : (
                  <TrendingDown className="w-4 h-4 mr-1" />
                )}
                <span className="font-bold">
                  {(entry.performance_pct || 0) >= 0 ? '+' : ''}
                  {(entry.performance_pct || 0).toFixed(2)}%
                </span>
              </div>
              <p className="text-sm text-gray-500">
                ${(entry.current_capital || 0).toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

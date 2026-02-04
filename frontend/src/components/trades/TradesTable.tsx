'use client';

import { Trade } from '@/types';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';

interface TradesTableProps {
  trades: Trade[];
  showAgent?: boolean;
}

export default function TradesTable({ trades, showAgent = false }: TradesTableProps) {
  const getDecisionIcon = (decision: string) => {
    switch (decision) {
      case 'BUY':
        return <ArrowUpRight className="w-4 h-4 text-success-600" />;
      case 'SELL':
        return <ArrowDownRight className="w-4 h-4 text-danger-600" />;
      default:
        return <Minus className="w-4 h-4 text-gray-400" />;
    }
  };

  const getDecisionBadge = (decision: string) => {
    const baseClasses = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium';
    switch (decision) {
      case 'BUY':
        return `${baseClasses} bg-success-100 text-success-700`;
      case 'SELL':
        return `${baseClasses} bg-danger-100 text-danger-700`;
      default:
        return `${baseClasses} bg-gray-100 text-gray-600`;
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead>
          <tr className="bg-gray-50">
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Date
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Décision
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Symbole
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Quantité
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Prix
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              P&L
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Confiance
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {trades.map((trade, index) => (
            <tr key={index} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">
                {format(parseISO(trade.timestamp), 'dd MMM HH:mm', { locale: fr })}
              </td>
              <td className="px-4 py-4 whitespace-nowrap">
                <span className={getDecisionBadge(trade.decision)}>
                  {getDecisionIcon(trade.decision)}
                  <span className="ml-1">{trade.decision}</span>
                </span>
              </td>
              <td className="px-4 py-4 whitespace-nowrap">
                <span className="text-sm font-medium text-gray-900">
                  {trade.symbol || '-'}
                </span>
              </td>
              <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">
                {trade.quantity || '-'}
              </td>
              <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">
                {trade.price ? `$${trade.price.toFixed(2)}` : '-'}
              </td>
              <td className="px-4 py-4 whitespace-nowrap">
                {trade.pnl !== 0 ? (
                  <span className={`text-sm font-medium ${
                    trade.pnl > 0 ? 'text-success-600' : 'text-danger-600'
                  }`}>
                    {trade.pnl > 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                  </span>
                ) : (
                  <span className="text-sm text-gray-400">-</span>
                )}
              </td>
              <td className="px-4 py-4 whitespace-nowrap">
                <div className="flex items-center">
                  <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        trade.confidence >= 70
                          ? 'bg-success-500'
                          : trade.confidence >= 50
                          ? 'bg-warning-500'
                          : 'bg-danger-500'
                      }`}
                      style={{ width: `${trade.confidence}%` }}
                    />
                  </div>
                  <span className="ml-2 text-xs text-gray-500">{trade.confidence}%</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      
      {trades.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          Aucun trade pour le moment
        </div>
      )}
    </div>
  );
}

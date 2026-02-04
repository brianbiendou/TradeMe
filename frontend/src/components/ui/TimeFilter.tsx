'use client';

import { useState } from 'react';
import { TimeFilter } from '@/types';

interface TimeFilterProps {
  value: TimeFilter;
  onChange: (filter: TimeFilter) => void;
  dark?: boolean;
}

const filters: { label: string; value: TimeFilter }[] = [
  { label: '1H', value: '1h' },
  { label: '24H', value: '24h' },
  { label: '7J', value: '7d' },
  { label: '30J', value: '30d' },
  { label: '3M', value: '3m' },
  { label: '6M', value: '6m' },
  { label: '1A', value: '1y' },
  { label: '5A', value: '5y' },
];

export default function TimeFilterSelector({ value, onChange, dark = false }: TimeFilterProps) {
  return (
    <div className={`inline-flex rounded-lg p-1 ${dark ? 'bg-gray-800' : 'bg-gray-100'}`}>
      {filters.map((filter) => (
        <button
          key={filter.value}
          onClick={() => onChange(filter.value)}
          className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
            value === filter.value
              ? dark 
                ? 'bg-gray-700 text-white shadow-sm'
                : 'bg-white text-gray-900 shadow-sm'
              : dark
                ? 'text-gray-400 hover:text-gray-200'
                : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {filter.label}
        </button>
      ))}
    </div>
  );
}

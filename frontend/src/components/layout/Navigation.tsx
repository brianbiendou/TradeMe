'use client';

import { ReactNode, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Bot,
  TrendingUp,
  History,
  Settings,
  Menu,
  X,
  Activity,
  Trophy,
  Eye,
} from 'lucide-react';

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
}

const navItems: NavItem[] = [
  { href: '/', label: 'Dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
  { href: '/agents', label: 'Agents IA', icon: <Bot className="w-5 h-5" /> },
  { href: '/veille', label: 'Veille IA', icon: <Eye className="w-5 h-5" /> },
  { href: '/trades', label: 'Trades', icon: <TrendingUp className="w-5 h-5" /> },
  { href: '/leaderboard', label: 'Classement', icon: <Trophy className="w-5 h-5" /> },
  { href: '/history', label: 'Historique', icon: <History className="w-5 h-5" /> },
  { href: '/settings', label: 'Paramètres', icon: <Settings className="w-5 h-5" /> },
];

export default function Navigation() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Sidebar Desktop */}
      <aside className="hidden md:flex md:flex-col md:w-64 md:fixed md:inset-y-0 bg-white border-r border-gray-200">
        {/* Logo */}
        <div className="flex items-center h-16 px-6 border-b border-gray-200">
          <Activity className="w-8 h-8 text-blue-600" />
          <span className="ml-3 text-xl font-bold text-gray-900">TradeMe</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <span className={isActive ? 'text-blue-600' : 'text-gray-400'}>
                  {item.icon}
                </span>
                <span className="ml-3">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Status */}
        <div className="px-4 py-4 border-t border-gray-200">
          <div className="flex items-center px-4 py-3 bg-green-50 rounded-lg">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            <span className="ml-3 text-sm font-medium text-green-700">
              Marché ouvert
            </span>
          </div>
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between h-16 px-4">
          <div className="flex items-center">
            <Activity className="w-8 h-8 text-blue-600" />
            <span className="ml-2 text-xl font-bold text-gray-900">TradeMe</span>
          </div>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="p-2 rounded-lg hover:bg-gray-100"
          >
            {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Sidebar Overlay */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black bg-opacity-50"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Mobile Sidebar */}
      <aside
        className={`md:hidden fixed top-16 left-0 bottom-0 z-40 w-64 bg-white border-r border-gray-200 transform transition-transform ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <nav className="px-4 py-6 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setIsOpen(false)}
                className={`flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <span className={isActive ? 'text-blue-600' : 'text-gray-400'}>
                  {item.icon}
                </span>
                <span className="ml-3">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
    </>
  );
}

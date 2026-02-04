import type { Metadata } from 'next';
import './globals.css';
import Navigation from '@/components/layout/Navigation';

export const metadata: Metadata = {
  title: 'TradeMe - Multi-AI Trading Dashboard',
  description: 'Plateforme de trading automatisé avec plusieurs agents IA',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-white">
        <Navigation />
        <main className="md:ml-64 pt-16 md:pt-0 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}

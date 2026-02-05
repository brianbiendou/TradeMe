"""
Backtesting Service - Teste les stratégies sur l'historique.
Valide les décisions AVANT de les exécuter en live.

FONCTIONNALITÉS:
1. Backtest sur les N derniers trades
2. Calcul du win-rate attendu
3. Validation du Kelly fraction
4. Détection des stratégies "cassées"
5. Recommandations d'ajustement
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .supabase_client import supabase_client
from .memory_service import memory_service

logger = logging.getLogger(__name__)


class StrategyHealth(Enum):
    """Santé de la stratégie."""
    EXCELLENT = "EXCELLENT"  # Win rate > 65%
    GOOD = "GOOD"  # Win rate 55-65%
    AVERAGE = "AVERAGE"  # Win rate 45-55%
    POOR = "POOR"  # Win rate 35-45%
    BROKEN = "BROKEN"  # Win rate < 35%


@dataclass
class BacktestResult:
    """Résultat d'un backtest."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    win_loss_ratio: float
    total_pnl: float
    max_drawdown: float
    sharpe_estimate: float
    kelly_fraction: float
    strategy_health: StrategyHealth
    recommendations: List[str]
    period_days: int


class BacktestService:
    """
    Service de backtesting pour valider les stratégies.
    """
    
    def __init__(self):
        self._initialized = False
        
        # Seuils de santé
        self.excellent_threshold = 0.65  # >65% win rate
        self.good_threshold = 0.55  # >55%
        self.average_threshold = 0.45  # >45%
        self.poor_threshold = 0.35  # >35%
        # <35% = BROKEN
        
        # Minimum trades pour backtest valide
        self.min_trades_for_valid_backtest = 10
    
    def initialize(self) -> bool:
        """Initialise le service."""
        self._initialized = True
        logger.info("✅ Backtest Service initialisé")
        return True
    
    async def backtest_agent(
        self,
        agent_id: str,
        days: int = 30,
        include_open: bool = False,
    ) -> Optional[BacktestResult]:
        """
        Exécute un backtest sur les trades historiques d'un agent.
        
        Args:
            agent_id: ID de l'agent
            days: Nombre de jours à analyser
            include_open: Inclure les positions encore ouvertes
        
        Returns:
            BacktestResult avec les métriques
        """
        if not supabase_client._initialized:
            logger.warning("Supabase non initialisé, backtest impossible")
            return None
        
        try:
            # Récupérer les trades de la période
            since = (datetime.now() - timedelta(days=days)).isoformat()
            
            query = supabase_client.client.table('trade_memories').select('*')
            query = query.eq('agent_id', agent_id)
            query = query.gte('created_at', since)
            
            if not include_open:
                query = query.not_.is_('success', 'null')
            
            response = query.order('created_at', desc=False).execute()
            trades = response.data
            
            if not trades:
                logger.info(f"Aucun trade trouvé pour backtest (agent={agent_id}, days={days})")
                return BacktestResult(
                    total_trades=0,
                    winning_trades=0,
                    losing_trades=0,
                    win_rate=0.5,  # Default
                    avg_win_pct=0,
                    avg_loss_pct=0,
                    win_loss_ratio=1.5,
                    total_pnl=0,
                    max_drawdown=0,
                    sharpe_estimate=0,
                    kelly_fraction=0.125,
                    strategy_health=StrategyHealth.AVERAGE,
                    recommendations=["Pas assez de trades pour un backtest valide"],
                    period_days=days,
                )
            
            # Calculer les métriques
            return self._calculate_metrics(trades, days)
            
        except Exception as e:
            logger.error(f"Erreur backtest: {e}")
            return None
    
    def _calculate_metrics(
        self,
        trades: List[Dict],
        period_days: int,
    ) -> BacktestResult:
        """Calcule les métriques de backtest."""
        
        # Compter les résultats
        wins = [t for t in trades if t.get('success') is True]
        losses = [t for t in trades if t.get('success') is False]
        
        total = len(wins) + len(losses)
        if total == 0:
            return BacktestResult(
                total_trades=len(trades),
                winning_trades=0,
                losing_trades=0,
                win_rate=0.5,
                avg_win_pct=0,
                avg_loss_pct=0,
                win_loss_ratio=1.5,
                total_pnl=0,
                max_drawdown=0,
                sharpe_estimate=0,
                kelly_fraction=0.125,
                strategy_health=StrategyHealth.AVERAGE,
                recommendations=["Trades sans résultat défini"],
                period_days=period_days,
            )
        
        # Win rate
        win_rate = len(wins) / total
        
        # Moyennes de gains/pertes
        win_pcts = [float(t.get('pnl_percent', 0)) for t in wins if t.get('pnl_percent')]
        loss_pcts = [abs(float(t.get('pnl_percent', 0))) for t in losses if t.get('pnl_percent')]
        
        avg_win_pct = sum(win_pcts) / len(win_pcts) if win_pcts else 3.0  # Default 3%
        avg_loss_pct = sum(loss_pcts) / len(loss_pcts) if loss_pcts else 2.0  # Default 2%
        
        # Win/Loss ratio
        win_loss_ratio = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 1.5
        
        # Total PnL
        total_pnl = sum(float(t.get('pnl', 0)) for t in trades if t.get('pnl'))
        
        # Max Drawdown (simplifié)
        max_drawdown = self._calculate_max_drawdown(trades)
        
        # Kelly Fraction
        kelly = win_rate - (1 - win_rate) / win_loss_ratio if win_loss_ratio > 0 else 0
        kelly = max(0, kelly)  # Pas de Kelly négatif
        
        # Sharpe estimate (simplifié)
        returns = [float(t.get('pnl_percent', 0)) for t in trades if t.get('pnl_percent')]
        if returns:
            import statistics
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = (mean_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        else:
            sharpe = 0
        
        # Déterminer la santé
        strategy_health = self._determine_health(win_rate, win_loss_ratio, max_drawdown)
        
        # Générer les recommandations
        recommendations = self._generate_recommendations(
            win_rate, avg_win_pct, avg_loss_pct, win_loss_ratio, max_drawdown, total
        )
        
        return BacktestResult(
            total_trades=total,
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            win_loss_ratio=win_loss_ratio,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            sharpe_estimate=sharpe,
            kelly_fraction=kelly,
            strategy_health=strategy_health,
            recommendations=recommendations,
            period_days=period_days,
        )
    
    def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
        """Calcule le max drawdown."""
        if not trades:
            return 0
        
        cumulative = 0
        peak = 0
        max_dd = 0
        
        for trade in trades:
            pnl_pct = float(trade.get('pnl_percent', 0) or 0)
            cumulative += pnl_pct
            
            if cumulative > peak:
                peak = cumulative
            
            drawdown = peak - cumulative
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def _determine_health(
        self,
        win_rate: float,
        win_loss_ratio: float,
        max_drawdown: float,
    ) -> StrategyHealth:
        """Détermine la santé de la stratégie."""
        
        # Pénaliser si drawdown élevé
        effective_wr = win_rate
        if max_drawdown > 15:
            effective_wr *= 0.9
        elif max_drawdown > 25:
            effective_wr *= 0.8
        
        # Bonus si bon ratio G/P
        if win_loss_ratio > 2:
            effective_wr *= 1.1
        
        if effective_wr >= self.excellent_threshold:
            return StrategyHealth.EXCELLENT
        elif effective_wr >= self.good_threshold:
            return StrategyHealth.GOOD
        elif effective_wr >= self.average_threshold:
            return StrategyHealth.AVERAGE
        elif effective_wr >= self.poor_threshold:
            return StrategyHealth.POOR
        else:
            return StrategyHealth.BROKEN
    
    def _generate_recommendations(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        wl_ratio: float,
        max_dd: float,
        total_trades: int,
    ) -> List[str]:
        """Génère des recommandations basées sur les métriques."""
        recs = []
        
        # Pas assez de trades
        if total_trades < self.min_trades_for_valid_backtest:
            recs.append(f"⚠️ Seulement {total_trades} trades - résultats peu fiables")
        
        # Win rate
        if win_rate < 0.40:
            recs.append("🚨 Win rate très bas (<40%) - Revoir les critères d'entrée")
        elif win_rate < 0.50:
            recs.append("⚠️ Win rate sous 50% - Améliorer la sélection des trades")
        elif win_rate > 0.65:
            recs.append("✅ Excellent win rate! Maintenir la stratégie actuelle")
        
        # Ratio G/P
        if wl_ratio < 1:
            recs.append("🚨 Ratio G/P < 1 - Les pertes sont plus grandes que les gains")
            recs.append("   → Resserrer les stop-losses ou élargir les take-profits")
        elif wl_ratio < 1.5:
            recs.append("⚠️ Ratio G/P faible - Viser des gains plus importants")
        
        # Drawdown
        if max_dd > 20:
            recs.append(f"🚨 Max drawdown élevé ({max_dd:.1f}%) - Réduire la taille des positions")
        elif max_dd > 10:
            recs.append(f"⚠️ Max drawdown de {max_dd:.1f}% - Surveiller les pertes consécutives")
        
        # Gains moyens
        if avg_win < 2:
            recs.append("💡 Gains moyens faibles - Laisser courir les profits plus longtemps")
        
        if avg_loss > 5:
            recs.append("⚠️ Pertes moyennes élevées (>5%) - Couper les pertes plus tôt")
        
        if not recs:
            recs.append("✅ Métriques dans les normes - Continuer ainsi!")
        
        return recs
    
    async def validate_trade_decision(
        self,
        agent_id: str,
        symbol: str,
        decision: str,
        confidence: int,
    ) -> Tuple[bool, str, float]:
        """
        Valide une décision de trade en se basant sur l'historique.
        
        Args:
            agent_id: ID de l'agent
            symbol: Symbole à trader
            decision: BUY/SELL
            confidence: Niveau de confiance
        
        Returns:
            (should_proceed, reason, adjusted_sizing_multiplier)
        """
        # Backtest rapide sur 30 jours
        result = await self.backtest_agent(agent_id, days=30)
        
        if not result or result.total_trades < 5:
            return True, "Pas assez d'historique pour valider", 1.0
        
        # Vérifier la santé
        if result.strategy_health == StrategyHealth.BROKEN:
            return False, f"🚨 Stratégie CASSÉE (win rate {result.win_rate*100:.1f}%) - Trading bloqué", 0.0
        
        # Vérifier l'historique sur ce symbole
        symbol_trades = memory_service.get_similar_trades(agent_id, symbol=symbol, limit=5)
        if symbol_trades:
            symbol_wins = len([t for t in symbol_trades if t.get('success')])
            symbol_wr = symbol_wins / len(symbol_trades)
            
            if symbol_wr < 0.3:
                return False, f"⚠️ Mauvais historique sur {symbol} (win rate {symbol_wr*100:.0f}%)", 0.5
        
        # Ajuster le sizing selon la santé
        sizing_multipliers = {
            StrategyHealth.EXCELLENT: 1.2,
            StrategyHealth.GOOD: 1.0,
            StrategyHealth.AVERAGE: 0.8,
            StrategyHealth.POOR: 0.5,
            StrategyHealth.BROKEN: 0.0,
        }
        
        multiplier = sizing_multipliers.get(result.strategy_health, 1.0)
        
        return True, f"Stratégie {result.strategy_health.value} - sizing x{multiplier}", multiplier
    
    def format_backtest_for_agent(self, result: BacktestResult) -> str:
        """Formate le résultat pour inclusion dans le prompt."""
        
        health_emoji = {
            StrategyHealth.EXCELLENT: "🟢",
            StrategyHealth.GOOD: "🟢",
            StrategyHealth.AVERAGE: "🟡",
            StrategyHealth.POOR: "🟠",
            StrategyHealth.BROKEN: "🔴",
        }
        
        lines = [
            f"\n## 📊 BACKTEST ({result.period_days} derniers jours)",
            f"{health_emoji.get(result.strategy_health, '⚪')} Santé: **{result.strategy_health.value}**",
            f"",
            f"**Statistiques:**",
            f"- Trades: {result.total_trades} ({result.winning_trades}W / {result.losing_trades}L)",
            f"- Win Rate: {result.win_rate*100:.1f}%",
            f"- Ratio G/P: {result.win_loss_ratio:.2f}",
            f"- P&L Total: ${result.total_pnl:.2f}",
            f"- Max Drawdown: {result.max_drawdown:.1f}%",
            f"- Kelly suggéré: {result.kelly_fraction*100:.1f}%",
            f"",
            f"**Recommandations:**",
        ]
        
        for rec in result.recommendations[:3]:
            lines.append(f"  {rec}")
        
        return "\n".join(lines)


# Instance globale
backtest_service = BacktestService()

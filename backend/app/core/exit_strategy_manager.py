"""
Exit Strategy Manager - Gestion automatique des sorties de positions.
Stop-Loss, Take-Profit, et Trailing Stops intelligents.

CRITÈRES DE SORTIE:
1. Stop-Loss fixe: -5% par défaut (ajustable par volatilité)
2. Take-Profit fixe: +8% par défaut (ajustable par momentum)
3. Trailing Stop: Protège les gains quand +3% atteint
4. Time-based exit: Sortie si position stagne >5 jours
5. Signal-based exit: Sortie si Smart Money devient très bearish
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ExitReason(Enum):
    """Raisons de sortie d'une position."""
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_EXIT = "TIME_EXIT"
    SIGNAL_EXIT = "SIGNAL_EXIT"
    MANUAL = "MANUAL"


@dataclass
class ExitLevel:
    """Niveaux de sortie pour une position."""
    stop_loss_price: float
    stop_loss_pct: float
    take_profit_price: float
    take_profit_pct: float
    trailing_stop_active: bool
    trailing_stop_price: Optional[float]
    highest_price_seen: float
    entry_time: datetime
    reasoning: str


@dataclass
class ExitSignal:
    """Signal de sortie généré."""
    should_exit: bool
    reason: ExitReason
    urgency: str  # LOW, MEDIUM, HIGH, CRITICAL
    current_pnl_pct: float
    message: str


class ExitStrategyManager:
    """
    Gestionnaire des stratégies de sortie.
    Calcule et vérifie les conditions de sortie pour chaque position.
    """
    
    def __init__(self):
        self._initialized = False
        
        # === PARAMÈTRES STOP-LOSS (V2.2 - Ratio 2:1) ===
        self.default_stop_loss_pct = 0.03  # -3% par défaut (AVANT: -5%)
        self.min_stop_loss_pct = 0.02  # -2% minimum (AVANT: -3%)
        self.max_stop_loss_pct = 0.06  # -6% maximum (AVANT: -10%)
        
        # === PARAMÈTRES TAKE-PROFIT (V2.2 - Ratio 2:1) ===
        self.default_take_profit_pct = 0.06  # +6% par défaut (AVANT: +8%)
        self.min_take_profit_pct = 0.04  # +4% minimum
        self.max_take_profit_pct = 0.15  # +15% maximum (AVANT: +20%)
        
        # === PARAMÈTRES TRAILING STOP (V2.2 - Plus agressif) ===
        self.trailing_activation_pct = 0.04  # Active à +4% (AVANT: +3%)
        self.trailing_distance_pct = 0.015  # 1.5% en dessous du plus haut (AVANT: 2%)
        self.trailing_max_target_pct = 0.12  # Target trailing +12%
        
        # === PARAMÈTRES TAKE-PROFIT PARTIEL (V2.2 - NOUVEAU) ===
        self.partial_take_profit_enabled = True
        self.partial_take_profit_pct = 0.06  # Prendre 50% des profits à +6%
        self.partial_take_profit_ratio = 0.5  # Vendre 50% de la position
        
        # === PARAMÈTRES TIME EXIT ===
        self.max_holding_days = 10  # Sortie après 10 jours si stagnant
        self.stagnation_threshold_pct = 0.01  # <1% de mouvement = stagnant
        
        # === CACHE DES POSITIONS ===
        self.position_exits: Dict[str, Dict[str, ExitLevel]] = {}  # agent_id -> {symbol -> ExitLevel}
        self.highest_prices: Dict[str, Dict[str, float]] = {}  # Pour trailing stop
    
    def initialize(self) -> bool:
        """Initialise le manager."""
        self._initialized = True
        logger.info("✅ Exit Strategy Manager initialisé")
        logger.info(f"   📉 Stop-Loss par défaut: {self.default_stop_loss_pct*100}%")
        logger.info(f"   📈 Take-Profit par défaut: {self.default_take_profit_pct*100}%")
        logger.info(f"   🔄 Trailing Stop: Active à +{self.trailing_activation_pct*100}%")
        return True
    
    def calculate_stop_loss_pct(
        self,
        vix: float = 20,
        confidence: int = 50,
        risk_level: str = "MEDIUM",
    ) -> float:
        """
        Calcule le pourcentage de stop-loss adaptatif.
        
        - VIX élevé → Stop plus serré (marché volatile)
        - Confiance basse → Stop plus serré (pas convaincu)
        - Risque HIGH → Stop plus serré
        """
        base_sl = self.default_stop_loss_pct
        
        # Ajustement VIX
        if vix > 30:
            base_sl *= 0.8  # Stop plus serré si très volatile
        elif vix > 25:
            base_sl *= 0.9
        elif vix < 15:
            base_sl *= 1.1  # Stop plus large si calme
        
        # Ajustement confiance
        if confidence < 60:
            base_sl *= 0.8  # Stop serré si pas confiant
        elif confidence >= 85:
            base_sl *= 1.1  # Stop large si très confiant
        
        # Ajustement risque
        if risk_level == "HIGH":
            base_sl *= 0.85
        elif risk_level == "LOW":
            base_sl *= 1.1
        
        return max(self.min_stop_loss_pct, min(self.max_stop_loss_pct, base_sl))
    
    def calculate_take_profit_pct(
        self,
        vix: float = 20,
        confidence: int = 50,
        smart_money_signal: str = "NEUTRAL",
    ) -> float:
        """
        Calcule le pourcentage de take-profit adaptatif.
        
        - VIX bas + signal bullish → Target plus haut
        - Signal bearish → Target plus bas (prendre profits tôt)
        """
        base_tp = self.default_take_profit_pct
        
        # Ajustement VIX
        if vix < 15:
            base_tp *= 1.2  # Target plus haut si calme (tendance possible)
        elif vix > 30:
            base_tp *= 0.8  # Target plus bas si volatile (profiter vite)
        
        # Ajustement confiance
        if confidence >= 85:
            base_tp *= 1.15  # Target plus haut si très confiant
        elif confidence < 60:
            base_tp *= 0.85
        
        # Ajustement Smart Money
        if smart_money_signal in ["BULLISH", "STRONG_BULLISH"]:
            base_tp *= 1.1
        elif smart_money_signal in ["BEARISH", "STRONG_BEARISH"]:
            base_tp *= 0.8
        
        return max(self.min_take_profit_pct, min(self.max_take_profit_pct, base_tp))
    
    def create_exit_levels(
        self,
        agent_id: str,
        symbol: str,
        entry_price: float,
        confidence: int = 50,
        risk_level: str = "MEDIUM",
        vix: float = 20,
        smart_money_signal: str = "NEUTRAL",
    ) -> ExitLevel:
        """
        Crée les niveaux de sortie pour une nouvelle position.
        
        Args:
            agent_id: ID de l'agent
            symbol: Symbole de l'action
            entry_price: Prix d'entrée
            confidence: Confiance de l'IA (0-100)
            risk_level: Niveau de risque (LOW, MEDIUM, HIGH)
            vix: Niveau VIX actuel
            smart_money_signal: Signal des données alternatives
        
        Returns:
            ExitLevel avec tous les niveaux calculés
        """
        # Calculer les pourcentages adaptatifs
        sl_pct = self.calculate_stop_loss_pct(vix, confidence, risk_level)
        tp_pct = self.calculate_take_profit_pct(vix, confidence, smart_money_signal)
        
        # Calculer les prix
        stop_loss_price = entry_price * (1 - sl_pct)
        take_profit_price = entry_price * (1 + tp_pct)
        
        exit_level = ExitLevel(
            stop_loss_price=round(stop_loss_price, 2),
            stop_loss_pct=sl_pct,
            take_profit_price=round(take_profit_price, 2),
            take_profit_pct=tp_pct,
            trailing_stop_active=False,
            trailing_stop_price=None,
            highest_price_seen=entry_price,
            entry_time=datetime.now(),
            reasoning=self._build_exit_reasoning(
                entry_price, sl_pct, tp_pct, vix, confidence, smart_money_signal
            )
        )
        
        # Stocker dans le cache
        if agent_id not in self.position_exits:
            self.position_exits[agent_id] = {}
            self.highest_prices[agent_id] = {}
        
        self.position_exits[agent_id][symbol] = exit_level
        self.highest_prices[agent_id][symbol] = entry_price
        
        logger.info(
            f"🎯 Exit Levels créés pour {symbol}: "
            f"SL=${exit_level.stop_loss_price} (-{sl_pct*100:.1f}%), "
            f"TP=${exit_level.take_profit_price} (+{tp_pct*100:.1f}%)"
        )
        
        return exit_level
    
    def check_exit_conditions(
        self,
        agent_id: str,
        symbol: str,
        current_price: float,
        smart_money_signal: str = "NEUTRAL",
    ) -> ExitSignal:
        """
        Vérifie si une position doit être fermée.
        
        Args:
            agent_id: ID de l'agent
            symbol: Symbole de l'action
            current_price: Prix actuel
            smart_money_signal: Signal Smart Money actuel
        
        Returns:
            ExitSignal indiquant si on doit sortir et pourquoi
        """
        # Récupérer les niveaux de sortie
        if agent_id not in self.position_exits or symbol not in self.position_exits[agent_id]:
            return ExitSignal(
                should_exit=False,
                reason=ExitReason.MANUAL,
                urgency="LOW",
                current_pnl_pct=0,
                message="Aucun niveau de sortie défini pour cette position"
            )
        
        exit_level = self.position_exits[agent_id][symbol]
        entry_price = exit_level.highest_price_seen / (1 + exit_level.take_profit_pct) * (1 + exit_level.take_profit_pct)
        
        # Calculer le prix d'entrée approximatif
        # On utilise le stop-loss pour déduire le prix d'entrée
        entry_price = exit_level.stop_loss_price / (1 - exit_level.stop_loss_pct)
        current_pnl_pct = (current_price - entry_price) / entry_price
        
        # 1. CHECK STOP-LOSS
        if current_price <= exit_level.stop_loss_price:
            return ExitSignal(
                should_exit=True,
                reason=ExitReason.STOP_LOSS,
                urgency="CRITICAL",
                current_pnl_pct=current_pnl_pct,
                message=f"🚨 STOP-LOSS ATTEINT! Prix ${current_price:.2f} <= ${exit_level.stop_loss_price:.2f} ({current_pnl_pct*100:.1f}%)"
            )
        
        # 2. CHECK TAKE-PROFIT
        if current_price >= exit_level.take_profit_price:
            return ExitSignal(
                should_exit=True,
                reason=ExitReason.TAKE_PROFIT,
                urgency="HIGH",
                current_pnl_pct=current_pnl_pct,
                message=f"🎉 TAKE-PROFIT ATTEINT! Prix ${current_price:.2f} >= ${exit_level.take_profit_price:.2f} (+{current_pnl_pct*100:.1f}%)"
            )
        
        # 3. UPDATE TRAILING STOP
        if current_pnl_pct >= self.trailing_activation_pct:
            if not exit_level.trailing_stop_active:
                exit_level.trailing_stop_active = True
                logger.info(f"🔄 Trailing Stop activé pour {symbol} à +{current_pnl_pct*100:.1f}%")
            
            # Mettre à jour le plus haut
            if current_price > exit_level.highest_price_seen:
                exit_level.highest_price_seen = current_price
                self.highest_prices[agent_id][symbol] = current_price
            
            # Calculer le trailing stop
            trailing_price = exit_level.highest_price_seen * (1 - self.trailing_distance_pct)
            exit_level.trailing_stop_price = trailing_price
            
            # 4. CHECK TRAILING STOP
            if current_price <= trailing_price:
                return ExitSignal(
                    should_exit=True,
                    reason=ExitReason.TRAILING_STOP,
                    urgency="HIGH",
                    current_pnl_pct=current_pnl_pct,
                    message=f"🔄 TRAILING STOP déclenché! Prix ${current_price:.2f} <= ${trailing_price:.2f} (depuis high ${exit_level.highest_price_seen:.2f})"
                )
        
        # 5. CHECK TIME EXIT
        holding_days = (datetime.now() - exit_level.entry_time).days
        if holding_days >= self.max_holding_days:
            if abs(current_pnl_pct) < self.stagnation_threshold_pct:
                return ExitSignal(
                    should_exit=True,
                    reason=ExitReason.TIME_EXIT,
                    urgency="MEDIUM",
                    current_pnl_pct=current_pnl_pct,
                    message=f"⏰ TIME EXIT: Position stagnante depuis {holding_days} jours ({current_pnl_pct*100:.1f}%)"
                )
        
        # 6. CHECK SIGNAL EXIT (Smart Money devient très bearish)
        if smart_money_signal == "STRONG_BEARISH" and current_pnl_pct > 0:
            return ExitSignal(
                should_exit=True,
                reason=ExitReason.SIGNAL_EXIT,
                urgency="MEDIUM",
                current_pnl_pct=current_pnl_pct,
                message=f"⚠️ SIGNAL EXIT: Smart Money très bearish, protection des gains (+{current_pnl_pct*100:.1f}%)"
            )
        
        # Pas de sortie nécessaire
        return ExitSignal(
            should_exit=False,
            reason=ExitReason.MANUAL,
            urgency="LOW",
            current_pnl_pct=current_pnl_pct,
            message=f"Position OK: {current_pnl_pct*100:+.1f}%, SL à ${exit_level.stop_loss_price:.2f}, TP à ${exit_level.take_profit_price:.2f}"
        )
    
    def remove_position(self, agent_id: str, symbol: str):
        """Supprime les niveaux de sortie quand une position est fermée."""
        if agent_id in self.position_exits and symbol in self.position_exits[agent_id]:
            del self.position_exits[agent_id][symbol]
            if agent_id in self.highest_prices and symbol in self.highest_prices[agent_id]:
                del self.highest_prices[agent_id][symbol]
            logger.info(f"🗑️ Exit levels supprimés pour {symbol}")
    
    def get_all_positions_status(self, agent_id: str) -> Dict[str, Dict]:
        """Retourne le statut de toutes les positions d'un agent."""
        if agent_id not in self.position_exits:
            return {}
        
        status = {}
        for symbol, exit_level in self.position_exits[agent_id].items():
            status[symbol] = {
                "stop_loss_price": exit_level.stop_loss_price,
                "stop_loss_pct": exit_level.stop_loss_pct,
                "take_profit_price": exit_level.take_profit_price,
                "take_profit_pct": exit_level.take_profit_pct,
                "trailing_stop_active": exit_level.trailing_stop_active,
                "trailing_stop_price": exit_level.trailing_stop_price,
                "highest_price_seen": exit_level.highest_price_seen,
                "entry_time": exit_level.entry_time.isoformat(),
                "holding_days": (datetime.now() - exit_level.entry_time).days,
            }
        
        return status
    
    def format_exit_levels_for_agent(self, agent_id: str) -> str:
        """Formate les niveaux de sortie pour inclusion dans le prompt."""
        status = self.get_all_positions_status(agent_id)
        
        if not status:
            return ""
        
        lines = [
            "\n## 🎯 NIVEAUX DE SORTIE DE TES POSITIONS",
            "Tu DOIS respecter ces niveaux automatiquement!",
            ""
        ]
        
        for symbol, data in status.items():
            lines.append(f"**{symbol}:**")
            lines.append(f"  - 🔴 Stop-Loss: ${data['stop_loss_price']:.2f} (-{data['stop_loss_pct']*100:.1f}%)")
            lines.append(f"  - 🟢 Take-Profit: ${data['take_profit_price']:.2f} (+{data['take_profit_pct']*100:.1f}%)")
            
            if data['trailing_stop_active']:
                lines.append(f"  - 🔄 Trailing Stop: ${data['trailing_stop_price']:.2f} (depuis high ${data['highest_price_seen']:.2f})")
            
            lines.append(f"  - ⏱️ En position depuis: {data['holding_days']} jour(s)")
            lines.append("")
        
        lines.extend([
            "**⚠️ RÈGLES CRITIQUES:**",
            "- Si le prix atteint un niveau, tu DOIS sortir immédiatement",
            "- Ne désactive JAMAIS un stop-loss manuellement",
            "- Laisse courir les gains (trailing stop protège)",
        ])
        
        return "\n".join(lines)
    
    def _build_exit_reasoning(
        self,
        entry_price: float,
        sl_pct: float,
        tp_pct: float,
        vix: float,
        confidence: int,
        smart_signal: str,
    ) -> str:
        """Construit l'explication des niveaux de sortie."""
        return (
            f"Entrée: ${entry_price:.2f} | "
            f"SL: -{sl_pct*100:.1f}% (VIX={vix}, Conf={confidence}%) | "
            f"TP: +{tp_pct*100:.1f}% (Signal={smart_signal}) | "
            f"Trailing activé à +{self.trailing_activation_pct*100}%"
        )


# Instance globale
exit_strategy_manager = ExitStrategyManager()

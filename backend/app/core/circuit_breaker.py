"""
Circuit Breaker - Protection contre les pertes excessives.
Arrête automatiquement le trading en cas de drawdown.

RÈGLES DE PROTECTION:
1. Daily Loss Limit: -5% du capital → pause 24h
2. Weekly Loss Limit: -10% du capital → pause 7 jours
3. Monthly Loss Limit: -15% du capital → review obligatoire
4. Consecutive Losses: 5 pertes consécutives → pause 4h
5. Win Streak Bonus: 5 gains consécutifs → peut augmenter sizing
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class BreakerStatus(Enum):
    """État du circuit breaker."""
    ACTIVE = "ACTIVE"  # Trading autorisé
    PAUSED_DAILY = "PAUSED_DAILY"  # Pause 24h
    PAUSED_WEEKLY = "PAUSED_WEEKLY"  # Pause 7j
    PAUSED_CONSECUTIVE = "PAUSED_CONSECUTIVE"  # Pause après pertes consécutives
    REVIEW_REQUIRED = "REVIEW_REQUIRED"  # Review manuelle nécessaire
    

@dataclass
class AgentBreakerState:
    """État du circuit breaker pour un agent."""
    status: BreakerStatus = BreakerStatus.ACTIVE
    pause_until: Optional[datetime] = None
    pause_reason: str = ""
    
    # Historique du jour
    daily_start_capital: float = 0
    daily_pnl: float = 0
    daily_trades: int = 0
    
    # Historique de la semaine
    weekly_start_capital: float = 0
    weekly_pnl: float = 0
    
    # Streak tracking
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    last_results: deque = field(default_factory=lambda: deque(maxlen=10))
    
    # Bonuses/Malus
    sizing_multiplier: float = 1.0  # Ajuste le Kelly
    
    # Timestamps
    last_trade_time: Optional[datetime] = None
    last_reset_daily: Optional[datetime] = None
    last_reset_weekly: Optional[datetime] = None


class CircuitBreaker:
    """
    Circuit Breaker pour protéger contre les pertes excessives.
    Pause automatiquement le trading si les limites sont atteintes.
    """
    
    def __init__(self):
        self._initialized = False
        
        # === LIMITES DE PERTES ===
        self.daily_loss_limit = 0.05  # -5% par jour
        self.weekly_loss_limit = 0.10  # -10% par semaine
        self.monthly_loss_limit = 0.15  # -15% par mois
        
        # === PAUSE DURATIONS ===
        self.pause_daily_hours = 24
        self.pause_weekly_days = 7
        self.pause_consecutive_hours = 4
        
        # === STREAK LIMITS ===
        self.max_consecutive_losses = 5  # Pause après 5 pertes
        self.win_streak_bonus_threshold = 5  # Bonus après 5 gains
        
        # === STREAK MULTIPLIERS ===
        self.loss_streak_multiplier = 0.7  # Réduit sizing de 30% après streak perdant
        self.win_streak_multiplier = 1.2  # Augmente sizing de 20% après streak gagnant
        
        # === STATE TRACKING ===
        self.agent_states: Dict[str, AgentBreakerState] = {}
    
    def initialize(self) -> bool:
        """Initialise le circuit breaker."""
        self._initialized = True
        logger.info("✅ Circuit Breaker initialisé")
        logger.info(f"   📉 Limite journalière: -{self.daily_loss_limit*100}%")
        logger.info(f"   📉 Limite hebdomadaire: -{self.weekly_loss_limit*100}%")
        logger.info(f"   🔢 Max pertes consécutives: {self.max_consecutive_losses}")
        return True
    
    def get_or_create_state(self, agent_id: str, initial_capital: float) -> AgentBreakerState:
        """Récupère ou crée l'état d'un agent."""
        if agent_id not in self.agent_states:
            state = AgentBreakerState(
                daily_start_capital=initial_capital,
                weekly_start_capital=initial_capital,
                last_reset_daily=datetime.now(),
                last_reset_weekly=datetime.now(),
            )
            self.agent_states[agent_id] = state
        
        return self.agent_states[agent_id]
    
    def _reset_daily_if_needed(self, state: AgentBreakerState, current_capital: float):
        """Reset les compteurs journaliers si nouveau jour."""
        now = datetime.now()
        if state.last_reset_daily is None or state.last_reset_daily.date() < now.date():
            state.daily_start_capital = current_capital
            state.daily_pnl = 0
            state.daily_trades = 0
            state.last_reset_daily = now
            logger.info(f"🔄 Reset journalier: Capital de départ ${current_capital:.2f}")
    
    def _reset_weekly_if_needed(self, state: AgentBreakerState, current_capital: float):
        """Reset les compteurs hebdomadaires si nouvelle semaine."""
        now = datetime.now()
        if state.last_reset_weekly is None:
            state.last_reset_weekly = now
            state.weekly_start_capital = current_capital
            return
        
        # Nouvelle semaine si lundi et dernière update pas cette semaine
        days_since_reset = (now - state.last_reset_weekly).days
        if days_since_reset >= 7:
            state.weekly_start_capital = current_capital
            state.weekly_pnl = 0
            state.last_reset_weekly = now
            logger.info(f"🔄 Reset hebdomadaire: Capital de départ ${current_capital:.2f}")
    
    def can_trade(self, agent_id: str, current_capital: float) -> Tuple[bool, str]:
        """
        Vérifie si un agent peut trader.
        
        Args:
            agent_id: ID de l'agent
            current_capital: Capital actuel
        
        Returns:
            (can_trade, reason)
        """
        state = self.get_or_create_state(agent_id, current_capital)
        
        # Reset si nouveau jour/semaine
        self._reset_daily_if_needed(state, current_capital)
        self._reset_weekly_if_needed(state, current_capital)
        
        # Vérifier si pause encore active
        if state.status != BreakerStatus.ACTIVE:
            if state.pause_until and datetime.now() < state.pause_until:
                remaining = state.pause_until - datetime.now()
                return False, f"⏸️ Trading en pause jusqu'à {state.pause_until.strftime('%Y-%m-%d %H:%M')} ({state.pause_reason}). Reste: {remaining}"
            else:
                # Pause terminée, réactiver
                self._reactivate_trading(state)
        
        # Calculer les pertes actuelles
        daily_loss_pct = self._calculate_daily_loss_pct(state, current_capital)
        weekly_loss_pct = self._calculate_weekly_loss_pct(state, current_capital)
        
        # CHECK 1: Limite journalière
        if daily_loss_pct >= self.daily_loss_limit:
            self._trigger_pause(
                state, 
                BreakerStatus.PAUSED_DAILY, 
                timedelta(hours=self.pause_daily_hours),
                f"Perte journalière -{daily_loss_pct*100:.1f}% >= -{self.daily_loss_limit*100}%"
            )
            return False, f"🚨 Circuit Breaker DAILY activé: -{daily_loss_pct*100:.1f}% de perte aujourd'hui"
        
        # CHECK 2: Limite hebdomadaire
        if weekly_loss_pct >= self.weekly_loss_limit:
            self._trigger_pause(
                state,
                BreakerStatus.PAUSED_WEEKLY,
                timedelta(days=self.pause_weekly_days),
                f"Perte hebdomadaire -{weekly_loss_pct*100:.1f}% >= -{self.weekly_loss_limit*100}%"
            )
            return False, f"🚨 Circuit Breaker WEEKLY activé: -{weekly_loss_pct*100:.1f}% de perte cette semaine"
        
        # CHECK 3: Pertes consécutives
        if state.consecutive_losses >= self.max_consecutive_losses:
            self._trigger_pause(
                state,
                BreakerStatus.PAUSED_CONSECUTIVE,
                timedelta(hours=self.pause_consecutive_hours),
                f"{state.consecutive_losses} pertes consécutives"
            )
            return False, f"🚨 Circuit Breaker CONSECUTIVE activé: {state.consecutive_losses} pertes d'affilée"
        
        return True, "✅ Trading autorisé"
    
    def _calculate_daily_loss_pct(self, state: AgentBreakerState, current_capital: float) -> float:
        """Calcule le pourcentage de perte journalière."""
        if state.daily_start_capital <= 0:
            return 0
        return max(0, (state.daily_start_capital - current_capital) / state.daily_start_capital)
    
    def _calculate_weekly_loss_pct(self, state: AgentBreakerState, current_capital: float) -> float:
        """Calcule le pourcentage de perte hebdomadaire."""
        if state.weekly_start_capital <= 0:
            return 0
        return max(0, (state.weekly_start_capital - current_capital) / state.weekly_start_capital)
    
    def _trigger_pause(
        self,
        state: AgentBreakerState,
        status: BreakerStatus,
        duration: timedelta,
        reason: str,
    ):
        """Déclenche une pause de trading."""
        state.status = status
        state.pause_until = datetime.now() + duration
        state.pause_reason = reason
        
        logger.warning(f"🚨 CIRCUIT BREAKER: {reason}")
        logger.warning(f"   Pause jusqu'à: {state.pause_until}")
    
    def _reactivate_trading(self, state: AgentBreakerState):
        """Réactive le trading après une pause."""
        logger.info(f"✅ Circuit Breaker: Pause terminée, trading réactivé")
        state.status = BreakerStatus.ACTIVE
        state.pause_until = None
        state.pause_reason = ""
        
        # Reset le streak de pertes après pause
        state.consecutive_losses = 0
    
    def record_trade_result(
        self,
        agent_id: str,
        pnl: float,
        current_capital: float,
    ) -> Dict[str, Any]:
        """
        Enregistre le résultat d'un trade et met à jour les streaks.
        
        Args:
            agent_id: ID de l'agent
            pnl: Profit/Perte du trade
            current_capital: Capital après le trade
        
        Returns:
            Dict avec sizing_multiplier et autres infos
        """
        state = self.get_or_create_state(agent_id, current_capital)
        
        # Reset si nouveau jour
        self._reset_daily_if_needed(state, current_capital + abs(pnl))  # Avant le trade
        
        # Mise à jour PnL
        state.daily_pnl += pnl
        state.weekly_pnl += pnl
        state.daily_trades += 1
        state.last_trade_time = datetime.now()
        
        # Mise à jour des streaks
        is_win = pnl > 0
        state.last_results.append(is_win)
        
        if is_win:
            state.consecutive_wins += 1
            state.consecutive_losses = 0
            
            # Bonus si win streak
            if state.consecutive_wins >= self.win_streak_bonus_threshold:
                state.sizing_multiplier = self.win_streak_multiplier
                logger.info(f"🔥 Win streak! {state.consecutive_wins} gains consécutifs - Sizing x{self.win_streak_multiplier}")
        else:
            state.consecutive_losses += 1
            state.consecutive_wins = 0
            
            # Malus si loss streak
            if state.consecutive_losses >= 3:
                state.sizing_multiplier = self.loss_streak_multiplier
                logger.warning(f"⚠️ Loss streak: {state.consecutive_losses} pertes - Sizing réduit x{self.loss_streak_multiplier}")
        
        return {
            "daily_pnl": state.daily_pnl,
            "weekly_pnl": state.weekly_pnl,
            "consecutive_wins": state.consecutive_wins,
            "consecutive_losses": state.consecutive_losses,
            "sizing_multiplier": state.sizing_multiplier,
            "can_continue": state.status == BreakerStatus.ACTIVE,
        }
    
    def get_sizing_multiplier(self, agent_id: str, current_capital: float) -> float:
        """
        Retourne le multiplicateur de sizing basé sur les streaks.
        À utiliser avec Kelly Calculator.
        """
        state = self.get_or_create_state(agent_id, current_capital)
        return state.sizing_multiplier
    
    def get_agent_status(self, agent_id: str, current_capital: float) -> Dict[str, Any]:
        """Retourne le statut complet d'un agent."""
        state = self.get_or_create_state(agent_id, current_capital)
        
        daily_loss_pct = self._calculate_daily_loss_pct(state, current_capital)
        weekly_loss_pct = self._calculate_weekly_loss_pct(state, current_capital)
        
        return {
            "status": state.status.value,
            "can_trade": state.status == BreakerStatus.ACTIVE,
            "pause_until": state.pause_until.isoformat() if state.pause_until else None,
            "pause_reason": state.pause_reason,
            "daily_loss_pct": daily_loss_pct,
            "daily_loss_limit": self.daily_loss_limit,
            "daily_loss_remaining": max(0, self.daily_loss_limit - daily_loss_pct),
            "weekly_loss_pct": weekly_loss_pct,
            "weekly_loss_limit": self.weekly_loss_limit,
            "weekly_loss_remaining": max(0, self.weekly_loss_limit - weekly_loss_pct),
            "consecutive_wins": state.consecutive_wins,
            "consecutive_losses": state.consecutive_losses,
            "sizing_multiplier": state.sizing_multiplier,
            "daily_trades": state.daily_trades,
        }
    
    def format_breaker_status_for_agent(self, agent_id: str, current_capital: float) -> str:
        """Formate le statut pour inclusion dans le prompt."""
        status = self.get_agent_status(agent_id, current_capital)
        
        lines = [
            "\n## ⚡ CIRCUIT BREAKER STATUS",
            ""
        ]
        
        # Statut global
        if status["can_trade"]:
            lines.append("✅ **Trading AUTORISÉ**")
        else:
            lines.append(f"🚨 **Trading EN PAUSE** - {status['pause_reason']}")
            lines.append(f"   Reprend: {status['pause_until']}")
            return "\n".join(lines)
        
        # Pertes journalières
        daily_remaining = status["daily_loss_remaining"]
        lines.append(f"\n📅 **Limite Journalière:** -{status['daily_loss_pct']*100:.1f}% / -{status['daily_loss_limit']*100}%")
        lines.append(f"   Marge restante: -{daily_remaining*100:.1f}%")
        
        if daily_remaining < 0.02:
            lines.append("   ⚠️ ATTENTION: Proche de la limite!")
        
        # Pertes hebdomadaires
        weekly_remaining = status["weekly_loss_remaining"]
        lines.append(f"\n📆 **Limite Hebdomadaire:** -{status['weekly_loss_pct']*100:.1f}% / -{status['weekly_loss_limit']*100}%")
        
        # Streaks
        if status["consecutive_wins"] > 0:
            lines.append(f"\n🔥 **Win Streak:** {status['consecutive_wins']} gains consécutifs")
            if status["sizing_multiplier"] > 1:
                lines.append(f"   Bonus sizing: x{status['sizing_multiplier']}")
        
        if status["consecutive_losses"] > 0:
            lines.append(f"\n⚠️ **Loss Streak:** {status['consecutive_losses']} pertes consécutives")
            if status["consecutive_losses"] >= 3:
                lines.append(f"   Malus sizing: x{status['sizing_multiplier']}")
            lines.append(f"   Reste {self.max_consecutive_losses - status['consecutive_losses']} pertes avant pause")
        
        return "\n".join(lines)
    
    def reset_agent(self, agent_id: str, capital: float):
        """Reset complet de l'état d'un agent."""
        if agent_id in self.agent_states:
            del self.agent_states[agent_id]
        self.get_or_create_state(agent_id, capital)
        logger.info(f"🔄 Circuit Breaker reset pour agent {agent_id}")


# Instance globale
circuit_breaker = CircuitBreaker()

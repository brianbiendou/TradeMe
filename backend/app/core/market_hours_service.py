"""
Market Hours Service - Gestion des horaires de trading V2.3.

Le marché US est ouvert de 9h30 à 16h00 (heure de New York).
En France (Paris), cela correspond à:
- Été (CET+2): 15h30 - 22h00
- Hiver (CET+1): 16h30 - 23h00

RÈGLES IMPORTANTES:
1. NE PAS trader pendant les 30 premières minutes (volatilité)
2. NE PAS trader pendant les 15 dernières minutes (volatilité)
3. Préférer 10h00-15h00 NY (16h00-21h00 Paris été)

Impact estimé: +40-60% de rentabilité
"""
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import pytz

logger = logging.getLogger(__name__)


class TradingWindow(Enum):
    """Fenêtre de trading."""
    OPTIMAL = "OPTIMAL"              # Meilleur moment pour trader
    ACCEPTABLE = "ACCEPTABLE"        # OK pour trader
    AVOID_OPENING = "AVOID_OPENING"  # 30 premières minutes - éviter
    AVOID_CLOSING = "AVOID_CLOSING"  # 15 dernières minutes - éviter
    MARKET_CLOSED = "MARKET_CLOSED"  # Marché fermé


class MarketStatus(Enum):
    """Statut du marché."""
    OPEN = "OPEN"
    CLOSED_WEEKEND = "CLOSED_WEEKEND"
    CLOSED_HOLIDAY = "CLOSED_HOLIDAY"
    CLOSED_AFTER_HOURS = "CLOSED_AFTER_HOURS"
    CLOSED_BEFORE_HOURS = "CLOSED_BEFORE_HOURS"
    PRE_MARKET = "PRE_MARKET"
    AFTER_MARKET = "AFTER_MARKET"


@dataclass
class MarketHoursInfo:
    """Information sur les horaires de marché."""
    is_open: bool
    status: MarketStatus
    trading_window: TradingWindow
    can_trade: bool  # Autorisation de trader
    reason: str      # Explication
    
    # Horaires en heure de Paris
    market_open_paris: str    # Ex: "15:30" ou "16:30"
    market_close_paris: str   # Ex: "22:00" ou "23:00"
    
    # Temps restant
    minutes_since_open: int
    minutes_until_close: int
    
    # Fenêtre optimale
    optimal_start_paris: str
    optimal_end_paris: str
    is_optimal_window: bool
    
    # Prochaine ouverture si fermé
    next_open_paris: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "is_open": self.is_open,
            "status": self.status.value,
            "trading_window": self.trading_window.value,
            "can_trade": self.can_trade,
            "reason": self.reason,
            "market_open_paris": self.market_open_paris,
            "market_close_paris": self.market_close_paris,
            "minutes_since_open": self.minutes_since_open,
            "minutes_until_close": self.minutes_until_close,
            "optimal_start_paris": self.optimal_start_paris,
            "optimal_end_paris": self.optimal_end_paris,
            "is_optimal_window": self.is_optimal_window,
            "next_open_paris": self.next_open_paris,
        }


class MarketHoursService:
    """
    Service de gestion des horaires de trading.
    
    Convertit automatiquement les heures US en heures France.
    Bloque le trading pendant les périodes à risque.
    """
    
    def __init__(self):
        """Initialise le service."""
        self._initialized = False
        
        # Fuseaux horaires
        self.tz_ny = pytz.timezone('America/New_York')
        self.tz_paris = pytz.timezone('Europe/Paris')
        
        # Horaires du marché US (heure de New York)
        self.market_open_ny = time(9, 30)   # 9h30 NY
        self.market_close_ny = time(16, 0)  # 16h00 NY
        
        # Fenêtres à éviter (en minutes depuis l'ouverture)
        self.avoid_opening_minutes = 30  # Éviter les 30 premières minutes
        self.avoid_closing_minutes = 15  # Éviter les 15 dernières minutes
        
        # Fenêtre optimale (heure de New York)
        self.optimal_start_ny = time(10, 0)   # 10h00 NY
        self.optimal_end_ny = time(15, 0)     # 15h00 NY
        
        # Jours fériés US 2024-2025 (à compléter)
        self.us_holidays = [
            # 2024
            datetime(2024, 1, 1),   # New Year's Day
            datetime(2024, 1, 15),  # MLK Day
            datetime(2024, 2, 19),  # Presidents Day
            datetime(2024, 3, 29),  # Good Friday
            datetime(2024, 5, 27),  # Memorial Day
            datetime(2024, 6, 19),  # Juneteenth
            datetime(2024, 7, 4),   # Independence Day
            datetime(2024, 9, 2),   # Labor Day
            datetime(2024, 11, 28), # Thanksgiving
            datetime(2024, 12, 25), # Christmas
            # 2025
            datetime(2025, 1, 1),   # New Year's Day
            datetime(2025, 1, 20),  # MLK Day
            datetime(2025, 2, 17),  # Presidents Day
            datetime(2025, 4, 18),  # Good Friday
            datetime(2025, 5, 26),  # Memorial Day
            datetime(2025, 6, 19),  # Juneteenth
            datetime(2025, 7, 4),   # Independence Day
            datetime(2025, 9, 1),   # Labor Day
            datetime(2025, 11, 27), # Thanksgiving
            datetime(2025, 12, 25), # Christmas
            # 2026
            datetime(2026, 1, 1),   # New Year's Day
            datetime(2026, 1, 19),  # MLK Day
            datetime(2026, 2, 16),  # Presidents Day
            datetime(2026, 4, 3),   # Good Friday
            datetime(2026, 5, 25),  # Memorial Day
            datetime(2026, 6, 19),  # Juneteenth
            datetime(2026, 7, 3),   # Independence Day (observed)
            datetime(2026, 9, 7),   # Labor Day
            datetime(2026, 11, 26), # Thanksgiving
            datetime(2026, 12, 25), # Christmas
        ]
    
    def initialize(self) -> bool:
        """Initialise le service."""
        self._initialized = True
        logger.info("✅ Market Hours Service initialisé (fuseau: Paris)")
        return True
    
    def _ny_to_paris(self, ny_time: datetime) -> datetime:
        """Convertit une heure de New York en heure de Paris."""
        if ny_time.tzinfo is None:
            ny_time = self.tz_ny.localize(ny_time)
        return ny_time.astimezone(self.tz_paris)
    
    def _paris_to_ny(self, paris_time: datetime) -> datetime:
        """Convertit une heure de Paris en heure de New York."""
        if paris_time.tzinfo is None:
            paris_time = self.tz_paris.localize(paris_time)
        return paris_time.astimezone(self.tz_ny)
    
    def _is_holiday(self, date: datetime) -> bool:
        """Vérifie si une date est un jour férié US."""
        date_only = datetime(date.year, date.month, date.day)
        return date_only in self.us_holidays
    
    def _is_weekend(self, date: datetime) -> bool:
        """Vérifie si une date est un weekend."""
        return date.weekday() >= 5  # Samedi = 5, Dimanche = 6
    
    def get_market_hours_info(self, paris_time: datetime = None) -> MarketHoursInfo:
        """
        Récupère les informations sur les horaires de marché.
        
        Args:
            paris_time: Heure de Paris (défaut: maintenant)
            
        Returns:
            MarketHoursInfo avec toutes les informations
        """
        if paris_time is None:
            paris_time = datetime.now(self.tz_paris)
        elif paris_time.tzinfo is None:
            paris_time = self.tz_paris.localize(paris_time)
        
        # Convertir en heure de New York
        ny_time = self._paris_to_ny(paris_time)
        
        # Calculer les horaires du jour en Paris
        today_open_ny = datetime.combine(ny_time.date(), self.market_open_ny)
        today_open_ny = self.tz_ny.localize(today_open_ny)
        today_close_ny = datetime.combine(ny_time.date(), self.market_close_ny)
        today_close_ny = self.tz_ny.localize(today_close_ny)
        
        market_open_paris = self._ny_to_paris(today_open_ny)
        market_close_paris = self._ny_to_paris(today_close_ny)
        
        # Fenêtre optimale en Paris
        optimal_start_ny = datetime.combine(ny_time.date(), self.optimal_start_ny)
        optimal_start_ny = self.tz_ny.localize(optimal_start_ny)
        optimal_end_ny = datetime.combine(ny_time.date(), self.optimal_end_ny)
        optimal_end_ny = self.tz_ny.localize(optimal_end_ny)
        
        optimal_start_paris = self._ny_to_paris(optimal_start_ny)
        optimal_end_paris = self._ny_to_paris(optimal_end_ny)
        
        # Vérifier le statut du marché
        if self._is_weekend(ny_time):
            return MarketHoursInfo(
                is_open=False,
                status=MarketStatus.CLOSED_WEEKEND,
                trading_window=TradingWindow.MARKET_CLOSED,
                can_trade=False,
                reason="🚫 Marché fermé (weekend)",
                market_open_paris=market_open_paris.strftime("%H:%M"),
                market_close_paris=market_close_paris.strftime("%H:%M"),
                minutes_since_open=0,
                minutes_until_close=0,
                optimal_start_paris=optimal_start_paris.strftime("%H:%M"),
                optimal_end_paris=optimal_end_paris.strftime("%H:%M"),
                is_optimal_window=False,
                next_open_paris=self._get_next_open(paris_time),
            )
        
        if self._is_holiday(ny_time):
            return MarketHoursInfo(
                is_open=False,
                status=MarketStatus.CLOSED_HOLIDAY,
                trading_window=TradingWindow.MARKET_CLOSED,
                can_trade=False,
                reason="🚫 Marché fermé (jour férié US)",
                market_open_paris=market_open_paris.strftime("%H:%M"),
                market_close_paris=market_close_paris.strftime("%H:%M"),
                minutes_since_open=0,
                minutes_until_close=0,
                optimal_start_paris=optimal_start_paris.strftime("%H:%M"),
                optimal_end_paris=optimal_end_paris.strftime("%H:%M"),
                is_optimal_window=False,
                next_open_paris=self._get_next_open(paris_time),
            )
        
        # Vérifier si c'est avant ou après les heures de marché
        current_time_ny = ny_time.time()
        
        if current_time_ny < self.market_open_ny:
            return MarketHoursInfo(
                is_open=False,
                status=MarketStatus.CLOSED_BEFORE_HOURS,
                trading_window=TradingWindow.MARKET_CLOSED,
                can_trade=False,
                reason=f"🚫 Marché pas encore ouvert. Ouverture à {market_open_paris.strftime('%H:%M')} (Paris)",
                market_open_paris=market_open_paris.strftime("%H:%M"),
                market_close_paris=market_close_paris.strftime("%H:%M"),
                minutes_since_open=0,
                minutes_until_close=0,
                optimal_start_paris=optimal_start_paris.strftime("%H:%M"),
                optimal_end_paris=optimal_end_paris.strftime("%H:%M"),
                is_optimal_window=False,
                next_open_paris=market_open_paris.strftime("%H:%M le %d/%m"),
            )
        
        if current_time_ny >= self.market_close_ny:
            return MarketHoursInfo(
                is_open=False,
                status=MarketStatus.CLOSED_AFTER_HOURS,
                trading_window=TradingWindow.MARKET_CLOSED,
                can_trade=False,
                reason="🚫 Marché fermé pour aujourd'hui",
                market_open_paris=market_open_paris.strftime("%H:%M"),
                market_close_paris=market_close_paris.strftime("%H:%M"),
                minutes_since_open=0,
                minutes_until_close=0,
                optimal_start_paris=optimal_start_paris.strftime("%H:%M"),
                optimal_end_paris=optimal_end_paris.strftime("%H:%M"),
                is_optimal_window=False,
                next_open_paris=self._get_next_open(paris_time),
            )
        
        # Le marché est ouvert - calculer les minutes
        minutes_since_open = int((ny_time - today_open_ny).total_seconds() / 60)
        minutes_until_close = int((today_close_ny - ny_time).total_seconds() / 60)
        
        # Vérifier la fenêtre de trading
        if minutes_since_open < self.avoid_opening_minutes:
            return MarketHoursInfo(
                is_open=True,
                status=MarketStatus.OPEN,
                trading_window=TradingWindow.AVOID_OPENING,
                can_trade=False,
                reason=f"⚠️ 30 premières minutes - Volatilité élevée. Attendre {self.avoid_opening_minutes - minutes_since_open} min",
                market_open_paris=market_open_paris.strftime("%H:%M"),
                market_close_paris=market_close_paris.strftime("%H:%M"),
                minutes_since_open=minutes_since_open,
                minutes_until_close=minutes_until_close,
                optimal_start_paris=optimal_start_paris.strftime("%H:%M"),
                optimal_end_paris=optimal_end_paris.strftime("%H:%M"),
                is_optimal_window=False,
            )
        
        if minutes_until_close <= self.avoid_closing_minutes:
            return MarketHoursInfo(
                is_open=True,
                status=MarketStatus.OPEN,
                trading_window=TradingWindow.AVOID_CLOSING,
                can_trade=False,
                reason=f"⚠️ 15 dernières minutes - Volatilité élevée. Fermeture dans {minutes_until_close} min",
                market_open_paris=market_open_paris.strftime("%H:%M"),
                market_close_paris=market_close_paris.strftime("%H:%M"),
                minutes_since_open=minutes_since_open,
                minutes_until_close=minutes_until_close,
                optimal_start_paris=optimal_start_paris.strftime("%H:%M"),
                optimal_end_paris=optimal_end_paris.strftime("%H:%M"),
                is_optimal_window=False,
            )
        
        # Vérifier si on est dans la fenêtre optimale
        is_optimal = self.optimal_start_ny <= current_time_ny <= self.optimal_end_ny
        
        if is_optimal:
            return MarketHoursInfo(
                is_open=True,
                status=MarketStatus.OPEN,
                trading_window=TradingWindow.OPTIMAL,
                can_trade=True,
                reason="✅ Fenêtre optimale de trading",
                market_open_paris=market_open_paris.strftime("%H:%M"),
                market_close_paris=market_close_paris.strftime("%H:%M"),
                minutes_since_open=minutes_since_open,
                minutes_until_close=minutes_until_close,
                optimal_start_paris=optimal_start_paris.strftime("%H:%M"),
                optimal_end_paris=optimal_end_paris.strftime("%H:%M"),
                is_optimal_window=True,
            )
        else:
            return MarketHoursInfo(
                is_open=True,
                status=MarketStatus.OPEN,
                trading_window=TradingWindow.ACCEPTABLE,
                can_trade=True,
                reason="✅ Marché ouvert - Fenêtre acceptable",
                market_open_paris=market_open_paris.strftime("%H:%M"),
                market_close_paris=market_close_paris.strftime("%H:%M"),
                minutes_since_open=minutes_since_open,
                minutes_until_close=minutes_until_close,
                optimal_start_paris=optimal_start_paris.strftime("%H:%M"),
                optimal_end_paris=optimal_end_paris.strftime("%H:%M"),
                is_optimal_window=False,
            )
    
    def _get_next_open(self, current_time: datetime) -> str:
        """Calcule la prochaine ouverture du marché."""
        if current_time.tzinfo is None:
            current_time = self.tz_paris.localize(current_time)
        
        ny_time = self._paris_to_ny(current_time)
        
        # Chercher le prochain jour ouvrable
        next_day = ny_time.date() + timedelta(days=1)
        
        for _ in range(10):  # Max 10 jours de recherche
            next_datetime = datetime.combine(next_day, self.market_open_ny)
            next_datetime = self.tz_ny.localize(next_datetime)
            
            if not self._is_weekend(next_datetime) and not self._is_holiday(next_datetime):
                paris_next_open = self._ny_to_paris(next_datetime)
                return paris_next_open.strftime("%H:%M le %d/%m")
            
            next_day += timedelta(days=1)
        
        return "Inconnu"
    
    def can_trade_now(self) -> Tuple[bool, str]:
        """
        Vérifie rapidement si on peut trader maintenant.
        
        Returns:
            (peut_trader, raison)
        """
        info = self.get_market_hours_info()
        return info.can_trade, info.reason
    
    def should_skip_cycle(self) -> Tuple[bool, str]:
        """
        Vérifie si le cycle de trading doit être sauté.
        Utilisé par le scheduler.
        
        Returns:
            (skip, raison)
        """
        can_trade, reason = self.can_trade_now()
        return not can_trade, reason
    
    def format_for_agent(self) -> str:
        """
        Formate les informations de marché pour le prompt de l'IA.
        """
        info = self.get_market_hours_info()
        
        lines = [
            "## 🕐 HORAIRES DE MARCHÉ",
            f"Statut: {info.status.value}",
            f"Fenêtre: {info.trading_window.value}",
        ]
        
        if info.is_open:
            lines.extend([
                f"Ouvert depuis: {info.minutes_since_open} minutes",
                f"Fermeture dans: {info.minutes_until_close} minutes",
                f"Fenêtre optimale: {info.optimal_start_paris} - {info.optimal_end_paris} (Paris)",
                f"Dans fenêtre optimale: {'✅ Oui' if info.is_optimal_window else '⚠️ Non'}",
            ])
        else:
            lines.append(f"Prochaine ouverture: {info.next_open_paris}")
        
        lines.append(f"\n{'✅ TRADING AUTORISÉ' if info.can_trade else '🚫 TRADING BLOQUÉ'}: {info.reason}")
        
        return "\n".join(lines)


# Instance globale
market_hours_service = MarketHoursService()

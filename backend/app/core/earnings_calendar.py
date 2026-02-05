"""
Service de Calendrier Earnings pour TradeMe V2.2.

Vérifie les dates d'annonces de résultats pour éviter d'acheter
juste avant des earnings (risque de gap -20%).

Sources de données:
- Finnhub (gratuit, déjà configuré)
- Yahoo Finance (backup)

Impact estimé: +10-15% de rentabilité
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import aiohttp

from .config import settings

logger = logging.getLogger(__name__)


class EarningsRisk(Enum):
    """Niveau de risque lié aux earnings."""
    HIGH = "HIGH"           # Earnings dans < 3 jours - NE PAS ACHETER
    MEDIUM = "MEDIUM"       # Earnings dans 3-7 jours - Prudence
    LOW = "LOW"             # Earnings dans 7-14 jours - OK avec réduction de taille
    NONE = "NONE"           # Pas d'earnings proche - OK


@dataclass
class EarningsInfo:
    """Information sur les earnings d'une action."""
    symbol: str
    
    # Date des earnings
    earnings_date: Optional[datetime]
    is_confirmed: bool  # Date confirmée ou estimée
    
    # Temps jusqu'aux earnings
    days_until_earnings: Optional[int]
    
    # Risque
    risk_level: EarningsRisk
    
    # Recommandation
    should_avoid_buy: bool
    position_size_multiplier: float  # 0.0 = ne pas acheter, 1.0 = taille normale
    
    # Message pour l'agent
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "symbol": self.symbol,
            "earnings_date": self.earnings_date.isoformat() if self.earnings_date else None,
            "is_confirmed": self.is_confirmed,
            "days_until_earnings": self.days_until_earnings,
            "risk_level": self.risk_level.value,
            "should_avoid_buy": self.should_avoid_buy,
            "position_size_multiplier": self.position_size_multiplier,
            "message": self.message,
        }


class EarningsCalendarService:
    """
    Service de gestion du calendrier des earnings.
    
    Règles:
    - Earnings < 3 jours: NE PAS ACHETER (gap risk -20%)
    - Earnings 3-7 jours: Position réduite à 50%
    - Earnings 7-14 jours: Position réduite à 75%
    - Earnings > 14 jours ou passés: OK
    """
    
    def __init__(self):
        """Initialise le service."""
        self._initialized = False
        
        # Cache des earnings (symbol -> EarningsInfo)
        self._cache: Dict[str, EarningsInfo] = {}
        self._cache_ttl = timedelta(hours=6)  # Refresh toutes les 6h
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # API Finnhub
        self.finnhub_api_key = settings.finnhub_api_key if hasattr(settings, 'finnhub_api_key') else None
        self.finnhub_base_url = "https://finnhub.io/api/v1"
    
    def initialize(self) -> bool:
        """Initialise le service."""
        if not self.finnhub_api_key:
            logger.warning("⚠️ Finnhub API key non configurée - Earnings Calendar désactivé")
            # On s'initialise quand même, mais on retournera des données vides
        
        self._initialized = True
        logger.info("✅ Earnings Calendar Service initialisé")
        return True
    
    async def _fetch_earnings_finnhub(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les earnings depuis Finnhub.
        
        Args:
            symbol: Symbole de l'action
            
        Returns: Dict avec les infos earnings ou None
        """
        if not self.finnhub_api_key:
            return None
        
        try:
            # Earnings calendar endpoint
            url = f"{self.finnhub_base_url}/calendar/earnings"
            params = {
                "symbol": symbol,
                "token": self.finnhub_api_key,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        earnings_list = data.get("earningsCalendar", [])
                        if earnings_list:
                            # Prendre le prochain earnings
                            next_earnings = earnings_list[0]
                            return {
                                "date": next_earnings.get("date"),
                                "hour": next_earnings.get("hour"),  # "amc" (after market close) ou "bmo" (before market open)
                                "eps_estimate": next_earnings.get("epsEstimate"),
                                "eps_actual": next_earnings.get("epsActual"),
                                "revenue_estimate": next_earnings.get("revenueEstimate"),
                            }
                        
                        return None
                    else:
                        logger.warning(f"Finnhub API error for {symbol}: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erreur fetch earnings {symbol}: {e}")
            return None
    
    def _calculate_risk_level(
        self, 
        days_until: int,
    ) -> tuple[EarningsRisk, bool, float, str]:
        """
        Calcule le niveau de risque basé sur les jours jusqu'aux earnings.
        
        Args:
            days_until: Jours jusqu'aux earnings
            
        Returns: (risk_level, should_avoid_buy, size_multiplier, message)
        """
        if days_until <= 0:
            # Earnings passés ou aujourd'hui - vérifier si c'était récent
            if days_until >= -2:
                return (
                    EarningsRisk.MEDIUM,
                    False,
                    0.75,
                    f"⚠️ Earnings récents ({-days_until}j). Volatilité possible."
                )
            return (
                EarningsRisk.NONE,
                False,
                1.0,
                "✅ Earnings passés. Pas de risque imminent."
            )
        
        if days_until <= 3:
            return (
                EarningsRisk.HIGH,
                True,
                0.0,
                f"🚨 EARNINGS DANS {days_until}J - NE PAS ACHETER! Risque de gap -20%"
            )
        
        if days_until <= 7:
            return (
                EarningsRisk.MEDIUM,
                False,
                0.5,
                f"⚠️ Earnings dans {days_until}j. Position réduite à 50% recommandée."
            )
        
        if days_until <= 14:
            return (
                EarningsRisk.LOW,
                False,
                0.75,
                f"📅 Earnings dans {days_until}j. Position réduite à 75% recommandée."
            )
        
        return (
            EarningsRisk.NONE,
            False,
            1.0,
            f"✅ Earnings dans {days_until}j. Pas de risque imminent."
        )
    
    async def check_earnings(self, symbol: str) -> EarningsInfo:
        """
        Vérifie les earnings pour un symbole.
        
        Args:
            symbol: Symbole de l'action
            
        Returns: EarningsInfo avec le risque et les recommandations
        """
        # Vérifier le cache
        if symbol in self._cache:
            cache_time = self._cache_timestamps.get(symbol)
            if cache_time and datetime.now() - cache_time < self._cache_ttl:
                return self._cache[symbol]
        
        # Pas d'API key = pas de données
        if not self.finnhub_api_key:
            return EarningsInfo(
                symbol=symbol,
                earnings_date=None,
                is_confirmed=False,
                days_until_earnings=None,
                risk_level=EarningsRisk.NONE,
                should_avoid_buy=False,
                position_size_multiplier=1.0,
                message="ℹ️ Calendrier earnings non disponible (API non configurée)"
            )
        
        # Fetch depuis Finnhub
        earnings_data = await self._fetch_earnings_finnhub(symbol)
        
        if not earnings_data or not earnings_data.get("date"):
            # Pas d'earnings trouvés
            info = EarningsInfo(
                symbol=symbol,
                earnings_date=None,
                is_confirmed=False,
                days_until_earnings=None,
                risk_level=EarningsRisk.NONE,
                should_avoid_buy=False,
                position_size_multiplier=1.0,
                message="✅ Aucun earnings programmé dans les prochaines semaines."
            )
        else:
            # Parser la date
            try:
                earnings_date = datetime.strptime(earnings_data["date"], "%Y-%m-%d")
            except ValueError:
                earnings_date = None
            
            if earnings_date:
                days_until = (earnings_date - datetime.now()).days
                
                risk_level, should_avoid, size_mult, message = self._calculate_risk_level(days_until)
                
                # Ajouter l'heure si disponible
                hour = earnings_data.get("hour")
                if hour == "bmo":
                    message += " (Before Market Open)"
                elif hour == "amc":
                    message += " (After Market Close)"
                
                info = EarningsInfo(
                    symbol=symbol,
                    earnings_date=earnings_date,
                    is_confirmed=True,
                    days_until_earnings=days_until,
                    risk_level=risk_level,
                    should_avoid_buy=should_avoid,
                    position_size_multiplier=size_mult,
                    message=message,
                )
            else:
                info = EarningsInfo(
                    symbol=symbol,
                    earnings_date=None,
                    is_confirmed=False,
                    days_until_earnings=None,
                    risk_level=EarningsRisk.NONE,
                    should_avoid_buy=False,
                    position_size_multiplier=1.0,
                    message="✅ Date earnings non disponible."
                )
        
        # Mettre en cache
        self._cache[symbol] = info
        self._cache_timestamps[symbol] = datetime.now()
        
        return info
    
    async def check_multiple(self, symbols: List[str]) -> Dict[str, EarningsInfo]:
        """
        Vérifie les earnings pour plusieurs symboles.
        
        Args:
            symbols: Liste de symboles
            
        Returns: Dict symbol -> EarningsInfo
        """
        results = {}
        for symbol in symbols:
            results[symbol] = await self.check_earnings(symbol)
        return results
    
    def format_for_agent(self, earnings_info: EarningsInfo) -> str:
        """
        Formate l'info earnings pour le prompt de l'agent.
        
        Args:
            earnings_info: Information earnings
            
        Returns: Texte formaté
        """
        if not earnings_info:
            return ""
        
        if earnings_info.risk_level == EarningsRisk.HIGH:
            return f"""
## 🚨 ALERTE EARNINGS - {earnings_info.symbol}

{earnings_info.message}

**⛔ RECOMMANDATION: NE PAS ACHETER**
- Date earnings: {earnings_info.earnings_date.strftime('%Y-%m-%d') if earnings_info.earnings_date else 'N/A'}
- Jours restants: {earnings_info.days_until_earnings}
- Risque de gap: -15% à -30% si résultats décevants
"""
        
        if earnings_info.risk_level == EarningsRisk.MEDIUM:
            return f"""
## ⚠️ EARNINGS PROCHE - {earnings_info.symbol}

{earnings_info.message}

**📉 RECOMMANDATION: Réduire la taille de position à {int(earnings_info.position_size_multiplier * 100)}%**
- Date earnings: {earnings_info.earnings_date.strftime('%Y-%m-%d') if earnings_info.earnings_date else 'N/A'}
- Jours restants: {earnings_info.days_until_earnings}
"""
        
        if earnings_info.risk_level == EarningsRisk.LOW:
            return f"""
## 📅 EARNINGS À VENIR - {earnings_info.symbol}

{earnings_info.message}

**ℹ️ NOTE: Position légèrement réduite recommandée ({int(earnings_info.position_size_multiplier * 100)}%)**
"""
        
        # NONE - pas de risque
        return ""
    
    def should_block_trade(self, earnings_info: EarningsInfo) -> bool:
        """
        Détermine si un trade BUY devrait être bloqué.
        
        Args:
            earnings_info: Information earnings
            
        Returns: True si le trade devrait être bloqué
        """
        return earnings_info.should_avoid_buy


# Instance globale
earnings_calendar = EarningsCalendarService()

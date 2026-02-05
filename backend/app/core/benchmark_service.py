"""
Service de benchmarks pour comparer les performances des IAs.
Récupère les données historiques du S&P 500 et Berkshire Hathaway.
"""
import logging
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class BenchmarkService:
    """
    Service pour récupérer les données de benchmark.
    - S&P 500 (^GSPC) : Indice de référence du marché US
    - Berkshire Hathaway (BRK-B) : Portfolio de Warren Buffett
    """
    
    def __init__(self):
        self._initialized = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Dict] = {}
        self._cache_duration = timedelta(minutes=5)  # Cache 5 minutes
    
    def initialize(self) -> bool:
        """Initialise le service."""
        self._initialized = True
        logger.info("✅ Benchmark Service initialisé")
        return True
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Retourne une session HTTP réutilisable."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self._session
    
    async def close(self):
        """Ferme la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _is_cache_valid(self, key: str) -> bool:
        """Vérifie si le cache est encore valide."""
        if key not in self._cache:
            return False
        return datetime.now() - self._cache[key]["timestamp"] < self._cache_duration
    
    def _get_yahoo_interval_range(self, period: str) -> tuple:
        """
        Convertit une période en paramètres Yahoo Finance.
        
        Returns:
            (interval, range) pour l'API Yahoo
        """
        period_map = {
            "1h": ("5m", "1d"),
            "24h": ("15m", "1d"),
            "7d": ("1h", "5d"),
            "30d": ("1d", "1mo"),
            "3m": ("1d", "3mo"),
            "6m": ("1d", "6mo"),
            "1y": ("1d", "1y"),
            "5y": ("1wk", "5y"),
        }
        return period_map.get(period, ("1d", "1mo"))
    
    async def get_benchmark_data(
        self, 
        symbol: str, 
        period: str = "1h"
    ) -> Dict[str, Any]:
        """
        Récupère les données historiques d'un symbole.
        
        Args:
            symbol: ^GSPC (S&P 500) ou BRK-B (Berkshire)
            period: 1h, 24h, 7d, 30d, 3m, 6m, 1y, 5y
            
        Returns:
            Dict avec les données de performance
        """
        cache_key = f"{symbol}_{period}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        try:
            session = await self._get_session()
            interval, range_param = self._get_yahoo_interval_range(period)
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_param}"
            
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Erreur Yahoo Finance pour {symbol}: {response.status}")
                    return self._get_fallback_data(symbol)
                
                data = await response.json()
                result = data.get("chart", {}).get("result", [])
                
                if not result:
                    return self._get_fallback_data(symbol)
                
                chart_data = result[0]
                timestamps = chart_data.get("timestamp", [])
                quotes = chart_data.get("indicators", {}).get("quote", [{}])[0]
                closes = quotes.get("close", [])
                
                if not timestamps or not closes:
                    return self._get_fallback_data(symbol)
                
                # Calculer les performances relatives
                first_close = None
                for c in closes:
                    if c is not None:
                        first_close = c
                        break
                
                if not first_close:
                    return self._get_fallback_data(symbol)
                
                # Construire les points de données
                data_points = []
                for i, (ts, close) in enumerate(zip(timestamps, closes)):
                    if close is not None:
                        perf_pct = ((close - first_close) / first_close) * 100
                        data_points.append({
                            "time": datetime.fromtimestamp(ts).isoformat(),
                            "price": round(close, 2),
                            "performance_pct": round(perf_pct, 4),
                        })
                
                # Méta-données
                meta = chart_data.get("meta", {})
                current_price = meta.get("regularMarketPrice", closes[-1] if closes else 0)
                prev_close = meta.get("chartPreviousClose") or first_close
                
                result_data = {
                    "symbol": symbol,
                    "name": self._get_benchmark_name(symbol),
                    "period": period,
                    "current_price": round(current_price, 2) if current_price else 0,
                    "period_start_price": round(first_close, 2),
                    "total_performance_pct": round(((current_price - first_close) / first_close) * 100, 4) if first_close else 0,
                    "data_points": data_points,
                    "point_count": len(data_points),
                    "timestamp": datetime.now().isoformat(),
                }
                
                # Mettre en cache
                self._cache[cache_key] = {
                    "data": result_data,
                    "timestamp": datetime.now()
                }
                
                logger.info(f"📊 Benchmark {symbol} ({period}): {result_data['total_performance_pct']:+.2f}%")
                return result_data
                
        except Exception as e:
            logger.error(f"Erreur récupération benchmark {symbol}: {e}")
            return self._get_fallback_data(symbol)
    
    def _get_benchmark_name(self, symbol: str) -> str:
        """Retourne le nom lisible du benchmark."""
        names = {
            "^GSPC": "S&P 500",
            "BRK-B": "Berkshire (Buffett)",
            "BRK-A": "Berkshire (Buffett)",
            "QQQ": "Nasdaq 100",
            "DIA": "Dow Jones",
        }
        return names.get(symbol, symbol)
    
    def _get_fallback_data(self, symbol: str) -> Dict[str, Any]:
        """Retourne des données de fallback en cas d'erreur."""
        return {
            "symbol": symbol,
            "name": self._get_benchmark_name(symbol),
            "period": "unknown",
            "current_price": 0,
            "period_start_price": 0,
            "total_performance_pct": 0,
            "data_points": [],
            "point_count": 0,
            "timestamp": datetime.now().isoformat(),
            "error": "Data unavailable",
        }
    
    async def get_all_benchmarks(self, period: str = "1h") -> Dict[str, Any]:
        """
        Récupère tous les benchmarks pour une période donnée.
        
        Args:
            period: 1h, 24h, 7d, 30d, 3m, 6m, 1y, 5y
            
        Returns:
            Dict avec S&P 500 et Berkshire Hathaway
        """
        # Récupérer en parallèle
        import asyncio
        
        sp500_task = self.get_benchmark_data("^GSPC", period)
        berkshire_task = self.get_benchmark_data("BRK-B", period)
        
        sp500_data, berkshire_data = await asyncio.gather(
            sp500_task, 
            berkshire_task,
            return_exceptions=True
        )
        
        # Gérer les erreurs
        if isinstance(sp500_data, Exception):
            sp500_data = self._get_fallback_data("^GSPC")
        if isinstance(berkshire_data, Exception):
            berkshire_data = self._get_fallback_data("BRK-B")
        
        return {
            "sp500": sp500_data,
            "berkshire": berkshire_data,
            "period": period,
            "timestamp": datetime.now().isoformat(),
        }
    
    def format_benchmarks_for_chart(
        self, 
        benchmarks: Dict[str, Any],
        agents_data: Dict[str, List]
    ) -> Dict[str, Any]:
        """
        Formate les benchmarks pour être compatibles avec le graphique frontend.
        Aligne les timestamps avec les données des agents si possible.
        
        Args:
            benchmarks: Données des benchmarks
            agents_data: Données des agents (format existant)
            
        Returns:
            Dict formaté pour le graphique
        """
        result = {}
        
        # S&P 500
        if "sp500" in benchmarks and benchmarks["sp500"].get("data_points"):
            result["S&P 500"] = [
                {
                    "time": point["time"],
                    "capital": 10000 * (1 + point["performance_pct"] / 100),  # Simuler $10k de départ
                    "performance": point["performance_pct"],
                }
                for point in benchmarks["sp500"]["data_points"]
            ]
        
        # Berkshire
        if "berkshire" in benchmarks and benchmarks["berkshire"].get("data_points"):
            result["Buffett"] = [
                {
                    "time": point["time"],
                    "capital": 10000 * (1 + point["performance_pct"] / 100),  # Simuler $10k de départ
                    "performance": point["performance_pct"],
                }
                for point in benchmarks["berkshire"]["data_points"]
            ]
        
        return result


# Singleton
benchmark_service = BenchmarkService()

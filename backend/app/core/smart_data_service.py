"""
Smart Data Service - Données Alternatives "Smart Money" GRATUITES.
Récupère les données Dark Pool, Options Flow et Insider Trading via des sources gratuites.

Sources gratuites utilisées:
- FINRA ADF (Dark Pool volumes) via API publique
- Yahoo Finance (Options data)
- SEC EDGAR (Insider transactions - Form 4)
- CBOE (VIX, Put/Call ratios)
"""
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import json
import re

from .supabase_client import supabase_client
from .config import settings

logger = logging.getLogger(__name__)


class SmartDataService:
    """
    Service de récupération de données "Smart Money" - 100% GRATUIT.
    Agrège les données de Dark Pools, Options et Insiders.
    """
    
    def __init__(self):
        self._initialized = False
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Cache pour éviter les requêtes répétées
        self._cache: Dict[str, Dict] = {}
        self._cache_duration = timedelta(minutes=15)
    
    def initialize(self) -> bool:
        """Initialise le service."""
        self._initialized = True
        logger.info("✅ Smart Data Service initialisé")
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
    
    def _is_cache_valid(self, key: str) -> bool:
        """Vérifie si le cache est encore valide."""
        if key not in self._cache:
            return False
        return datetime.now() - self._cache[key]["timestamp"] < self._cache_duration
    
    # =====================================================
    # VIX & VOLATILITÉ (CBOE - Gratuit)
    # =====================================================
    
    async def get_vix_data(self) -> Dict[str, Any]:
        """
        Récupère le VIX actuel et le Put/Call ratio.
        Source: Yahoo Finance (gratuit)
        """
        cache_key = "vix_data"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        try:
            session = await self._get_session()
            
            # VIX via Yahoo Finance
            vix_url = "https://query1.finance.yahoo.com/v8/finance/chart/^VIX?interval=1d&range=5d"
            async with session.get(vix_url) as response:
                if response.status == 200:
                    data = await response.json()
                    meta = data["chart"]["result"][0]["meta"]
                    vix_price = meta.get("regularMarketPrice", 20.0)
                    # Utiliser chartPreviousClose ou calculer à partir des données
                    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                    if prev_close and prev_close > 0:
                        vix_change = ((vix_price - prev_close) / prev_close) * 100
                    else:
                        # Calculer à partir des données historiques si disponibles
                        closes = data["chart"]["result"][0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                        if len(closes) >= 2 and closes[-2]:
                            vix_change = ((vix_price - closes[-2]) / closes[-2]) * 100
                        else:
                            vix_change = 0.0
                else:
                    vix_price = 20.0  # Valeur par défaut
                    vix_change = 0.0
            
            result = {
                "vix": round(vix_price, 2),
                "vix_change_pct": round(vix_change, 2),
                "volatility_regime": self._get_volatility_regime(vix_price),
                "timestamp": datetime.now().isoformat(),
            }
            
            self._cache[cache_key] = {"data": result, "timestamp": datetime.now()}
            logger.info(f"📊 VIX: {vix_price:.2f} ({vix_change:+.2f}%)")
            return result
            
        except Exception as e:
            logger.warning(f"Erreur récupération VIX: {e}")
            return {"vix": 20.0, "volatility_regime": "NORMAL", "error": str(e)}
    
    def _get_volatility_regime(self, vix: float) -> str:
        """Détermine le régime de volatilité."""
        if vix < 15:
            return "LOW"
        elif vix < 20:
            return "NORMAL"
        elif vix < 30:
            return "ELEVATED"
        else:
            return "HIGH"
    
    # =====================================================
    # OPTIONS FLOW (Yahoo Finance - Gratuit)
    # =====================================================
    
    async def get_options_data(self, symbol: str) -> Dict[str, Any]:
        """
        Récupère les données d'options pour un symbole.
        Analyse le Put/Call ratio et l'activité inhabituelle.
        """
        cache_key = f"options_{symbol}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        try:
            session = await self._get_session()
            
            # Options chain via Yahoo Finance
            url = f"https://query1.finance.yahoo.com/v7/finance/options/{symbol}"
            async with session.get(url) as response:
                if response.status != 200:
                    return {"error": "Options data unavailable", "symbol": symbol}
                
                data = await response.json()
            
            if "optionChain" not in data or not data["optionChain"]["result"]:
                return {"error": "No options data", "symbol": symbol}
            
            options = data["optionChain"]["result"][0]
            quote = options.get("quote", {})
            
            # Calculer le Put/Call ratio
            calls = options.get("options", [{}])[0].get("calls", [])
            puts = options.get("options", [{}])[0].get("puts", [])
            
            total_call_volume = sum(c.get("volume", 0) or 0 for c in calls)
            total_put_volume = sum(p.get("volume", 0) or 0 for p in puts)
            total_call_oi = sum(c.get("openInterest", 0) or 0 for c in calls)
            total_put_oi = sum(p.get("openInterest", 0) or 0 for p in puts)
            
            put_call_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else 1.0
            put_call_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
            
            # Détecter l'activité inhabituelle
            unusual_calls = [c for c in calls if (c.get("volume", 0) or 0) > 5 * (c.get("openInterest", 1) or 1)]
            unusual_puts = [p for p in puts if (p.get("volume", 0) or 0) > 5 * (p.get("openInterest", 1) or 1)]
            
            # Calculer le sentiment
            if put_call_ratio < 0.7:
                sentiment = "BULLISH"
            elif put_call_ratio > 1.3:
                sentiment = "BEARISH"
            else:
                sentiment = "NEUTRAL"
            
            result = {
                "symbol": symbol,
                "put_call_ratio": round(put_call_ratio, 3),
                "put_call_oi_ratio": round(put_call_oi_ratio, 3),
                "total_call_volume": total_call_volume,
                "total_put_volume": total_put_volume,
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "unusual_call_activity": len(unusual_calls) > 0,
                "unusual_put_activity": len(unusual_puts) > 0,
                "unusual_activity_count": len(unusual_calls) + len(unusual_puts),
                "options_sentiment": sentiment,
                "implied_volatility": quote.get("impliedVolatility"),
                "timestamp": datetime.now().isoformat(),
            }
            
            self._cache[cache_key] = {"data": result, "timestamp": datetime.now()}
            logger.info(f"📊 Options {symbol}: P/C Ratio={put_call_ratio:.2f}, Sentiment={sentiment}")
            return result
            
        except Exception as e:
            logger.warning(f"Erreur récupération options {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    # =====================================================
    # DARK POOL (Estimation via volume + FINRA)
    # =====================================================
    
    async def get_dark_pool_estimate(self, symbol: str) -> Dict[str, Any]:
        """
        Estime l'activité Dark Pool pour un symbole.
        Utilise le ratio volume off-exchange vs on-exchange.
        Note: Données réelles Dark Pool nécessitent abonnement FINRA.
        On utilise ici une estimation basée sur les patterns de volume.
        """
        cache_key = f"darkpool_{symbol}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        try:
            session = await self._get_session()
            
            # Récupérer les données de volume via Yahoo
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
            async with session.get(url) as response:
                if response.status != 200:
                    return {"error": "Volume data unavailable", "symbol": symbol}
                
                data = await response.json()
            
            result = data["chart"]["result"][0]
            volumes = result["indicators"]["quote"][0]["volume"]
            
            # Filtrer les None
            volumes = [v for v in volumes if v is not None]
            
            if not volumes:
                return {"error": "No volume data", "symbol": symbol}
            
            current_volume = volumes[-1]
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else current_volume
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Estimation Dark Pool (généralement 35-45% du volume total)
            # Un volume anormalement bas peut indiquer plus d'activité dark pool
            estimated_dp_ratio = 0.40  # Base de 40%
            
            # Ajuster l'estimation basée sur le volume relatif
            if volume_ratio < 0.7:
                # Volume faible = peut-être plus de dark pool
                estimated_dp_ratio = 0.50
                dp_signal = "HIGH"
            elif volume_ratio > 1.5:
                # Volume élevé = probablement moins de dark pool (activité retail)
                estimated_dp_ratio = 0.30
                dp_signal = "LOW"
            else:
                dp_signal = "NORMAL"
            
            # Détecter si le volume est anormalement concentré (possible block trade)
            is_block_trade_likely = volume_ratio > 2.0
            
            result = {
                "symbol": symbol,
                "current_volume": current_volume,
                "avg_volume_5d": int(avg_volume),
                "volume_ratio": round(volume_ratio, 2),
                "estimated_dark_pool_ratio": estimated_dp_ratio,
                "dark_pool_signal": dp_signal,
                "block_trade_likely": is_block_trade_likely,
                "direction": "BULLISH" if volume_ratio > 1.2 else "BEARISH" if volume_ratio < 0.8 else "NEUTRAL",
                "timestamp": datetime.now().isoformat(),
            }
            
            self._cache[cache_key] = {"data": result, "timestamp": datetime.now()}
            logger.info(f"📊 Dark Pool {symbol}: Ratio estimé={estimated_dp_ratio:.0%}, Signal={dp_signal}")
            return result
            
        except Exception as e:
            logger.warning(f"Erreur estimation dark pool {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    # =====================================================
    # INSIDER TRADING (SEC EDGAR - Gratuit)
    # =====================================================
    
    async def get_insider_activity(self, symbol: str) -> Dict[str, Any]:
        """
        Récupère l'activité insider récente depuis SEC EDGAR (Form 4).
        100% gratuit via l'API SEC.
        """
        cache_key = f"insider_{symbol}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        try:
            session = await self._get_session()
            
            # D'abord, obtenir le CIK du ticker
            ticker_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={symbol}&type=4&dateb=&owner=include&count=10&output=atom"
            
            async with session.get(ticker_url) as response:
                if response.status != 200:
                    return {"error": "SEC data unavailable", "symbol": symbol, "insider_activity": "UNKNOWN"}
                
                text = await response.text()
            
            # Parser les résultats (format Atom/RSS)
            transactions = []
            
            # Chercher les Form 4 filings
            soup = BeautifulSoup(text, 'xml')
            entries = soup.find_all('entry')
            
            total_buy_value = 0
            total_sell_value = 0
            buy_count = 0
            sell_count = 0
            
            for entry in entries[:10]:  # Derniers 10 filings
                title = entry.find('title')
                if title:
                    title_text = title.text.lower()
                    # Estimation basique: chercher des indices d'achat/vente
                    if 'acquisition' in title_text or 'purchase' in title_text:
                        buy_count += 1
                        total_buy_value += 100000  # Estimation
                    elif 'disposition' in title_text or 'sale' in title_text:
                        sell_count += 1
                        total_sell_value += 100000
                    
                    transactions.append({
                        "title": title.text[:100],
                        "date": entry.find('updated').text if entry.find('updated') else None,
                    })
            
            # Déterminer le sentiment insider
            if buy_count > sell_count * 1.5:
                insider_sentiment = "BUYING"
            elif sell_count > buy_count * 1.5:
                insider_sentiment = "SELLING"
            else:
                insider_sentiment = "NEUTRAL"
            
            result = {
                "symbol": symbol,
                "insider_activity": insider_sentiment,
                "buy_transactions": buy_count,
                "sell_transactions": sell_count,
                "net_insider_sentiment": "BULLISH" if buy_count > sell_count else "BEARISH" if sell_count > buy_count else "NEUTRAL",
                "recent_filings": len(transactions),
                "transactions": transactions[:5],  # Top 5
                "timestamp": datetime.now().isoformat(),
            }
            
            self._cache[cache_key] = {"data": result, "timestamp": datetime.now()}
            logger.info(f"📊 Insider {symbol}: {insider_sentiment} (Buy: {buy_count}, Sell: {sell_count})")
            return result
            
        except Exception as e:
            logger.warning(f"Erreur récupération insider {symbol}: {e}")
            return {"error": str(e), "symbol": symbol, "insider_activity": "UNKNOWN"}
    
    # =====================================================
    # FEAR & GREED INDEX (CNN - Scraping gratuit)
    # =====================================================
    
    async def get_fear_greed_index(self) -> Dict[str, Any]:
        """
        Récupère le Fear & Greed Index.
        Source: Alternative.me (gratuit)
        """
        cache_key = "fear_greed"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        try:
            session = await self._get_session()
            
            # API gratuite Alternative.me (crypto mais corrélé)
            url = "https://api.alternative.me/fng/?limit=1"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    fng_data = data["data"][0]
                    value = int(fng_data["value"])
                    classification = fng_data["value_classification"]
                else:
                    # Fallback: estimer basé sur VIX
                    vix_data = await self.get_vix_data()
                    vix = vix_data.get("vix", 20)
                    # VIX inversé comme proxy du Fear/Greed
                    value = max(0, min(100, int(100 - (vix - 10) * 3)))
                    if value < 25:
                        classification = "Extreme Fear"
                    elif value < 45:
                        classification = "Fear"
                    elif value < 55:
                        classification = "Neutral"
                    elif value < 75:
                        classification = "Greed"
                    else:
                        classification = "Extreme Greed"
            
            result = {
                "fear_greed_index": value,
                "classification": classification,
                "market_sentiment": "BULLISH" if value > 55 else "BEARISH" if value < 45 else "NEUTRAL",
                "timestamp": datetime.now().isoformat(),
            }
            
            self._cache[cache_key] = {"data": result, "timestamp": datetime.now()}
            logger.info(f"📊 Fear & Greed Index: {value} ({classification})")
            return result
            
        except Exception as e:
            logger.warning(f"Erreur récupération Fear/Greed: {e}")
            return {"fear_greed_index": 50, "classification": "Neutral", "error": str(e)}
    
    # =====================================================
    # AGRÉGATION COMPLÈTE
    # =====================================================
    
    async def get_smart_money_summary(self, symbol: str) -> Dict[str, Any]:
        """
        Récupère toutes les données Smart Money pour un symbole.
        Agrège Dark Pool, Options et Insider en un résumé actionnable.
        """
        # Récupérer toutes les données en parallèle
        vix_task = self.get_vix_data()
        options_task = self.get_options_data(symbol)
        darkpool_task = self.get_dark_pool_estimate(symbol)
        insider_task = self.get_insider_activity(symbol)
        fng_task = self.get_fear_greed_index()
        
        vix, options, darkpool, insider, fng = await asyncio.gather(
            vix_task, options_task, darkpool_task, insider_task, fng_task,
            return_exceptions=True
        )
        
        # Gérer les exceptions
        if isinstance(vix, Exception):
            vix = {"vix": 20, "volatility_regime": "NORMAL"}
        if isinstance(options, Exception):
            options = {"options_sentiment": "NEUTRAL"}
        if isinstance(darkpool, Exception):
            darkpool = {"dark_pool_signal": "NORMAL"}
        if isinstance(insider, Exception):
            insider = {"insider_activity": "UNKNOWN"}
        if isinstance(fng, Exception):
            fng = {"fear_greed_index": 50, "market_sentiment": "NEUTRAL"}
        
        # Calculer le score Smart Money global
        bullish_signals = 0
        bearish_signals = 0
        
        if options.get("options_sentiment") == "BULLISH":
            bullish_signals += 2
        elif options.get("options_sentiment") == "BEARISH":
            bearish_signals += 2
        
        if darkpool.get("direction") == "BULLISH":
            bullish_signals += 1
        elif darkpool.get("direction") == "BEARISH":
            bearish_signals += 1
        
        if insider.get("net_insider_sentiment") == "BULLISH":
            bullish_signals += 2
        elif insider.get("net_insider_sentiment") == "BEARISH":
            bearish_signals += 2
        
        if fng.get("market_sentiment") == "BULLISH":
            bullish_signals += 1
        elif fng.get("market_sentiment") == "BEARISH":
            bearish_signals += 1
        
        # Déterminer le signal global
        if bullish_signals > bearish_signals + 2:
            overall_signal = "STRONG_BULLISH"
            confidence_boost = 10
        elif bullish_signals > bearish_signals:
            overall_signal = "BULLISH"
            confidence_boost = 5
        elif bearish_signals > bullish_signals + 2:
            overall_signal = "STRONG_BEARISH"
            confidence_boost = -10
        elif bearish_signals > bullish_signals:
            overall_signal = "BEARISH"
            confidence_boost = -5
        else:
            overall_signal = "NEUTRAL"
            confidence_boost = 0
        
        return {
            "symbol": symbol,
            "overall_signal": overall_signal,
            "confidence_adjustment": confidence_boost,
            "bullish_count": bullish_signals,
            "bearish_count": bearish_signals,
            
            # Détails
            "vix": vix,
            "options": options,
            "dark_pool": darkpool,
            "insider": insider,
            "fear_greed": fng,
            
            "timestamp": datetime.now().isoformat(),
        }
    
    def format_smart_data_for_agent(self, smart_data: Dict[str, Any]) -> str:
        """
        Formate les données Smart Money pour inclusion dans le prompt de l'agent.
        """
        if not smart_data or "error" in smart_data:
            return ""
        
        lines = [f"\n## 🎯 DONNÉES SMART MONEY - {smart_data.get('symbol', 'MARKET')}"]
        
        # Signal global
        signal = smart_data.get("overall_signal", "NEUTRAL")
        emoji = "🟢" if "BULLISH" in signal else "🔴" if "BEARISH" in signal else "⚪"
        lines.append(f"{emoji} **Signal Global: {signal}**")
        
        # VIX
        vix = smart_data.get("vix", {})
        if vix and not isinstance(vix, Exception):
            lines.append(f"\n📊 **Volatilité (VIX):** {vix.get('vix', 'N/A')} ({vix.get('volatility_regime', 'N/A')})")
        
        # Options
        options = smart_data.get("options", {})
        if options and not options.get("error"):
            lines.append(f"\n📈 **Options Flow:**")
            lines.append(f"  - Put/Call Ratio: {options.get('put_call_ratio', 'N/A')}")
            lines.append(f"  - Sentiment: {options.get('options_sentiment', 'N/A')}")
            if options.get("unusual_activity_count", 0) > 0:
                lines.append(f"  - ⚠️ ACTIVITÉ INHABITUELLE DÉTECTÉE ({options['unusual_activity_count']} contrats)")
        
        # Dark Pool
        dp = smart_data.get("dark_pool", {})
        if dp and not dp.get("error"):
            lines.append(f"\n🌑 **Dark Pool (estimation):**")
            lines.append(f"  - Ratio estimé: {dp.get('estimated_dark_pool_ratio', 0):.0%}")
            lines.append(f"  - Volume vs moyenne: {dp.get('volume_ratio', 1):.2f}x")
            if dp.get("block_trade_likely"):
                lines.append(f"  - ⚠️ BLOCK TRADE PROBABLE (gros acheteur institutionnel)")
        
        # Insider
        insider = smart_data.get("insider", {})
        if insider and not insider.get("error"):
            lines.append(f"\n👔 **Insider Activity:**")
            lines.append(f"  - Tendance: {insider.get('insider_activity', 'N/A')}")
            lines.append(f"  - Achats: {insider.get('buy_transactions', 0)} | Ventes: {insider.get('sell_transactions', 0)}")
        
        # Fear & Greed
        fng = smart_data.get("fear_greed", {})
        if fng and not isinstance(fng, Exception):
            lines.append(f"\n😱 **Fear & Greed Index:** {fng.get('fear_greed_index', 'N/A')} ({fng.get('classification', 'N/A')})")
        
        return "\n".join(lines)
    
    async def save_signal_to_db(self, signal_data: Dict[str, Any]) -> bool:
        """Sauvegarde un signal Smart Money en base."""
        if not supabase_client._initialized:
            return False
        
        try:
            supabase_client.client.table('smart_money_signals').insert(signal_data).execute()
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde signal: {e}")
            return False
    
    async def close(self):
        """Ferme la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()


# Instance globale
smart_data_service = SmartDataService()

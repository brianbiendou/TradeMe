"""
Data Aggregator - Collecteur Multi-Sources OPTIMISÉ.
Récupère les données de 15+ sources SANS utiliser de LLM.
Le but: préparer les données, calculer les métriques, réduire les tokens.
"""
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import re

from .config import settings
from .symbol_whitelist import is_symbol_allowed

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Sources de données disponibles."""
    # Incluses avec Alpaca
    ALPACA_NEWS = "alpaca_news"
    ALPACA_MARKET = "alpaca_market"
    
    # APIs gratuites avec clé
    FINNHUB = "finnhub"
    ALPHA_VANTAGE = "alpha_vantage"
    
    # APIs publiques (scraping léger)
    YAHOO_FINANCE = "yahoo_finance"
    CNN_FEAR_GREED = "cnn_fear_greed"
    SEC_EDGAR = "sec_edgar"
    FINVIZ = "finviz"
    
    # Reddit (API gratuite limitée)
    REDDIT_WSB = "reddit_wsb"
    
    # Calculés localement (GRATUIT, pas d'API)
    TECHNICAL_INDICATORS = "technical_local"
    MARKET_BREADTH = "market_breadth"
    VOLUME_ANALYSIS = "volume_analysis"


@dataclass
class MarketSentiment:
    """Sentiment du marché calculé automatiquement."""
    fear_greed_index: int  # 0-100
    fear_greed_label: str  # "Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"
    news_sentiment: float  # -1 à +1
    social_sentiment: float  # -1 à +1
    technical_sentiment: float  # -1 à +1
    overall_score: float  # -1 à +1
    overall_label: str  # "Bearish", "Neutral", "Bullish"


@dataclass
class StockSignal:
    """Signal technique calculé localement (SANS LLM)."""
    symbol: str
    signal: str  # "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    score: int  # -100 à +100
    reasons: List[str]
    momentum: float
    trend: str  # "UP", "DOWN", "SIDEWAYS"
    support: float
    resistance: float
    volume_ratio: float  # vs moyenne


class DataAggregator:
    """
    Agrégateur de données multi-sources OPTIMISÉ.
    
    Objectif: Collecter et PRÉ-TRAITER les données SANS LLM.
    L'IA reçoit ensuite un résumé concis = moins de tokens.
    """
    
    def __init__(self):
        self._initialized = False
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = {
            "fear_greed": 3600,      # 1 heure
            "news": 300,              # 5 minutes
            "movers": 60,             # 1 minute
            "technicals": 300,        # 5 minutes
            "reddit": 900,            # 15 minutes
            "earnings": 86400,        # 24 heures
        }
        self._api_calls_today: Dict[str, int] = {}
        self._daily_limits = {
            "alpha_vantage": 25,      # 25/jour gratuit
            "finnhub": 60,            # 60/minute
            "reddit": 100,            # ~100/jour safe
        }
    
    def initialize(self) -> bool:
        """Initialise l'agrégateur."""
        self._initialized = True
        self._api_calls_today = {k: 0 for k in self._daily_limits}
        logger.info("✅ DataAggregator initialisé (multi-sources optimisé)")
        return True
    
    # =========================================================
    # SOURCES GRATUITES - PAS D'API KEY REQUISE
    # =========================================================
    
    async def get_fear_greed_index(self) -> Dict[str, Any]:
        """
        Récupère le Fear & Greed Index de CNN.
        GRATUIT, pas d'API key.
        """
        cache_key = "fear_greed"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        try:
            # CNN Fear & Greed API (non-officielle mais stable)
            url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        score = data.get("fear_and_greed", {}).get("score", 50)
                        
                        # Déterminer le label
                        if score <= 25:
                            label = "Extreme Fear"
                        elif score <= 45:
                            label = "Fear"
                        elif score <= 55:
                            label = "Neutral"
                        elif score <= 75:
                            label = "Greed"
                        else:
                            label = "Extreme Greed"
                        
                        result = {
                            "score": int(score),
                            "label": label,
                            "previous_close": data.get("fear_and_greed", {}).get("previous_close"),
                            "timestamp": datetime.now().isoformat(),
                        }
                        
                        self._set_cache(cache_key, result)
                        return result
        
        except Exception as e:
            logger.warning(f"Fear & Greed non disponible: {e}")
        
        return {"score": 50, "label": "Neutral", "error": "Non disponible"}
    
    async def get_yahoo_movers(self) -> Dict[str, List[Dict]]:
        """
        Récupère les top movers de Yahoo Finance.
        GRATUIT, scraping léger.
        """
        cache_key = "yahoo_movers"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        result = {"gainers": [], "losers": [], "most_active": []}
        
        try:
            urls = {
                "gainers": "https://finance.yahoo.com/gainers",
                "losers": "https://finance.yahoo.com/losers",
                "most_active": "https://finance.yahoo.com/most-active",
            }
            
            async with aiohttp.ClientSession() as session:
                for category, url in urls.items():
                    try:
                        headers = {"User-Agent": "Mozilla/5.0"}
                        async with session.get(url, headers=headers, timeout=10) as response:
                            if response.status == 200:
                                html = await response.text()
                                # Parser basique - extraire les symboles et % change
                                # (en prod, utiliser BeautifulSoup)
                                symbols = re.findall(r'data-symbol="([A-Z]+)"', html)
                                changes = re.findall(r'data-field="regularMarketChangePercent"[^>]*>([+-]?\d+\.?\d*)%', html)
                                
                                for i, symbol in enumerate(symbols[:10]):
                                    # === V2.5: FILTRER SYMBOLES (S&P500/Nasdaq100) ===
                                    if not is_symbol_allowed(symbol):
                                        continue
                                    change = float(changes[i]) if i < len(changes) else 0
                                    result[category].append({
                                        "symbol": symbol,
                                        "change_pct": change,
                                    })
                    except Exception:
                        pass
            
            self._set_cache(cache_key, result)
            
        except Exception as e:
            logger.warning(f"Yahoo movers error: {e}")
        
        return result
    
    async def get_sec_recent_filings(self, form_types: List[str] = None) -> List[Dict]:
        """
        Récupère les filings SEC récents (8-K, 10-K, etc.).
        GRATUIT, API publique.
        """
        if form_types is None:
            form_types = ["8-K", "10-K", "10-Q"]  # Événements majeurs
        
        cache_key = "sec_filings"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        filings = []
        
        try:
            # SEC EDGAR RSS Feed
            url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=20&output=atom"
            
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "TradeMe Bot contact@example.com"}
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Parser basique XML
                        entries = re.findall(r'<entry>(.*?)</entry>', text, re.DOTALL)
                        
                        for entry in entries[:15]:
                            title = re.search(r'<title>(.*?)</title>', entry)
                            company = re.search(r'<company-info>(.*?)</company-info>', entry)
                            
                            if title:
                                filings.append({
                                    "title": title.group(1),
                                    "type": "8-K",
                                    "timestamp": datetime.now().isoformat(),
                                })
            
            self._set_cache(cache_key, filings)
            
        except Exception as e:
            logger.warning(f"SEC filings error: {e}")
        
        return filings
    
    # =========================================================
    # CALCULS LOCAUX - AUCUN COÛT API
    # =========================================================
    
    def calculate_technical_signal(
        self,
        prices: List[float],
        volumes: List[float] = None,
    ) -> Dict[str, Any]:
        """
        Calcule les indicateurs techniques LOCALEMENT.
        GRATUIT - Aucun appel API ni LLM.
        """
        if len(prices) < 20:
            return {"signal": "INSUFFICIENT_DATA", "score": 0}
        
        # Simple Moving Averages
        sma_10 = sum(prices[-10:]) / 10
        sma_20 = sum(prices[-20:]) / 20
        sma_50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else sma_20
        
        current_price = prices[-1]
        
        # RSI (Relative Strength Index)
        gains = []
        losses = []
        for i in range(1, min(15, len(prices))):
            change = prices[-i] - prices[-i-1]
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))
        
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 0.001
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # MACD simplifié
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        macd = ema_12 - ema_26
        
        # Score composite
        score = 0
        reasons = []
        
        # Prix vs SMAs
        if current_price > sma_10 > sma_20:
            score += 20
            reasons.append("Prix au-dessus des SMAs (tendance haussière)")
        elif current_price < sma_10 < sma_20:
            score -= 20
            reasons.append("Prix en-dessous des SMAs (tendance baissière)")
        
        # RSI
        if rsi < 30:
            score += 25
            reasons.append(f"RSI survendu ({rsi:.0f})")
        elif rsi > 70:
            score -= 25
            reasons.append(f"RSI suracheté ({rsi:.0f})")
        elif 40 < rsi < 60:
            reasons.append(f"RSI neutre ({rsi:.0f})")
        
        # MACD
        if macd > 0:
            score += 15
            reasons.append("MACD positif")
        else:
            score -= 15
            reasons.append("MACD négatif")
        
        # Momentum (changement sur 5 jours)
        if len(prices) >= 5:
            momentum = ((current_price / prices[-5]) - 1) * 100
            if momentum > 3:
                score += 15
                reasons.append(f"Momentum fort (+{momentum:.1f}%)")
            elif momentum < -3:
                score -= 15
                reasons.append(f"Momentum faible ({momentum:.1f}%)")
        else:
            momentum = 0
        
        # Volume (si disponible)
        volume_ratio = 1.0
        if volumes and len(volumes) >= 20:
            avg_volume = sum(volumes[-20:]) / 20
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_ratio > 1.5:
                score += 10
                reasons.append(f"Volume élevé ({volume_ratio:.1f}x)")
            elif volume_ratio < 0.5:
                score -= 5
                reasons.append(f"Volume faible ({volume_ratio:.1f}x)")
        
        # Déterminer le signal
        if score >= 40:
            signal = "STRONG_BUY"
        elif score >= 15:
            signal = "BUY"
        elif score <= -40:
            signal = "STRONG_SELL"
        elif score <= -15:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # Trend
        if sma_10 > sma_20 > sma_50:
            trend = "UP"
        elif sma_10 < sma_20 < sma_50:
            trend = "DOWN"
        else:
            trend = "SIDEWAYS"
        
        # Support/Resistance basiques
        recent_low = min(prices[-20:])
        recent_high = max(prices[-20:])
        
        return {
            "signal": signal,
            "score": score,
            "reasons": reasons,
            "indicators": {
                "rsi": round(rsi, 1),
                "macd": round(macd, 4),
                "sma_10": round(sma_10, 2),
                "sma_20": round(sma_20, 2),
                "momentum_5d": round(momentum, 2),
                "volume_ratio": round(volume_ratio, 2),
            },
            "trend": trend,
            "support": round(recent_low, 2),
            "resistance": round(recent_high, 2),
        }
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calcule l'EMA (Exponential Moving Average)."""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def calculate_market_breadth(
        self,
        advancing: int,
        declining: int,
        new_highs: int,
        new_lows: int,
    ) -> Dict[str, Any]:
        """
        Calcule les indicateurs de breadth du marché.
        GRATUIT - Calcul local.
        """
        total = advancing + declining
        if total == 0:
            return {"breadth_ratio": 0.5, "signal": "NEUTRAL"}
        
        # Advance/Decline Ratio
        ad_ratio = advancing / total
        
        # New High/Low Ratio
        hl_total = new_highs + new_lows
        hl_ratio = new_highs / hl_total if hl_total > 0 else 0.5
        
        # Score composite
        breadth_score = (ad_ratio * 0.6 + hl_ratio * 0.4) * 100
        
        if breadth_score > 65:
            signal = "BULLISH"
        elif breadth_score < 35:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"
        
        return {
            "breadth_ratio": round(ad_ratio, 3),
            "advance_decline": f"{advancing}/{declining}",
            "new_highs_lows": f"{new_highs}/{new_lows}",
            "breadth_score": round(breadth_score, 1),
            "signal": signal,
        }
    
    def analyze_news_sentiment_local(self, headlines: List[str]) -> Dict[str, Any]:
        """
        Analyse le sentiment des news LOCALEMENT sans LLM.
        Utilise des mots-clés positifs/négatifs.
        """
        positive_words = {
            'surge', 'jump', 'soar', 'rally', 'gain', 'rise', 'climb', 'beat',
            'profit', 'growth', 'record', 'strong', 'bullish', 'upgrade',
            'buy', 'outperform', 'exceed', 'boom', 'breakthrough', 'innovation',
            'approval', 'deal', 'partnership', 'acquisition', 'dividend'
        }
        
        negative_words = {
            'crash', 'plunge', 'drop', 'fall', 'decline', 'loss', 'miss',
            'weak', 'bearish', 'downgrade', 'sell', 'underperform', 'layoff',
            'bankruptcy', 'fraud', 'investigation', 'lawsuit', 'recall',
            'delay', 'warning', 'risk', 'fear', 'concern', 'cut', 'slash'
        }
        
        neutral_words = {'hold', 'steady', 'flat', 'unchanged', 'mixed'}
        
        total_positive = 0
        total_negative = 0
        total_neutral = 0
        analyzed = []
        
        for headline in headlines:
            words = headline.lower().split()
            pos = sum(1 for w in words if any(p in w for p in positive_words))
            neg = sum(1 for w in words if any(n in w for n in negative_words))
            
            if pos > neg:
                sentiment = "positive"
                total_positive += 1
            elif neg > pos:
                sentiment = "negative"
                total_negative += 1
            else:
                sentiment = "neutral"
                total_neutral += 1
            
            analyzed.append({
                "headline": headline[:100],
                "sentiment": sentiment,
                "pos_score": pos,
                "neg_score": neg,
            })
        
        total = len(headlines) or 1
        sentiment_score = (total_positive - total_negative) / total
        
        if sentiment_score > 0.2:
            overall = "BULLISH"
        elif sentiment_score < -0.2:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"
        
        return {
            "overall_sentiment": overall,
            "sentiment_score": round(sentiment_score, 3),
            "positive_count": total_positive,
            "negative_count": total_negative,
            "neutral_count": total_neutral,
            "top_headlines": analyzed[:5],
        }
    
    # =========================================================
    # SOURCES AVEC API KEY (Gratuites avec limites)
    # =========================================================
    
    async def get_finnhub_data(self, symbol: str = None) -> Dict[str, Any]:
        """
        Récupère données Finnhub (sentiment, earnings, recommendations).
        GRATUIT avec API key (60 calls/minute).
        """
        if not settings.finnhub_api_key:
            return {"error": "Finnhub API key non configurée"}
        
        if self._api_calls_today.get("finnhub", 0) >= self._daily_limits["finnhub"] * 60:
            return {"error": "Limite Finnhub atteinte"}
        
        result = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                base_url = "https://finnhub.io/api/v1"
                headers = {"X-Finnhub-Token": settings.finnhub_api_key}
                
                # Market news
                url = f"{base_url}/news?category=general"
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        news = await response.json()
                        result["news"] = [
                            {
                                "headline": n.get("headline"),
                                "source": n.get("source"),
                                "datetime": n.get("datetime"),
                            }
                            for n in news[:10]
                        ]
                        self._api_calls_today["finnhub"] = self._api_calls_today.get("finnhub", 0) + 1
                
                # Earnings calendar
                today = datetime.now().strftime("%Y-%m-%d")
                next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                url = f"{base_url}/calendar/earnings?from={today}&to={next_week}"
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        earnings = await response.json()
                        result["upcoming_earnings"] = earnings.get("earningsCalendar", [])[:20]
                        self._api_calls_today["finnhub"] = self._api_calls_today.get("finnhub", 0) + 1
                
                # Si symbole spécifique
                if symbol:
                    # Recommendation trends
                    url = f"{base_url}/stock/recommendation?symbol={symbol}"
                    async with session.get(url, headers=headers, timeout=10) as response:
                        if response.status == 200:
                            recs = await response.json()
                            if recs:
                                latest = recs[0]
                                result["recommendations"] = {
                                    "buy": latest.get("buy", 0),
                                    "hold": latest.get("hold", 0),
                                    "sell": latest.get("sell", 0),
                                    "strong_buy": latest.get("strongBuy", 0),
                                    "strong_sell": latest.get("strongSell", 0),
                                }
                            self._api_calls_today["finnhub"] = self._api_calls_today.get("finnhub", 0) + 1
        
        except Exception as e:
            logger.error(f"Finnhub error: {e}")
            result["error"] = str(e)
        
        return result
    
    async def get_reddit_sentiment(self, subreddit: str = "wallstreetbets") -> Dict[str, Any]:
        """
        Récupère le sentiment Reddit (WSB, stocks, etc.).
        GRATUIT mais limité.
        """
        cache_key = f"reddit_{subreddit}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        result = {"posts": [], "trending_tickers": {}, "sentiment": "neutral"}
        
        try:
            # Reddit JSON API (pas besoin d'auth pour lecture publique)
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
            
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "TradeMe/1.0"}
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        posts = data.get("data", {}).get("children", [])
                        
                        ticker_mentions = {}
                        titles = []
                        
                        for post in posts:
                            post_data = post.get("data", {})
                            title = post_data.get("title", "")
                            titles.append(title)
                            
                            # Extraire les tickers mentionnés ($AAPL, TSLA, etc.)
                            tickers = re.findall(r'\$?([A-Z]{2,5})\b', title)
                            for ticker in tickers:
                                if ticker not in ["THE", "FOR", "AND", "WSB", "DD", "YOLO"]:
                                    ticker_mentions[ticker] = ticker_mentions.get(ticker, 0) + 1
                            
                            result["posts"].append({
                                "title": title[:150],
                                "score": post_data.get("score", 0),
                                "comments": post_data.get("num_comments", 0),
                            })
                        
                        # Top tickers mentionnés
                        result["trending_tickers"] = dict(
                            sorted(ticker_mentions.items(), key=lambda x: x[1], reverse=True)[:10]
                        )
                        
                        # Analyse sentiment locale
                        sentiment_analysis = self.analyze_news_sentiment_local(titles)
                        result["sentiment"] = sentiment_analysis["overall_sentiment"]
                        result["sentiment_score"] = sentiment_analysis["sentiment_score"]
            
            self._set_cache(cache_key, result)
            
        except Exception as e:
            logger.warning(f"Reddit error: {e}")
        
        return result
    
    # =========================================================
    # AGRÉGATION COMPLÈTE OPTIMISÉE
    # =========================================================
    
    async def get_full_market_context(self) -> Dict[str, Any]:
        """
        Récupère TOUTES les données disponibles de manière optimisée.
        Retourne un résumé CONCIS pour minimiser les tokens LLM.
        """
        logger.info("📊 Collecte des données multi-sources...")
        
        # Collecter en parallèle
        tasks = [
            self.get_fear_greed_index(),
            self.get_yahoo_movers(),
            self.get_finnhub_data(),
            self.get_reddit_sentiment(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        fear_greed = results[0] if not isinstance(results[0], Exception) else {}
        yahoo_movers = results[1] if not isinstance(results[1], Exception) else {}
        finnhub = results[2] if not isinstance(results[2], Exception) else {}
        reddit = results[3] if not isinstance(results[3], Exception) else {}
        
        # Construire le contexte agrégé
        context = {
            "timestamp": datetime.now().isoformat(),
            "market_sentiment": {
                "fear_greed": fear_greed,
                "reddit_sentiment": reddit.get("sentiment", "unknown"),
                "reddit_trending": list(reddit.get("trending_tickers", {}).keys())[:5],
            },
            "movers": {
                "top_gainers": yahoo_movers.get("gainers", [])[:5],
                "top_losers": yahoo_movers.get("losers", [])[:5],
            },
            "upcoming_earnings": finnhub.get("upcoming_earnings", [])[:10],
            "news_headlines": [
                n.get("headline") for n in finnhub.get("news", [])[:5]
            ],
            "sources_used": [
                "cnn_fear_greed",
                "yahoo_finance",
                "finnhub" if settings.finnhub_api_key else None,
                "reddit_wsb",
            ],
            "api_calls_remaining": {
                k: self._daily_limits[k] - v 
                for k, v in self._api_calls_today.items()
            },
        }
        
        return context
    
    def format_context_for_llm(self, context: Dict[str, Any], max_tokens: int = 800) -> str:
        """
        Formate le contexte de manière CONCISE pour l'IA.
        Objectif: Maximum d'info, minimum de tokens.
        """
        lines = []
        
        # Fear & Greed (très concis)
        fg = context.get("market_sentiment", {}).get("fear_greed", {})
        if fg:
            lines.append(f"📊 SENTIMENT: Fear&Greed={fg.get('score', '?')}/100 ({fg.get('label', '?')})")
        
        # Reddit trending
        trending = context.get("market_sentiment", {}).get("reddit_trending", [])
        if trending:
            lines.append(f"🔥 REDDIT HOT: {', '.join(trending[:5])}")
        
        # Movers (ultra concis)
        gainers = context.get("movers", {}).get("top_gainers", [])
        if gainers:
            g_str = ", ".join([f"{g['symbol']}+{g.get('change_pct', 0):.1f}%" for g in gainers[:3]])
            lines.append(f"📈 GAINERS: {g_str}")
        
        losers = context.get("movers", {}).get("top_losers", [])
        if losers:
            l_str = ", ".join([f"{l['symbol']}{l.get('change_pct', 0):.1f}%" for l in losers[:3]])
            lines.append(f"📉 LOSERS: {l_str}")
        
        # Earnings à venir (juste les symboles)
        earnings = context.get("upcoming_earnings", [])
        if earnings:
            e_symbols = [e.get("symbol", "") for e in earnings[:5] if e.get("symbol")]
            if e_symbols:
                lines.append(f"📅 EARNINGS SOON: {', '.join(e_symbols)}")
        
        # Headlines (très court)
        headlines = context.get("news_headlines", [])
        if headlines:
            lines.append("📰 NEWS:")
            for h in headlines[:3]:
                if h:
                    lines.append(f"  • {h[:80]}...")
        
        return "\n".join(lines)
    
    # =========================================================
    # UTILITAIRES CACHE
    # =========================================================
    
    def _is_cache_valid(self, key: str) -> bool:
        """Vérifie si le cache est valide."""
        if key not in self._cache:
            return False
        
        cached = self._cache[key]
        ttl = self._cache_ttl.get(key.split("_")[0], 300)
        age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
        
        return age < ttl
    
    def _set_cache(self, key: str, data: Any):
        """Met en cache les données."""
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now(),
        }
    
    def get_api_usage_stats(self) -> Dict[str, Any]:
        """Retourne les stats d'utilisation des APIs."""
        return {
            "calls_today": self._api_calls_today,
            "limits": self._daily_limits,
            "remaining": {
                k: self._daily_limits[k] - v 
                for k, v in self._api_calls_today.items()
            },
        }


# Instance globale
data_aggregator = DataAggregator()

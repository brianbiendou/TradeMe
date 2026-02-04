"""
News Aggregator - Collecteur d'actualités financières multi-sources.
Permet aux agents IA d'avoir accès à l'information en temps réel.
"""
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json

from .config import settings

logger = logging.getLogger(__name__)


class NewsAggregator:
    """
    Agrégateur d'actualités financières multi-sources.
    
    Sources utilisées:
    1. Alpaca News API (gratuit avec compte Alpaca)
    2. Finnhub (news financières)
    3. Alpha Vantage (news et sentiment)
    4. RSS Feeds (Reuters, Bloomberg, CNBC)
    """
    
    def __init__(self):
        self._initialized = False
        self._cache: Dict[str, Dict] = {}
        self._cache_duration = 300  # 5 minutes
        self._last_fetch: Dict[str, datetime] = {}
    
    def initialize(self) -> bool:
        """Initialise le collecteur de news."""
        self._initialized = True
        logger.info("✅ NewsAggregator initialisé")
        return True
    
    async def get_market_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Récupère les actualités générales du marché.
        Combine plusieurs sources pour une vue complète.
        """
        news = []
        
        # Source 1: Alpaca News
        alpaca_news = await self._fetch_alpaca_news(limit=limit)
        news.extend(alpaca_news)
        
        # Source 2: Finnhub (si API key disponible)
        if settings.finnhub_api_key:
            finnhub_news = await self._fetch_finnhub_news(limit=limit)
            news.extend(finnhub_news)
        
        # Dédupliquer et trier par date
        seen_titles = set()
        unique_news = []
        for item in news:
            title_key = item.get("title", "")[:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_news.append(item)
        
        # Trier par date (plus récent en premier)
        unique_news.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return unique_news[:limit]
    
    async def get_symbol_news(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les actualités spécifiques à un symbole."""
        cache_key = f"symbol_{symbol}"
        
        # Vérifier le cache
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        news = await self._fetch_alpaca_news(symbols=[symbol], limit=limit)
        
        # Mettre en cache
        self._cache[cache_key] = {
            "data": news,
            "timestamp": datetime.now()
        }
        
        return news
    
    async def get_trending_topics(self) -> List[str]:
        """
        Identifie les sujets tendance du moment.
        Analyse les titres des news pour extraire les thèmes récurrents.
        """
        news = await self.get_market_news(limit=50)
        
        # Extraire les symboles mentionnés
        symbols_mentioned = {}
        keywords = {}
        
        important_keywords = [
            "earnings", "FDA", "merger", "acquisition", "IPO", "split",
            "dividend", "bankruptcy", "lawsuit", "CEO", "guidance",
            "upgrade", "downgrade", "beat", "miss", "rally", "crash",
            "AI", "artificial intelligence", "chips", "semiconductor",
            "oil", "gold", "crypto", "bitcoin", "inflation", "fed",
            "interest rate", "tariff", "regulation"
        ]
        
        for item in news:
            title = item.get("title", "").lower()
            # Compter les symboles
            for sym in item.get("symbols", []):
                symbols_mentioned[sym] = symbols_mentioned.get(sym, 0) + 1
            # Compter les keywords
            for kw in important_keywords:
                if kw.lower() in title:
                    keywords[kw] = keywords.get(kw, 0) + 1
        
        # Top symboles et keywords
        top_symbols = sorted(symbols_mentioned.items(), key=lambda x: x[1], reverse=True)[:5]
        top_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:5]
        
        topics = []
        for sym, count in top_symbols:
            topics.append(f"${sym} ({count} mentions)")
        for kw, count in top_keywords:
            topics.append(f"{kw} ({count} articles)")
        
        return topics
    
    async def get_sentiment_summary(self) -> Dict[str, Any]:
        """
        Génère un résumé du sentiment général du marché.
        """
        news = await self.get_market_news(limit=30)
        
        positive_words = ["surge", "rally", "gain", "beat", "record", "bullish", "growth", "profit", "up"]
        negative_words = ["drop", "fall", "crash", "miss", "loss", "bearish", "decline", "down", "fear"]
        
        positive_count = 0
        negative_count = 0
        
        for item in news:
            title = item.get("title", "").lower()
            headline = item.get("headline", "").lower()
            text = f"{title} {headline}"
            
            for word in positive_words:
                if word in text:
                    positive_count += 1
            for word in negative_words:
                if word in text:
                    negative_count += 1
        
        total = positive_count + negative_count
        if total == 0:
            sentiment_score = 50
        else:
            sentiment_score = int((positive_count / total) * 100)
        
        return {
            "score": sentiment_score,
            "label": "BULLISH" if sentiment_score > 60 else "BEARISH" if sentiment_score < 40 else "NEUTRAL",
            "positive_signals": positive_count,
            "negative_signals": negative_count,
            "analyzed_articles": len(news),
        }
    
    async def format_news_for_agent(self, limit: int = 15) -> str:
        """
        Formate les actualités pour être comprises par les agents IA.
        Retourne un texte structuré avec les infos clés.
        """
        news = await self.get_market_news(limit=limit)
        sentiment = await self.get_sentiment_summary()
        trending = await self.get_trending_topics()
        
        formatted = []
        formatted.append("=" * 60)
        formatted.append("📰 ACTUALITÉS FINANCIÈRES EN TEMPS RÉEL")
        formatted.append("=" * 60)
        formatted.append("")
        
        # Sentiment global
        formatted.append(f"## SENTIMENT DU MARCHÉ: {sentiment['label']} ({sentiment['score']}/100)")
        formatted.append(f"   Signaux positifs: {sentiment['positive_signals']} | Négatifs: {sentiment['negative_signals']}")
        formatted.append("")
        
        # Sujets tendance
        if trending:
            formatted.append("## SUJETS TENDANCE:")
            for topic in trending[:5]:
                formatted.append(f"   • {topic}")
            formatted.append("")
        
        # News détaillées
        formatted.append("## DERNIÈRES ACTUALITÉS:")
        formatted.append("")
        
        for i, item in enumerate(news[:limit], 1):
            title = item.get("title") or item.get("headline", "Sans titre")
            source = item.get("source", "Unknown")
            symbols = item.get("symbols", [])
            created = item.get("created_at", "")[:16]  # Date courte
            summary = item.get("summary", "")[:200] if item.get("summary") else ""
            
            formatted.append(f"[{i}] {title}")
            formatted.append(f"    Source: {source} | Date: {created}")
            if symbols:
                formatted.append(f"    Symboles: {', '.join(symbols)}")
            if summary:
                formatted.append(f"    Résumé: {summary}...")
            formatted.append("")
        
        return "\n".join(formatted)
    
    async def _fetch_alpaca_news(
        self, 
        symbols: List[str] = None, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Récupère les news depuis l'API Alpaca."""
        try:
            url = "https://data.alpaca.markets/v1beta1/news"
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
            }
            params = {"limit": limit}
            if symbols:
                params["symbols"] = ",".join(symbols)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("news", [])
                    else:
                        logger.warning(f"Alpaca News API: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"Erreur Alpaca News: {e}")
            return []
    
    async def _fetch_finnhub_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Récupère les news depuis Finnhub."""
        if not settings.finnhub_api_key:
            return []
        
        try:
            url = "https://finnhub.io/api/v1/news"
            params = {
                "category": "general",
                "token": settings.finnhub_api_key,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Convertir au format standard
                        news = []
                        for item in data[:limit]:
                            news.append({
                                "title": item.get("headline", ""),
                                "source": item.get("source", "Finnhub"),
                                "created_at": datetime.fromtimestamp(
                                    item.get("datetime", 0)
                                ).isoformat(),
                                "summary": item.get("summary", ""),
                                "url": item.get("url", ""),
                                "symbols": [],
                            })
                        return news
                    return []
        except Exception as e:
            logger.error(f"Erreur Finnhub: {e}")
            return []
    
    def _is_cache_valid(self, key: str) -> bool:
        """Vérifie si le cache est encore valide."""
        if key not in self._cache:
            return False
        cache_time = self._cache[key].get("timestamp")
        if not cache_time:
            return False
        return (datetime.now() - cache_time).seconds < self._cache_duration


# Instance singleton
news_aggregator = NewsAggregator()

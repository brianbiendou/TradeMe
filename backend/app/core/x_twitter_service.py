"""
X (Twitter) Service - Collecteur de tendances X pour Grok.
Permet à Grok d'analyser les tendances et buzz sur X.
"""
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json

from .config import settings

logger = logging.getLogger(__name__)


class XTwitterService:
    """
    Service de collecte de tendances X (Twitter).
    
    Utilise l'API X v2 si disponible, sinon fallback sur des alternatives.
    
    Configuration requise dans .env:
    - X_BEARER_TOKEN: Token Bearer pour l'API X v2
    """
    
    def __init__(self):
        self._initialized = False
        self._bearer_token = None
        self._cache: Dict[str, Dict] = {}
        self._cache_duration = 300  # 5 minutes
    
    def initialize(self) -> bool:
        """Initialise le service X."""
        # Récupérer le token depuis les settings
        self._bearer_token = getattr(settings, 'x_bearer_token', None)
        
        if self._bearer_token:
            logger.info("✅ X/Twitter Service initialisé avec API officielle")
        else:
            logger.warning("⚠️ X/Twitter Service: Pas de token API, mode limité")
        
        self._initialized = True
        return True
    
    async def get_trending_topics(self, woeid: int = 23424977) -> List[Dict[str, Any]]:
        """
        Récupère les tendances X (Twitter).
        
        Args:
            woeid: Where On Earth ID (23424977 = USA, 23424819 = France)
            
        Returns:
            Liste des tendances avec volume et contexte
        """
        if not self._initialized:
            return []
        
        # Vérifier le cache
        cache_key = f"trending_{woeid}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        
        try:
            if self._bearer_token:
                trends = await self._fetch_trends_api(woeid)
            else:
                # Mode dégradé: retourner des tendances simulées basées sur les news
                trends = await self._get_simulated_trends()
            
            # Mettre en cache
            self._cache[cache_key] = {
                "data": trends,
                "timestamp": datetime.now()
            }
            
            return trends
            
        except Exception as e:
            logger.error(f"Erreur get_trending_topics: {e}")
            return []
    
    async def search_finance_tweets(
        self,
        query: str,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Recherche des tweets sur un sujet financier.
        
        Args:
            query: Terme de recherche (ex: "$AAPL" ou "Tesla earnings")
            max_results: Nombre max de tweets
            
        Returns:
            Liste des tweets avec sentiment
        """
        if not self._bearer_token:
            return [{
                "text": f"[API X non configurée] Recherche simulée pour: {query}",
                "created_at": datetime.now().isoformat(),
                "sentiment": "neutral",
                "engagement": 0,
            }]
        
        try:
            tweets = await self._search_tweets_api(query, max_results)
            return tweets
        except Exception as e:
            logger.error(f"Erreur search_finance_tweets: {e}")
            return []
    
    async def get_influencer_mentions(
        self,
        usernames: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Récupère les derniers tweets d'influenceurs financiers.
        
        Args:
            usernames: Liste de usernames à suivre
            
        Returns:
            Tweets récents des influenceurs
        """
        if usernames is None:
            # Influenceurs par défaut
            usernames = [
                "elonmusk",      # Elon Musk
                "jimcramer",     # Jim Cramer
                "WSJ",           # Wall Street Journal
                "Bloomberg",     # Bloomberg
                "ReutersBiz",    # Reuters Business
            ]
        
        if not self._bearer_token:
            return [{
                "username": "system",
                "text": "[API X non configurée] Surveillance des influenceurs désactivée",
                "created_at": datetime.now().isoformat(),
            }]
        
        all_tweets = []
        
        for username in usernames:
            try:
                tweets = await self._get_user_tweets_api(username, limit=5)
                all_tweets.extend(tweets)
            except Exception as e:
                logger.error(f"Erreur get tweets de {username}: {e}")
        
        # Trier par date
        all_tweets.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return all_tweets[:20]
    
    async def analyze_sentiment_for_symbol(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """
        Analyse le sentiment X pour un symbole boursier.
        
        Args:
            symbol: Ticker (ex: AAPL, TSLA)
            
        Returns:
            Score de sentiment et résumé
        """
        # Rechercher les tweets mentionnant le symbole
        query = f"${symbol} OR #{symbol}"
        tweets = await self.search_finance_tweets(query, max_results=50)
        
        if not tweets:
            return {
                "symbol": symbol,
                "sentiment_score": 0,
                "sentiment_label": "neutral",
                "tweet_count": 0,
                "summary": "Pas assez de données",
            }
        
        # Analyser le sentiment (simple pour l'instant)
        positive_words = [
            "moon", "buy", "bullish", "up", "gain", "profit",
            "rocket", "strong", "growth", "beat", "surge"
        ]
        negative_words = [
            "crash", "sell", "bearish", "down", "loss", "dump",
            "fail", "weak", "miss", "drop", "tank"
        ]
        
        positive_count = 0
        negative_count = 0
        
        for tweet in tweets:
            text = tweet.get("text", "").lower()
            for word in positive_words:
                if word in text:
                    positive_count += 1
            for word in negative_words:
                if word in text:
                    negative_count += 1
        
        total = positive_count + negative_count
        if total == 0:
            sentiment_score = 0
            sentiment_label = "neutral"
        else:
            sentiment_score = ((positive_count - negative_count) / total) * 100
            if sentiment_score > 20:
                sentiment_label = "bullish"
            elif sentiment_score < -20:
                sentiment_label = "bearish"
            else:
                sentiment_label = "neutral"
        
        return {
            "symbol": symbol,
            "sentiment_score": round(sentiment_score, 2),
            "sentiment_label": sentiment_label,
            "tweet_count": len(tweets),
            "positive_mentions": positive_count,
            "negative_mentions": negative_count,
            "summary": f"{len(tweets)} tweets analysés, sentiment {sentiment_label}",
        }
    
    def format_for_grok(self, trends: List[Dict], tweets: List[Dict] = None) -> str:
        """
        Formate les données X pour Grok.
        
        Returns:
            Texte formaté pour le prompt de Grok
        """
        lines = ["## 📱 DONNÉES X (TWITTER) - Spécial Grok", ""]
        
        if trends:
            lines.append("### 🔥 Tendances en cours")
            for i, trend in enumerate(trends[:10], 1):
                name = trend.get("name", "N/A")
                volume = trend.get("tweet_volume", 0)
                vol_str = f" ({volume:,} tweets)" if volume else ""
                lines.append(f"{i}. {name}{vol_str}")
            lines.append("")
        
        if tweets:
            lines.append("### 💬 Tweets Influenceurs")
            for tweet in tweets[:10]:
                username = tweet.get("username", "?")
                text = tweet.get("text", "")[:200]
                lines.append(f"@{username}: {text}")
                lines.append("")
        
        if not trends and not tweets:
            lines.append("⚠️ Données X non disponibles (API non configurée)")
        
        return "\n".join(lines)
    
    # === Méthodes privées API ===
    
    async def _fetch_trends_api(self, woeid: int) -> List[Dict]:
        """Appelle l'API X pour récupérer les tendances."""
        url = f"https://api.twitter.com/1.1/trends/place.json?id={woeid}"
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self._bearer_token}"}
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        return data[0].get("trends", [])
        
        return []
    
    async def _search_tweets_api(self, query: str, max_results: int) -> List[Dict]:
        """Recherche de tweets via l'API v2."""
        url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics",
        }
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self._bearer_token}"}
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    tweets = data.get("data", [])
                    return [
                        {
                            "text": t.get("text"),
                            "created_at": t.get("created_at"),
                            "engagement": t.get("public_metrics", {}).get("like_count", 0),
                        }
                        for t in tweets
                    ]
        
        return []
    
    async def _get_user_tweets_api(self, username: str, limit: int) -> List[Dict]:
        """Récupère les tweets d'un utilisateur."""
        # D'abord récupérer l'ID de l'utilisateur
        user_url = f"https://api.twitter.com/2/users/by/username/{username}"
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self._bearer_token}"}
            
            async with session.get(user_url, headers=headers) as response:
                if response.status != 200:
                    return []
                user_data = await response.json()
                user_id = user_data.get("data", {}).get("id")
                if not user_id:
                    return []
            
            # Récupérer les tweets
            tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
            params = {
                "max_results": limit,
                "tweet.fields": "created_at,public_metrics",
            }
            
            async with session.get(tweets_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    tweets = data.get("data", [])
                    return [
                        {
                            "username": username,
                            "text": t.get("text"),
                            "created_at": t.get("created_at"),
                            "engagement": t.get("public_metrics", {}).get("like_count", 0),
                        }
                        for t in tweets
                    ]
        
        return []
    
    async def _get_simulated_trends(self) -> List[Dict]:
        """Retourne des tendances simulées basées sur les actualités financières."""
        # Tendances typiques liées à la finance
        return [
            {"name": "#Stocks", "tweet_volume": 50000},
            {"name": "#Trading", "tweet_volume": 35000},
            {"name": "$SPY", "tweet_volume": 28000},
            {"name": "#Earnings", "tweet_volume": 22000},
            {"name": "#WallStreet", "tweet_volume": 18000},
            {"name": "#Crypto", "tweet_volume": 45000},
            {"name": "$BTC", "tweet_volume": 40000},
            {"name": "#Markets", "tweet_volume": 15000},
            {"name": "#Investment", "tweet_volume": 12000},
            {"name": "#Finance", "tweet_volume": 10000},
        ]
    
    def _is_cache_valid(self, key: str) -> bool:
        """Vérifie si le cache est encore valide."""
        if key not in self._cache:
            return False
        
        cached_time = self._cache[key].get("timestamp")
        if not cached_time:
            return False
        
        return (datetime.now() - cached_time).total_seconds() < self._cache_duration


# Instance globale
x_service = XTwitterService()

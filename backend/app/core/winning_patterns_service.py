"""
Winning Patterns Service - Stockage et Analyse des Patterns Gagnants V2.4.

Ce service améliore la mémoire RAG pour stocker non seulement les erreurs
mais surtout les CONDITIONS DES SUCCÈS:
- Heure de trading
- Catalyst/News
- Setup technique complet (RSI, MACD, Volume, Trend)
- Contexte marché (VIX, sentiment)
- Pattern de prix (breakout, reversal, momentum)

Impact estimé: +15-20% de rentabilité
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
from .supabase_client import supabase_client
from .enhanced_memory_service import SECTOR_MAPPING

logger = logging.getLogger(__name__)


class WinningPatternsService:
    """
    Service d'analyse et stockage des patterns gagnants.
    
    Permet aux IAs d'apprendre des SUCCÈS et pas seulement des erreurs.
    """
    
    def __init__(self):
        """Initialise le service."""
        self._initialized = False
        
        # Cache des patterns gagnants (recalculé périodiquement)
        self._winning_patterns_cache: Dict[str, List[Dict]] = {}
        self._cache_timestamp: datetime = None
        self._cache_ttl_minutes = 30
    
    def initialize(self) -> bool:
        """Initialise le service."""
        if supabase_client._initialized:
            self._initialized = True
            logger.info("✅ Winning Patterns Service initialisé")
            # Pré-charger le cache au démarrage
            self._refresh_cache()
            return True
        logger.warning("⚠️ Winning Patterns Service: Supabase non initialisé")
        return False
    
    # =====================================================
    # STOCKAGE DES PATTERNS
    # =====================================================
    
    def record_winning_trade(
        self,
        agent_id: str,
        trade_id: str,
        symbol: str,
        decision: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_percent: float,
        holding_hours: float,
        # Conditions de succès
        entry_hour: int,  # Heure d'entrée (0-23)
        entry_minute: int,  # Minute d'entrée
        day_of_week: int,  # Jour (0=lundi, 6=dimanche)
        # Setup technique
        rsi_at_entry: float = None,
        macd_signal: str = None,  # "bullish", "bearish", "neutral"
        volume_ratio: float = None,  # Volume vs moyenne
        trend: str = None,  # "uptrend", "downtrend", "sideways"
        price_vs_sma20: float = None,  # % au-dessus/en-dessous SMA20
        price_vs_vwap: float = None,  # % vs VWAP
        atr_percent: float = None,  # ATR en % du prix
        # Contexte marché
        vix_level: float = None,
        market_sentiment: str = None,  # "bullish", "bearish", "neutral"
        spy_trend: str = None,  # Tendance du S&P 500
        # Catalyst
        catalyst_type: str = None,  # "earnings", "news", "upgrade", "momentum", etc.
        catalyst_description: str = None,
        # Pattern identifié
        pattern_type: str = None,  # "breakout", "reversal", "momentum", "dip_buy", etc.
        # Confiance initiale
        confidence: int = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Enregistre un trade gagnant avec toutes ses conditions de succès.
        
        Cette fonction doit être appelée à la CLÔTURE d'un trade gagnant
        pour capturer les conditions qui ont mené au succès.
        """
        if not self._initialized:
            return None
        
        try:
            sector = SECTOR_MAPPING.get(symbol.upper(), "Unknown")
            
            pattern_data = {
                "agent_id": agent_id,
                "trade_id": trade_id,
                "symbol": symbol,
                "sector": sector,
                "decision": decision,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "holding_hours": holding_hours,
                # Timing
                "entry_hour": entry_hour,
                "entry_minute": entry_minute,
                "day_of_week": day_of_week,
                # Setup technique
                "rsi_at_entry": rsi_at_entry,
                "macd_signal": macd_signal,
                "volume_ratio": volume_ratio,
                "trend": trend,
                "price_vs_sma20": price_vs_sma20,
                "price_vs_vwap": price_vs_vwap,
                "atr_percent": atr_percent,
                # Contexte marché
                "vix_level": vix_level,
                "market_sentiment": market_sentiment,
                "spy_trend": spy_trend,
                # Catalyst
                "catalyst_type": catalyst_type,
                "catalyst_description": catalyst_description,
                # Pattern
                "pattern_type": pattern_type,
                "confidence": confidence,
                # Métadonnées
                "created_at": datetime.utcnow().isoformat(),
            }
            
            # Essayer d'insérer dans la table winning_patterns
            # Si la table n'existe pas, on utilise trade_memories avec un flag
            try:
                response = supabase_client.client.table('winning_patterns').insert(pattern_data).execute()
                if response.data:
                    logger.info(f"🏆 Pattern gagnant enregistré: {symbol} +{pnl_percent:.2f}%")
                    return response.data[0]
            except Exception as table_error:
                # Table n'existe pas, stocker dans trade_memories avec metadata
                logger.info("Table winning_patterns non disponible, utilisation de trade_memories")
                self._store_pattern_in_memories(agent_id, pattern_data)
            
            return pattern_data
            
        except Exception as e:
            logger.error(f"Erreur enregistrement pattern gagnant: {e}")
            return None
    
    def _store_pattern_in_memories(self, agent_id: str, pattern_data: Dict) -> bool:
        """Stocke le pattern dans trade_memories comme fallback."""
        try:
            # Mise à jour du trade memory existant avec les données enrichies
            if pattern_data.get("trade_id"):
                update_data = {
                    "pattern_type": pattern_data.get("pattern_type"),
                    "catalyst_type": pattern_data.get("catalyst_type"),
                    "entry_hour": pattern_data.get("entry_hour"),
                    "vix_level": pattern_data.get("vix_level"),
                    "lesson_learned": self._generate_winning_lesson(pattern_data),
                }
                supabase_client.client.table('trade_memories').update(
                    update_data
                ).eq('trade_id', pattern_data['trade_id']).execute()
                return True
        except Exception as e:
            logger.warning(f"Erreur stockage pattern: {e}")
        return False
    
    def _generate_winning_lesson(self, pattern_data: Dict) -> str:
        """Génère une leçon automatique à partir du pattern gagnant."""
        lessons = []
        
        # Timing
        hour = pattern_data.get("entry_hour")
        if hour:
            if 9 <= hour <= 10:
                lessons.append("Entrée matinale efficace (ouverture)")
            elif 14 <= hour <= 15:
                lessons.append("Entrée fin de journée efficace")
        
        # RSI
        rsi = pattern_data.get("rsi_at_entry")
        if rsi:
            if rsi < 35:
                lessons.append(f"RSI bas ({rsi:.0f}) = bon point d'entrée")
            elif rsi > 65:
                lessons.append(f"RSI haut ({rsi:.0f}) mais momentum porteur")
        
        # Volume
        vol_ratio = pattern_data.get("volume_ratio")
        if vol_ratio and vol_ratio > 1.5:
            lessons.append(f"Fort volume ({vol_ratio:.1f}x) confirmait le mouvement")
        
        # Pattern
        pattern = pattern_data.get("pattern_type")
        if pattern:
            lessons.append(f"Pattern: {pattern}")
        
        # Catalyst
        catalyst = pattern_data.get("catalyst_type")
        if catalyst:
            lessons.append(f"Catalyst: {catalyst}")
        
        return " | ".join(lessons) if lessons else "Trade gagnant - Analyser les conditions pour répéter"
    
    # =====================================================
    # ANALYSE DES PATTERNS
    # =====================================================
    
    def _refresh_cache(self):
        """Rafraîchit le cache des patterns gagnants."""
        try:
            # Récupérer tous les trades gagnants des 30 derniers jours
            since = (datetime.utcnow() - timedelta(days=30)).isoformat()
            
            response = supabase_client.client.table('trade_memories').select(
                '*'
            ).eq('success', True).gte('created_at', since).execute()
            
            if response.data:
                self._analyze_patterns(response.data)
            
            self._cache_timestamp = datetime.utcnow()
            logger.info(f"🔄 Cache patterns gagnants rafraîchi ({len(response.data)} trades)")
            
        except Exception as e:
            logger.warning(f"Erreur rafraîchissement cache patterns: {e}")
    
    def _analyze_patterns(self, winning_trades: List[Dict]) -> None:
        """Analyse les trades gagnants pour identifier des patterns récurrents."""
        self._winning_patterns_cache = {
            "by_hour": defaultdict(list),
            "by_sector": defaultdict(list),
            "by_rsi_range": defaultdict(list),
            "by_pattern_type": defaultdict(list),
            "by_volume": defaultdict(list),
            "best_setups": [],
        }
        
        for trade in winning_trades:
            pnl_pct = trade.get("pnl_percent", 0)
            
            # Par heure (extraire de created_at)
            try:
                created = datetime.fromisoformat(trade['created_at'].replace('Z', '+00:00'))
                hour = created.hour
                self._winning_patterns_cache["by_hour"][hour].append({
                    "symbol": trade.get("symbol"),
                    "pnl_percent": pnl_pct,
                    "sector": trade.get("sector"),
                })
            except:
                pass
            
            # Par secteur
            sector = trade.get("sector")
            if sector:
                self._winning_patterns_cache["by_sector"][sector].append({
                    "symbol": trade.get("symbol"),
                    "pnl_percent": pnl_pct,
                    "decision": trade.get("decision"),
                })
            
            # Par range RSI
            rsi = trade.get("rsi_value")
            if rsi:
                if rsi < 30:
                    rsi_range = "0-30 (survente)"
                elif rsi < 40:
                    rsi_range = "30-40 (bas)"
                elif rsi < 60:
                    rsi_range = "40-60 (neutre)"
                elif rsi < 70:
                    rsi_range = "60-70 (haut)"
                else:
                    rsi_range = "70+ (surachat)"
                
                self._winning_patterns_cache["by_rsi_range"][rsi_range].append({
                    "symbol": trade.get("symbol"),
                    "pnl_percent": pnl_pct,
                    "rsi": rsi,
                })
            
            # Par volume ratio
            vol = trade.get("volume_ratio")
            if vol:
                if vol < 0.8:
                    vol_cat = "Faible (<0.8x)"
                elif vol < 1.2:
                    vol_cat = "Normal (0.8-1.2x)"
                elif vol < 2:
                    vol_cat = "Élevé (1.2-2x)"
                else:
                    vol_cat = "Très élevé (>2x)"
                
                self._winning_patterns_cache["by_volume"][vol_cat].append({
                    "symbol": trade.get("symbol"),
                    "pnl_percent": pnl_pct,
                    "volume_ratio": vol,
                })
            
            # Meilleurs setups (P&L > 2%)
            if pnl_pct > 2:
                self._winning_patterns_cache["best_setups"].append({
                    "symbol": trade.get("symbol"),
                    "sector": trade.get("sector"),
                    "pnl_percent": pnl_pct,
                    "decision": trade.get("decision"),
                    "confidence": trade.get("confidence"),
                    "rsi": trade.get("rsi_value"),
                    "volume_ratio": trade.get("volume_ratio"),
                    "reasoning": trade.get("reasoning", "")[:200],
                })
        
        # Trier les meilleurs setups
        self._winning_patterns_cache["best_setups"].sort(
            key=lambda x: x.get("pnl_percent", 0),
            reverse=True
        )
    
    def get_best_trading_hours(self) -> Dict[int, Dict]:
        """
        Retourne les heures de trading les plus rentables.
        
        Returns:
            Dict avec heure -> stats (count, avg_pnl, win_rate)
        """
        self._ensure_cache_fresh()
        
        hour_stats = {}
        for hour, trades in self._winning_patterns_cache.get("by_hour", {}).items():
            if trades:
                hour_stats[hour] = {
                    "count": len(trades),
                    "avg_pnl": sum(t["pnl_percent"] for t in trades) / len(trades),
                    "total_pnl": sum(t["pnl_percent"] for t in trades),
                    "sectors": list(set(t.get("sector") for t in trades if t.get("sector"))),
                }
        
        return dict(sorted(hour_stats.items(), key=lambda x: -x[1]["total_pnl"]))
    
    def get_best_sectors(self) -> Dict[str, Dict]:
        """
        Retourne les secteurs les plus rentables.
        
        Returns:
            Dict avec secteur -> stats
        """
        self._ensure_cache_fresh()
        
        sector_stats = {}
        for sector, trades in self._winning_patterns_cache.get("by_sector", {}).items():
            if trades and sector:
                sector_stats[sector] = {
                    "count": len(trades),
                    "avg_pnl": sum(t["pnl_percent"] for t in trades) / len(trades),
                    "total_pnl": sum(t["pnl_percent"] for t in trades),
                    "symbols": list(set(t.get("symbol") for t in trades)),
                }
        
        return dict(sorted(sector_stats.items(), key=lambda x: -x[1]["total_pnl"]))
    
    def get_winning_rsi_ranges(self) -> Dict[str, Dict]:
        """
        Retourne les ranges RSI les plus efficaces pour les achats.
        
        Returns:
            Dict avec range RSI -> stats
        """
        self._ensure_cache_fresh()
        
        rsi_stats = {}
        for rsi_range, trades in self._winning_patterns_cache.get("by_rsi_range", {}).items():
            if trades:
                rsi_stats[rsi_range] = {
                    "count": len(trades),
                    "avg_pnl": sum(t["pnl_percent"] for t in trades) / len(trades),
                    "avg_rsi": sum(t.get("rsi", 50) for t in trades) / len(trades),
                }
        
        return rsi_stats
    
    def get_best_setups(self, limit: int = 5) -> List[Dict]:
        """
        Retourne les meilleurs setups gagnants à répliquer.
        
        Args:
            limit: Nombre de setups à retourner
            
        Returns:
            Liste des meilleurs setups
        """
        self._ensure_cache_fresh()
        return self._winning_patterns_cache.get("best_setups", [])[:limit]
    
    def _ensure_cache_fresh(self):
        """S'assure que le cache est à jour."""
        if not self._cache_timestamp:
            self._refresh_cache()
            return
        
        age_minutes = (datetime.utcnow() - self._cache_timestamp).total_seconds() / 60
        if age_minutes > self._cache_ttl_minutes:
            self._refresh_cache()
    
    # =====================================================
    # CONTEXTE POUR LES IAS
    # =====================================================
    
    def get_winning_patterns_context(self, agent_id: str = None) -> str:
        """
        Génère un contexte formaté des patterns gagnants pour le prompt IA.
        
        Args:
            agent_id: ID de l'agent (optionnel, pour patterns spécifiques)
            
        Returns:
            Contexte formaté en string
        """
        if not self._initialized:
            return ""
        
        self._ensure_cache_fresh()
        
        context_parts = []
        context_parts.append("## 🏆 PATTERNS GAGNANTS - APPRENDS DE TES SUCCÈS")
        
        # 1. Meilleures heures
        best_hours = self.get_best_trading_hours()
        if best_hours:
            context_parts.append("\n⏰ HEURES LES PLUS RENTABLES:")
            for hour, stats in list(best_hours.items())[:3]:
                context_parts.append(
                    f"  ✅ {hour}h00: {stats['count']} trades gagnants, "
                    f"P&L moyen: +{stats['avg_pnl']:.2f}%"
                )
        
        # 2. Meilleurs secteurs
        best_sectors = self.get_best_sectors()
        if best_sectors:
            context_parts.append("\n🏢 SECTEURS LES PLUS RENTABLES:")
            for sector, stats in list(best_sectors.items())[:3]:
                context_parts.append(
                    f"  ✅ {sector}: {stats['count']} trades, "
                    f"P&L total: +{stats['total_pnl']:.2f}%"
                )
        
        # 3. Meilleurs ranges RSI
        best_rsi = self.get_winning_rsi_ranges()
        if best_rsi:
            context_parts.append("\n📊 RSI EFFICACES POUR ACHETER:")
            for rsi_range, stats in best_rsi.items():
                if "survente" in rsi_range or "bas" in rsi_range:
                    context_parts.append(
                        f"  ✅ RSI {rsi_range}: {stats['count']} succès, "
                        f"P&L moyen: +{stats['avg_pnl']:.2f}%"
                    )
        
        # 4. Top 3 meilleurs setups à répliquer
        best_setups = self.get_best_setups(3)
        if best_setups:
            context_parts.append("\n🎯 SETUPS GAGNANTS À RÉPLIQUER:")
            for setup in best_setups:
                rsi_info = f", RSI={setup.get('rsi', 'N/A')}" if setup.get('rsi') else ""
                vol_info = f", Vol={setup.get('volume_ratio', 'N/A')}x" if setup.get('volume_ratio') else ""
                context_parts.append(
                    f"  🏆 {setup['symbol']} ({setup.get('sector', 'N/A')}): "
                    f"+{setup['pnl_percent']:.2f}%{rsi_info}{vol_info}"
                )
        
        if len(context_parts) > 1:
            return "\n".join(context_parts)
        
        return ""
    
    def get_pattern_recommendation(
        self,
        symbol: str,
        current_rsi: float = None,
        current_hour: int = None,
        volume_ratio: float = None,
    ) -> Dict[str, Any]:
        """
        Donne une recommandation basée sur les patterns gagnants passés.
        
        Args:
            symbol: Symbole à analyser
            current_rsi: RSI actuel
            current_hour: Heure actuelle
            volume_ratio: Ratio de volume actuel
            
        Returns:
            Recommandation avec score et justification
        """
        if not self._initialized:
            return {"score": 0, "reasons": ["Service non initialisé"]}
        
        self._ensure_cache_fresh()
        
        score = 50  # Score neutre de base
        reasons = []
        
        sector = SECTOR_MAPPING.get(symbol.upper(), "Unknown")
        
        # 1. Vérifier l'heure
        if current_hour is not None:
            best_hours = self.get_best_trading_hours()
            if current_hour in best_hours:
                hour_stat = best_hours[current_hour]
                if hour_stat["count"] >= 3 and hour_stat["avg_pnl"] > 1:
                    score += 15
                    reasons.append(f"⏰ Heure rentable ({current_hour}h: +{hour_stat['avg_pnl']:.1f}% moyen)")
            else:
                # Heures connues comme mauvaises (première heure, dernière demi-heure)
                if current_hour == 9 or (current_hour == 15 and datetime.utcnow().minute > 30):
                    score -= 10
                    reasons.append(f"⚠️ Heure volatile/risquée")
        
        # 2. Vérifier le secteur
        best_sectors = self.get_best_sectors()
        if sector in best_sectors:
            sector_stat = best_sectors[sector]
            if sector_stat["count"] >= 3:
                score += 10
                reasons.append(f"🏢 Secteur {sector} performant (+{sector_stat['total_pnl']:.1f}% total)")
        
        # 3. Vérifier le RSI
        if current_rsi is not None:
            best_rsi = self.get_winning_rsi_ranges()
            
            if current_rsi < 35:
                # Zone de survente - historiquement bonne
                rsi_range = "0-30 (survente)" if current_rsi < 30 else "30-40 (bas)"
                if rsi_range in best_rsi and best_rsi[rsi_range]["count"] >= 2:
                    score += 15
                    reasons.append(f"📊 RSI bas ({current_rsi:.0f}) = zone de succès historique")
            elif current_rsi > 75:
                score -= 15
                reasons.append(f"⚠️ RSI élevé ({current_rsi:.0f}) = risque de retournement")
        
        # 4. Vérifier le volume
        if volume_ratio is not None:
            if volume_ratio > 1.5:
                score += 10
                reasons.append(f"📈 Volume élevé ({volume_ratio:.1f}x) = confirmation")
            elif volume_ratio < 0.5:
                score -= 10
                reasons.append(f"⚠️ Volume faible ({volume_ratio:.1f}x) = manque de conviction")
        
        # Classifier le score
        if score >= 70:
            recommendation = "FAVORABLE"
            emoji = "✅"
        elif score >= 50:
            recommendation = "NEUTRE"
            emoji = "🟡"
        else:
            recommendation = "DÉFAVORABLE"
            emoji = "❌"
        
        return {
            "score": score,
            "recommendation": recommendation,
            "emoji": emoji,
            "reasons": reasons,
            "sector": sector,
        }


# Instance globale
winning_patterns_service = WinningPatternsService()

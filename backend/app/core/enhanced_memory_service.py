"""
Enhanced Memory Service - Mémoire RAG Améliorée V2.3 + V2.4 Winning Patterns.

Ce service améliore l'utilisation de la mémoire RAG:
1. Contexte PRÉ-DÉCISION: Stats générales de l'agent
2. Contexte POST-DÉCISION: Mémoire spécifique au symbole choisi
3. Stockage enrichi: Symbole, Secteur, ET Indicateurs techniques
4. V2.4: Intégration des patterns gagnants

Impact estimé: +15-25% de rentabilité
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from .memory_service import memory_service
from .supabase_client import supabase_client

logger = logging.getLogger(__name__)

# Import différé pour éviter les imports circulaires
_winning_patterns_service = None

def get_winning_patterns_service():
    """Récupère le service de patterns gagnants (import différé)."""
    global _winning_patterns_service
    if _winning_patterns_service is None:
        try:
            from .winning_patterns_service import winning_patterns_service
            _winning_patterns_service = winning_patterns_service
        except ImportError:
            pass
    return _winning_patterns_service


# Mapping des symboles vers leurs secteurs
SECTOR_MAPPING = {
    # Tech
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology", "GOOG": "Technology",
    "META": "Technology", "NVDA": "Technology", "AMD": "Technology", "INTC": "Technology",
    "TSLA": "Technology", "AMZN": "Technology", "CRM": "Technology", "ORCL": "Technology",
    "ADBE": "Technology", "NOW": "Technology", "UBER": "Technology", "LYFT": "Technology",
    "NFLX": "Technology", "PYPL": "Technology", "SQ": "Technology", "SHOP": "Technology",
    "SNOW": "Technology", "PLTR": "Technology", "NET": "Technology", "DDOG": "Technology",
    "ZS": "Technology", "CRWD": "Technology", "PANW": "Technology", "OKTA": "Technology",
    "MDB": "Technology", "TEAM": "Technology", "TWLO": "Technology", "U": "Technology",
    "RBLX": "Technology", "COIN": "Technology", "HOOD": "Technology", "AFRM": "Technology",
    "SOFI": "Technology", "UPST": "Technology", "MELI": "Technology", "SE": "Technology",
    
    # Semiconducteurs
    "TSM": "Semiconductors", "ASML": "Semiconductors", "AVGO": "Semiconductors",
    "QCOM": "Semiconductors", "TXN": "Semiconductors", "MU": "Semiconductors",
    "LRCX": "Semiconductors", "KLAC": "Semiconductors", "AMAT": "Semiconductors",
    "MRVL": "Semiconductors", "ON": "Semiconductors", "SWKS": "Semiconductors",
    "ADI": "Semiconductors", "NXPI": "Semiconductors", "MPWR": "Semiconductors",
    
    # Finance
    "JPM": "Finance", "BAC": "Finance", "WFC": "Finance", "C": "Finance",
    "GS": "Finance", "MS": "Finance", "BLK": "Finance", "SCHW": "Finance",
    "V": "Finance", "MA": "Finance", "AXP": "Finance", "DFS": "Finance",
    "COF": "Finance", "USB": "Finance", "PNC": "Finance", "TFC": "Finance",
    "BRK.A": "Finance", "BRK.B": "Finance", "SPGI": "Finance", "MCO": "Finance",
    
    # Santé
    "JNJ": "Healthcare", "UNH": "Healthcare", "PFE": "Healthcare", "MRK": "Healthcare",
    "ABBV": "Healthcare", "LLY": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare",
    "DHR": "Healthcare", "BMY": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare",
    "CVS": "Healthcare", "CI": "Healthcare", "HUM": "Healthcare", "ELV": "Healthcare",
    "ISRG": "Healthcare", "VRTX": "Healthcare", "REGN": "Healthcare", "BIIB": "Healthcare",
    "MRNA": "Healthcare", "ZTS": "Healthcare", "DXCM": "Healthcare", "IDXX": "Healthcare",
    
    # Consommation
    "WMT": "Consumer", "PG": "Consumer", "KO": "Consumer", "PEP": "Consumer",
    "COST": "Consumer", "HD": "Consumer", "NKE": "Consumer", "MCD": "Consumer",
    "SBUX": "Consumer", "TGT": "Consumer", "LOW": "Consumer", "TJX": "Consumer",
    "CMG": "Consumer", "YUM": "Consumer", "DG": "Consumer", "DLTR": "Consumer",
    "DPZ": "Consumer", "LULU": "Consumer", "ROST": "Consumer", "ULTA": "Consumer",
    
    # Énergie
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
    "EOG": "Energy", "PXD": "Energy", "OXY": "Energy", "MPC": "Energy",
    "VLO": "Energy", "PSX": "Energy", "HAL": "Energy", "BKR": "Energy",
    "DVN": "Energy", "FANG": "Energy", "HES": "Energy", "MRO": "Energy",
    
    # Industrie
    "BA": "Industrial", "CAT": "Industrial", "RTX": "Industrial", "UNP": "Industrial",
    "UPS": "Industrial", "FDX": "Industrial", "DE": "Industrial", "GE": "Industrial",
    "HON": "Industrial", "MMM": "Industrial", "LMT": "Industrial", "NOC": "Industrial",
    "GD": "Industrial", "WM": "Industrial", "RSG": "Industrial", "LHX": "Industrial",
    
    # Communication
    "DIS": "Communication", "CMCSA": "Communication", "VZ": "Communication", "T": "Communication",
    "TMUS": "Communication", "CHTR": "Communication", "ATVI": "Communication", "EA": "Communication",
    "TTWO": "Communication", "WBD": "Communication", "PARA": "Communication", "FOX": "Communication",
    
    # Immobilier
    "PLD": "Real Estate", "AMT": "Real Estate", "CCI": "Real Estate", "EQIX": "Real Estate",
    "SPG": "Real Estate", "O": "Real Estate", "WELL": "Real Estate", "PSA": "Real Estate",
    "AVB": "Real Estate", "EQR": "Real Estate", "DLR": "Real Estate", "VTR": "Real Estate",
    
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "D": "Utilities",
    "AEP": "Utilities", "EXC": "Utilities", "SRE": "Utilities", "XEL": "Utilities",
    
    # Matériaux
    "LIN": "Materials", "APD": "Materials", "SHW": "Materials", "FCX": "Materials",
    "NEM": "Materials", "NUE": "Materials", "DOW": "Materials", "DD": "Materials",
}


class EnhancedMemoryService:
    """
    Service de mémoire RAG amélioré.
    
    Résout le problème où symbol et sector sont toujours None
    en les remplissant automatiquement.
    """
    
    def __init__(self):
        """Initialise le service."""
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialise le service."""
        if memory_service._initialized:
            self._initialized = True
            logger.info("✅ Enhanced Memory Service initialisé")
            return True
        logger.warning("⚠️ Enhanced Memory Service: Memory Service non initialisé")
        return False
    
    def get_sector_for_symbol(self, symbol: str) -> str:
        """
        Retourne le secteur d'un symbole.
        
        Args:
            symbol: Symbole de l'action
            
        Returns:
            Nom du secteur ou "Unknown"
        """
        return SECTOR_MAPPING.get(symbol.upper(), "Unknown")
    
    def get_pre_decision_context(
        self,
        agent_id: str,
        market_sentiment: str = None,
        current_hour: int = None,
    ) -> str:
        """
        Génère le contexte mémoire AVANT la décision.
        Inclut les stats générales sans symbole spécifique.
        V2.4: Inclut maintenant les patterns gagnants.
        
        Args:
            agent_id: ID de l'agent
            market_sentiment: Sentiment de marché actuel
            current_hour: Heure actuelle (pour patterns)
            
        Returns:
            Contexte formaté pour le prompt
        """
        if not self._initialized:
            return ""
        
        context_parts = []
        
        # V2.4: Ajouter les patterns gagnants en premier
        wp_service = get_winning_patterns_service()
        if wp_service and wp_service._initialized:
            winning_context = wp_service.get_winning_patterns_context(agent_id)
            if winning_context:
                context_parts.append(winning_context)
        
        # 1. Performance par niveau de confiance (toujours utile)
        try:
            conf_stats = memory_service.get_agent_performance_by_criteria(agent_id, "confidence")
            if conf_stats:
                context_parts.append("\n## 🧠 TON HISTORIQUE D'APPRENTISSAGE")
                context_parts.append("\n📊 TA PERFORMANCE PAR NIVEAU DE CONFIANCE:")
                for conf_level, stats in sorted(conf_stats.items()):
                    win_rate = stats['win_rate'] * 100
                    emoji = "✅" if win_rate > 55 else "⚠️" if win_rate > 45 else "❌"
                    context_parts.append(
                        f"  {emoji} {conf_level}: {stats['total']} trades, "
                        f"Win Rate: {win_rate:.0f}%, P&L moyen: ${stats['avg_pnl']:.2f}"
                    )
        except Exception as e:
            logger.warning(f"Erreur récupération stats confiance: {e}")
        
        # 2. Performance par secteur
        try:
            sector_stats = memory_service.get_agent_performance_by_criteria(agent_id, "sector")
            if sector_stats:
                context_parts.append("\n🏢 TA PERFORMANCE PAR SECTEUR:")
                for sector, stats in sorted(sector_stats.items(), key=lambda x: -x[1].get('win_rate', 0)):
                    if sector and sector != "unknown" and sector != "None":
                        win_rate = stats['win_rate'] * 100
                        emoji = "✅" if win_rate > 55 else "⚠️" if win_rate > 45 else "❌"
                        context_parts.append(
                            f"  {emoji} {sector}: {stats['total']} trades, "
                            f"Win Rate: {win_rate:.0f}%"
                        )
        except Exception as e:
            logger.warning(f"Erreur récupération stats secteur: {e}")
        
        # 3. Leçons globales récentes (3 dernières erreurs)
        try:
            response = supabase_client.client.table('trade_memories').select(
                'symbol, decision, pnl_percent, success, lesson_learned, sector'
            ).eq('agent_id', agent_id).eq('success', False).order(
                'created_at', desc=True
            ).limit(3).execute()
            
            if response.data:
                context_parts.append("\n❌ TES 3 DERNIÈRES ERREURS (apprends de tes erreurs!):")
                for mem in response.data:
                    context_parts.append(
                        f"  - {mem['decision']} {mem['symbol']} ({mem.get('sector', 'N/A')}): "
                        f"{mem['pnl_percent']:+.2f}%"
                    )
                    if mem.get('lesson_learned'):
                        context_parts.append(f"    → Leçon: {mem['lesson_learned']}")
        except Exception as e:
            logger.warning(f"Erreur récupération erreurs: {e}")
        
        # 4. Statistiques globales
        try:
            stats_response = supabase_client.client.table('agent_statistics').select('*').eq('agent_id', agent_id).single().execute()
            if stats_response.data:
                stats = stats_response.data
                context_parts.append(
                    f"\n📈 TES STATS GLOBALES: "
                    f"{stats['total_trades']} trades, "
                    f"Win Rate: {stats['win_rate']*100:.1f}%, "
                    f"Ratio Gain/Perte: {stats['win_loss_ratio']:.2f}"
                )
                
                # Conseils basés sur les stats
                if stats['win_rate'] < 0.45:
                    context_parts.append("⚠️ Ton win rate est bas. Sois plus sélectif dans tes trades!")
                elif stats['win_rate'] > 0.55:
                    context_parts.append("✅ Bon win rate! Continue sur cette lancée.")
        except:
            pass
        
        if context_parts:
            return "\n".join(context_parts)
        
        return ""
    
    def get_symbol_specific_context(
        self,
        agent_id: str,
        symbol: str,
        current_rsi: float = None,
        current_hour: int = None,
        volume_ratio: float = None,
    ) -> str:
        """
        Génère le contexte mémoire SPÉCIFIQUE à un symbole.
        À appeler APRÈS que l'IA a choisi un symbole.
        V2.4: Inclut les recommandations basées sur patterns gagnants.
        
        Args:
            agent_id: ID de l'agent
            symbol: Symbole de l'action
            current_rsi: RSI actuel du symbole
            current_hour: Heure actuelle
            volume_ratio: Ratio de volume actuel
            
        Returns:
            Contexte formaté pour le prompt
        """
        if not self._initialized or not symbol:
            return ""
        
        context_parts = []
        sector = self.get_sector_for_symbol(symbol)
        
        context_parts.append(f"## 🔍 MÉMOIRE SPÉCIFIQUE: {symbol} ({sector})")
        
        # V2.4: Recommandation basée sur les patterns gagnants
        wp_service = get_winning_patterns_service()
        if wp_service and wp_service._initialized:
            recommendation = wp_service.get_pattern_recommendation(
                symbol=symbol,
                current_rsi=current_rsi,
                current_hour=current_hour,
                volume_ratio=volume_ratio,
            )
            if recommendation and recommendation.get("reasons"):
                context_parts.append(f"\n🎯 ANALYSE PATTERNS GAGNANTS pour {symbol}:")
                context_parts.append(
                    f"  Score: {recommendation['score']}/100 - "
                    f"{recommendation['emoji']} {recommendation['recommendation']}"
                )
                for reason in recommendation.get("reasons", []):
                    context_parts.append(f"    {reason}")
        
        # 1. Historique sur ce symbole précis
        try:
            lessons = memory_service.get_lessons_for_symbol(agent_id, symbol, limit=5)
            if lessons:
                context_parts.append(f"\n📚 TON HISTORIQUE SUR {symbol}:")
                for lesson in lessons:
                    context_parts.append(f"  {lesson}")
            else:
                context_parts.append(f"\n📚 Aucun historique sur {symbol} - C'est ta première fois!")
        except Exception as e:
            logger.warning(f"Erreur récupération historique {symbol}: {e}")
        
        # 2. Performance sur ce secteur
        if sector and sector != "Unknown":
            try:
                sector_stats = memory_service.get_agent_performance_by_criteria(agent_id, "sector")
                if sector in sector_stats:
                    s = sector_stats[sector]
                    win_rate = s['win_rate'] * 100
                    context_parts.append(
                        f"\n🏢 TON HISTORIQUE SECTEUR {sector}: "
                        f"{s['total']} trades, Win Rate: {win_rate:.0f}%, P&L total: ${s['total_pnl']:.2f}"
                    )
                    
                    if win_rate < 40:
                        context_parts.append(f"⚠️ Tu n'es pas bon sur le secteur {sector}. Réfléchis bien avant de trader!")
                    elif win_rate > 60:
                        context_parts.append(f"✅ Tu as de bons résultats sur {sector}. Continue!")
            except Exception as e:
                logger.warning(f"Erreur récupération stats secteur: {e}")
        
        # 3. Trades similaires récents (même secteur)
        try:
            similar = memory_service.get_similar_trades(
                agent_id,
                sector=sector,
                limit=3
            )
            if similar:
                context_parts.append(f"\n🔄 TRADES RÉCENTS SECTEUR {sector}:")
                for mem in similar[:3]:
                    outcome = "✅" if mem['success'] else "❌"
                    context_parts.append(
                        f"  {outcome} {mem['symbol']}: {mem['decision']} - "
                        f"P&L: {mem['pnl_percent']:+.2f}%"
                    )
        except Exception as e:
            logger.warning(f"Erreur récupération trades similaires: {e}")
        
        if len(context_parts) > 1:  # Plus que juste le titre
            return "\n".join(context_parts)
        
        return ""
    
    def create_enriched_trade_memory(
        self,
        agent_id: str,
        trade_id: str,
        symbol: str,
        decision: str,
        entry_price: float,
        quantity: float,
        reasoning: str,
        confidence: int,
        technical_data: Dict[str, Any] = None,
        smart_money_data: Dict[str, Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Crée un souvenir de trade ENRICHI avec symbole et secteur.
        
        Args:
            agent_id: ID de l'agent
            trade_id: ID du trade
            symbol: Symbole de l'action
            decision: BUY ou SELL
            entry_price: Prix d'entrée
            quantity: Quantité
            reasoning: Raisonnement
            confidence: Confiance (0-100)
            technical_data: Données techniques (RSI, MACD, etc.)
            smart_money_data: Données Smart Money
            
        Returns:
            Mémoire créée ou None
        """
        if not self._initialized:
            return None
        
        # Enrichir avec le secteur
        sector = self.get_sector_for_symbol(symbol)
        
        # Construire le contexte de marché enrichi
        market_context = {
            "sector": sector,
            "symbol": symbol,
        }
        
        # Ajouter les indicateurs techniques si disponibles
        if technical_data:
            market_context.update({
                "rsi": technical_data.get("rsi"),
                "volume_ratio": technical_data.get("volume_ratio"),
                "trend": technical_data.get("trend"),
            })
        
        # Ajouter le sentiment Smart Money
        if smart_money_data:
            market_context.update({
                "vix": smart_money_data.get("vix", {}).get("vix"),
                "sentiment": smart_money_data.get("overall_signal"),
            })
        
        return memory_service.create_trade_memory(
            agent_id=agent_id,
            trade_id=trade_id,
            symbol=symbol,
            decision=decision,
            entry_price=entry_price,
            quantity=quantity,
            reasoning=reasoning,
            confidence=confidence,
            market_context=market_context,
            smart_money_data=smart_money_data,
        )
    
    def close_trade_with_lesson(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
        exit_reason: str = None,
    ) -> bool:
        """
        Ferme un souvenir de trade avec une leçon automatique.
        
        Args:
            trade_id: ID du trade
            exit_price: Prix de sortie
            pnl: P&L
            exit_reason: Raison de sortie (Stop-Loss, Take-Profit, etc.)
            
        Returns:
            True si succès
        """
        if not self._initialized:
            return False
        
        # Générer une leçon automatique
        lesson = None
        if pnl < 0:
            if exit_reason and "stop" in exit_reason.lower():
                lesson = "Stop-Loss déclenché - Le timing d'entrée était peut-être mauvais"
            else:
                lesson = "Perte - Analyser les indicateurs techniques avant la prochaine fois"
        elif pnl > 0:
            if exit_reason and "profit" in exit_reason.lower():
                lesson = "Prise de profit réussie - Bonne discipline"
            else:
                lesson = "Gain - Identifier ce qui a bien fonctionné pour répéter"
        
        return memory_service.close_trade_memory(
            trade_id=trade_id,
            exit_price=exit_price,
            pnl=pnl,
            lesson_learned=lesson,
        )


# Instance globale
enhanced_memory_service = EnhancedMemoryService()

"""
Memory Service - Cerveau Collectif des IAs (Mémoire RAG).
Stocke et récupère les souvenirs de trading pour que les IAs apprennent de leurs erreurs
ET de leurs SUCCÈS (V2.4: Winning Patterns).
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
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


class MemoryService:
    """
    Service de mémoire long terme pour les agents IA.
    Permet aux IAs d'apprendre de leurs trades passés.
    """
    
    def __init__(self):
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialise le service de mémoire."""
        if supabase_client._initialized:
            self._initialized = True
            logger.info("✅ Memory Service initialisé")
            return True
        logger.warning("⚠️ Memory Service: Supabase non initialisé")
        return False
    
    # =====================================================
    # CRÉATION DE SOUVENIRS
    # =====================================================
    
    def create_trade_memory(
        self,
        agent_id: str,
        trade_id: str,
        symbol: str,
        decision: str,
        entry_price: float,
        quantity: float,
        reasoning: str,
        confidence: int,
        market_context: Dict[str, Any] = None,
        smart_money_data: Dict[str, Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Crée un souvenir de trade au moment de l'entrée.
        Le résultat sera mis à jour lors de la clôture.
        """
        if not self._initialized:
            return None
        
        try:
            memory_data = {
                "agent_id": agent_id,
                "trade_id": trade_id,
                "symbol": symbol,
                "decision": decision,
                "entry_price": entry_price,
                "quantity": quantity,
                "reasoning": reasoning[:1000] if reasoning else "",
                "confidence": confidence,
            }
            
            # Ajouter le contexte de marché si disponible
            if market_context:
                memory_data.update({
                    "market_sentiment": market_context.get("sentiment"),
                    "vix_level": market_context.get("vix"),
                    "sector": market_context.get("sector"),
                    "market_trend": market_context.get("trend"),
                    "rsi_value": market_context.get("rsi"),
                    "volume_ratio": market_context.get("volume_ratio"),
                    "price_vs_sma20": market_context.get("price_vs_sma20"),
                })
            
            # Ajouter les données Smart Money si disponibles
            if smart_money_data:
                memory_data.update({
                    "dark_pool_ratio": smart_money_data.get("dark_pool_ratio"),
                    "options_sentiment": smart_money_data.get("options_sentiment"),
                    "insider_activity": smart_money_data.get("insider_activity"),
                })
            
            response = supabase_client.client.table('trade_memories').insert(memory_data).execute()
            
            if response.data:
                logger.info(f"🧠 Mémoire créée pour {symbol} - Agent {agent_id}")
                return response.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Erreur création mémoire: {e}")
            return None
    
    def close_trade_memory(
        self,
        memory_id: str = None,
        trade_id: str = None,
        exit_price: float = None,
        pnl: float = None,
        lesson_learned: str = None,
    ) -> bool:
        """
        Ferme un souvenir de trade avec le résultat final.
        Peut être appelé par memory_id ou trade_id.
        """
        if not self._initialized:
            return False
        
        try:
            # Récupérer la mémoire
            if memory_id:
                query = supabase_client.client.table('trade_memories').select('*').eq('id', memory_id)
            elif trade_id:
                query = supabase_client.client.table('trade_memories').select('*').eq('trade_id', trade_id)
            else:
                return False
            
            response = query.single().execute()
            memory = response.data
            
            if not memory:
                return False
            
            # Calculer le résultat
            entry_price = float(memory['entry_price'])
            quantity = float(memory['quantity'])
            decision = memory['decision']
            
            if exit_price is None:
                exit_price = entry_price  # Si pas de prix de sortie, supposer sortie à l'entrée
            
            # Calcul du P&L
            if pnl is None:
                if decision == "BUY":
                    pnl = (exit_price - entry_price) * quantity
                else:  # SELL
                    pnl = (entry_price - exit_price) * quantity
            
            pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price * quantity > 0 else 0
            success = pnl > 0
            
            # Calculer la durée
            created_at = datetime.fromisoformat(memory['created_at'].replace('Z', '+00:00'))
            holding_hours = int((datetime.now(created_at.tzinfo) - created_at).total_seconds() / 3600)
            
            # Mettre à jour la mémoire
            update_data = {
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "success": success,
                "holding_duration_hours": holding_hours,
                "closed_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            
            if lesson_learned:
                update_data["lesson_learned"] = lesson_learned
            
            supabase_client.client.table('trade_memories').update(update_data).eq('id', memory['id']).execute()
            
            # Mettre à jour les statistiques de l'agent
            self._update_agent_statistics(memory['agent_id'])
            
            # V2.4: Si trade gagnant, enregistrer le pattern pour apprentissage
            if success and pnl_percent > 0.5:  # Seuil minimum 0.5%
                self._record_winning_pattern(memory, exit_price, pnl, pnl_percent, holding_hours)
            
            logger.info(f"🧠 Mémoire fermée: {memory['symbol']} - P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)")
            return True
            
        except Exception as e:
            logger.error(f"Erreur fermeture mémoire: {e}")
            return False
    
    def _update_agent_statistics(self, agent_id: str) -> bool:
        """Appelle la fonction SQL pour mettre à jour les stats."""
        try:
            supabase_client.client.rpc('update_agent_statistics', {'p_agent_id': agent_id}).execute()
            return True
        except Exception as e:
            logger.warning(f"Erreur mise à jour stats: {e}")
            return False
    
    def _record_winning_pattern(
        self,
        memory: Dict[str, Any],
        exit_price: float,
        pnl: float,
        pnl_percent: float,
        holding_hours: int
    ) -> bool:
        """
        V2.4: Enregistre automatiquement un pattern gagnant.
        
        Capture les conditions de succès pour permettre aux IAs
        de reproduire les setups gagnants.
        """
        try:
            wp_service = get_winning_patterns_service()
            if not wp_service or not wp_service._initialized:
                return False
            
            # Extraire l'heure d'entrée depuis created_at
            created_at = datetime.fromisoformat(memory['created_at'].replace('Z', '+00:00'))
            entry_hour = created_at.hour
            entry_minute = created_at.minute
            day_of_week = created_at.weekday()
            
            # Extraire les données techniques du market_context
            rsi = memory.get('rsi_value')
            volume_ratio = memory.get('volume_ratio')
            trend = memory.get('market_trend')
            vix_level = memory.get('vix_level')
            market_sentiment = memory.get('market_sentiment')
            
            # Détecter le type de pattern basé sur les indicateurs
            pattern_type = self._detect_pattern_type(
                decision=memory.get('decision'),
                rsi=rsi,
                volume_ratio=volume_ratio,
                pnl_percent=pnl_percent
            )
            
            wp_service.record_winning_trade(
                agent_id=memory.get('agent_id'),
                trade_id=memory.get('trade_id'),
                symbol=memory.get('symbol'),
                decision=memory.get('decision'),
                entry_price=float(memory.get('entry_price', 0)),
                exit_price=exit_price,
                pnl=pnl,
                pnl_percent=pnl_percent,
                holding_hours=holding_hours,
                entry_hour=entry_hour,
                entry_minute=entry_minute,
                day_of_week=day_of_week,
                rsi_at_entry=rsi,
                volume_ratio=volume_ratio,
                trend=trend,
                vix_level=vix_level,
                market_sentiment=market_sentiment,
                pattern_type=pattern_type,
                confidence=memory.get('confidence'),
            )
            
            logger.info(f"🏆 Pattern gagnant enregistré: {memory.get('symbol')} +{pnl_percent:.2f}%")
            return True
            
        except Exception as e:
            logger.warning(f"Erreur enregistrement pattern gagnant: {e}")
            return False
    
    def _detect_pattern_type(
        self,
        decision: str,
        rsi: float = None,
        volume_ratio: float = None,
        pnl_percent: float = None
    ) -> str:
        """Détecte le type de pattern basé sur les indicateurs."""
        if decision == "BUY":
            if rsi and rsi < 35:
                return "dip_buy"  # Achat sur survente
            elif volume_ratio and volume_ratio > 2:
                return "breakout"  # Cassure avec volume
            elif pnl_percent and pnl_percent > 3:
                return "momentum"  # Momentum fort
            else:
                return "trend_following"  # Suivi de tendance
        else:  # SELL
            if rsi and rsi > 65:
                return "overbought_sell"  # Vente surachat
            elif volume_ratio and volume_ratio > 2:
                return "distribution"  # Distribution
            else:
                return "profit_taking"  # Prise de profit
    
    # =====================================================
    # RÉCUPÉRATION DE SOUVENIRS
    # =====================================================
    
    def get_similar_trades(
        self,
        agent_id: str,
        symbol: str = None,
        sector: str = None,
        market_sentiment: str = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Récupère les trades similaires passés pour apprendre.
        Retourne les trades fermés avec leur résultat.
        """
        if not self._initialized:
            return []
        
        try:
            query = supabase_client.client.table('trade_memories').select('*')
            query = query.eq('agent_id', agent_id)
            query = query.not_.is_('success', 'null')  # Uniquement les trades fermés
            
            if symbol:
                query = query.eq('symbol', symbol)
            if sector:
                query = query.eq('sector', sector)
            if market_sentiment:
                query = query.eq('market_sentiment', market_sentiment)
            
            response = query.order('created_at', desc=True).limit(limit).execute()
            return response.data
            
        except Exception as e:
            logger.error(f"Erreur récupération souvenirs: {e}")
            return []
    
    def get_agent_performance_by_criteria(
        self,
        agent_id: str,
        criteria: str,  # "sector", "confidence", "market_sentiment", "vix_level"
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyse la performance d'un agent selon différents critères.
        Retourne les stats par catégorie.
        """
        if not self._initialized:
            return {}
        
        try:
            query = supabase_client.client.table('trade_memories').select('*')
            query = query.eq('agent_id', agent_id)
            query = query.not_.is_('success', 'null')
            
            response = query.execute()
            memories = response.data
            
            if not memories:
                return {}
            
            # Grouper par critère
            stats = {}
            for memory in memories:
                key = memory.get(criteria) or "unknown"
                
                if criteria == "confidence":
                    # Grouper par tranches de confiance
                    conf = memory.get("confidence", 0)
                    if conf < 60:
                        key = "50-60%"
                    elif conf < 70:
                        key = "60-70%"
                    elif conf < 80:
                        key = "70-80%"
                    elif conf < 90:
                        key = "80-90%"
                    else:
                        key = "90-100%"
                
                if key not in stats:
                    stats[key] = {"total": 0, "wins": 0, "losses": 0, "total_pnl": 0}
                
                stats[key]["total"] += 1
                if memory.get("success"):
                    stats[key]["wins"] += 1
                else:
                    stats[key]["losses"] += 1
                stats[key]["total_pnl"] += float(memory.get("pnl", 0))
            
            # Calculer les win rates
            for key in stats:
                total = stats[key]["total"]
                stats[key]["win_rate"] = stats[key]["wins"] / total if total > 0 else 0
                stats[key]["avg_pnl"] = stats[key]["total_pnl"] / total if total > 0 else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur analyse performance: {e}")
            return {}
    
    def get_lessons_for_symbol(
        self,
        agent_id: str,
        symbol: str,
        limit: int = 5,
    ) -> List[str]:
        """
        Récupère les leçons apprises pour un symbole spécifique.
        """
        if not self._initialized:
            return []
        
        try:
            response = supabase_client.client.table('trade_memories').select(
                'symbol, decision, pnl, pnl_percent, success, reasoning, lesson_learned, confidence, market_sentiment'
            ).eq('agent_id', agent_id).eq('symbol', symbol).not_.is_('success', 'null').order(
                'created_at', desc=True
            ).limit(limit).execute()
            
            lessons = []
            for mem in response.data:
                outcome = "✅ GAIN" if mem['success'] else "❌ PERTE"
                lesson = (
                    f"{outcome}: {mem['decision']} {symbol} - "
                    f"P&L: {mem['pnl_percent']:+.2f}% (confiance: {mem['confidence']}%)"
                )
                if mem.get('lesson_learned'):
                    lesson += f" | Leçon: {mem['lesson_learned']}"
                lessons.append(lesson)
            
            return lessons
            
        except Exception as e:
            logger.error(f"Erreur récupération leçons: {e}")
            return []
    
    def format_memory_context_for_agent(
        self,
        agent_id: str,
        current_symbol: str = None,
        current_sector: str = None,
        current_sentiment: str = None,
        limit: int = 10,
    ) -> str:
        """
        Formate le contexte mémoire pour l'inclure dans le prompt de l'agent.
        C'est la fonction clé qui rend l'IA "consciente" de son passé.
        """
        if not self._initialized:
            return ""
        
        context_parts = []
        
        # 1. Leçons spécifiques au symbole
        if current_symbol:
            lessons = self.get_lessons_for_symbol(agent_id, current_symbol, limit=3)
            if lessons:
                context_parts.append(f"📚 HISTORIQUE SUR {current_symbol}:")
                context_parts.extend(lessons)
        
        # 2. Performance par niveau de confiance
        conf_stats = self.get_agent_performance_by_criteria(agent_id, "confidence")
        if conf_stats:
            context_parts.append("\n📊 TA PERFORMANCE PAR NIVEAU DE CONFIANCE:")
            for conf_level, stats in sorted(conf_stats.items()):
                win_rate = stats['win_rate'] * 100
                context_parts.append(
                    f"  - {conf_level}: {stats['total']} trades, "
                    f"Win Rate: {win_rate:.0f}%, P&L moyen: ${stats['avg_pnl']:.2f}"
                )
        
        # 3. Performance par secteur
        if current_sector:
            sector_stats = self.get_agent_performance_by_criteria(agent_id, "sector")
            if current_sector in sector_stats:
                s = sector_stats[current_sector]
                context_parts.append(
                    f"\n🏢 PERFORMANCE SECTEUR {current_sector}: "
                    f"{s['total']} trades, Win Rate: {s['win_rate']*100:.0f}%"
                )
        
        # 4. Trades similaires récents
        similar = self.get_similar_trades(
            agent_id, 
            sector=current_sector, 
            market_sentiment=current_sentiment,
            limit=5
        )
        if similar:
            context_parts.append("\n🔄 TRADES SIMILAIRES RÉCENTS:")
            for mem in similar[:3]:
                outcome = "✅" if mem['success'] else "❌"
                context_parts.append(
                    f"  {outcome} {mem['symbol']} ({mem['sector'] or 'N/A'}): "
                    f"{mem['decision']} - P&L: {mem['pnl_percent']:+.2f}%"
                )
        
        # 5. Statistiques globales
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
        except:
            pass
        
        if context_parts:
            return "\n## 🧠 MÉMOIRE - TES EXPÉRIENCES PASSÉES\n" + "\n".join(context_parts)
        
        return ""
    
    # =====================================================
    # CONTEXTE DE MARCHÉ
    # =====================================================
    
    def save_market_context(self, context_data: Dict[str, Any]) -> bool:
        """Sauvegarde un snapshot du contexte de marché."""
        if not self._initialized:
            return False
        
        try:
            supabase_client.client.table('market_context').insert(context_data).execute()
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde contexte: {e}")
            return False
    
    def get_recent_market_context(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Récupère le contexte de marché récent."""
        if not self._initialized:
            return []
        
        try:
            since = (datetime.now() - timedelta(hours=hours)).isoformat()
            response = supabase_client.client.table('market_context').select('*').gte(
                'snapshot_at', since
            ).order('snapshot_at', desc=True).execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur récupération contexte: {e}")
            return []


# Instance globale
memory_service = MemoryService()

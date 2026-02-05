"""
Agent de base pour le trading IA.
Classe abstraite définissant le comportement commun de tous les agents.

AMÉLIORATIONS V2:
- Mémoire RAG: Les IAs apprennent de leurs erreurs passées
- Données Smart Money: Dark Pool, Options Flow, Insider Trading
- Kelly Criterion: Position sizing optimal basé sur les stats

AMÉLIORATIONS V2.2:
- Indicateurs Techniques: RSI, MACD, Support/Résistance, Volume
- Calendrier Earnings: Éviter les achats avant earnings
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import json

from ..core.config import settings
from ..core.llm_client import llm_client
from ..core.alpaca_client import alpaca_client
from ..core.memory_service import memory_service
from ..core.smart_data_service import smart_data_service
from ..core.kelly_calculator import kelly_calculator
from ..core.technical_indicators import technical_indicators
from ..core.earnings_calendar import earnings_calendar

# === V2.3: IMPORT MÉMOIRE AMÉLIORÉE ===
from ..core.enhanced_memory_service import enhanced_memory_service

logger = logging.getLogger(__name__)


class Decision(Enum):
    """Types de décisions de trading."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RiskLevel(Enum):
    """Niveaux de risque."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TradeRecord:
    """Enregistrement d'un trade."""
    
    def __init__(
        self,
        decision: str,
        symbol: str,
        quantity: float,
        price: float,
        reasoning: str,
        confidence: int,
        timestamp: datetime = None,
    ):
        self.decision = decision
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.reasoning = reasoning
        self.confidence = confidence
        self.timestamp = timestamp or datetime.now()
        self.executed = False
        self.order_id: Optional[str] = None
        self.pnl: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "decision": self.decision,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "price": self.price,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "executed": self.executed,
            "order_id": self.order_id,
            "pnl": self.pnl,
        }


class BaseAgent(ABC):
    """
    Classe de base pour tous les agents de trading IA.
    Chaque agent a une personnalité et un style de trading unique.
    """
    
    def __init__(
        self,
        name: str,
        model: str,
        personality: str,
        initial_capital: float = None,
    ):
        """
        Initialise l'agent.
        
        Args:
            name: Nom de l'agent (ex: "Grok", "DeepSeek")
            model: ID du modèle LLM à utiliser
            personality: Prompt de personnalité
            initial_capital: Capital initial alloué
        """
        self.name = name
        self.model = model
        self.personality = personality
        self.initial_capital = initial_capital or settings.initial_capital_per_ai
        
        # État de l'agent
        self.current_capital = self.initial_capital
        self.history: List[TradeRecord] = []
        self.total_fees = 0.0
        self.trade_count = 0
        self.last_autocritique: Optional[str] = None
        self.autocritique_counter = 0
        
        # Métriques
        self.total_profit = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        self.positions: Dict[str, Dict] = {}  # symbol -> {qty, avg_price}
        
        logger.info(f"🤖 Agent {name} créé avec {initial_capital}$ de capital")
    
    def get_system_prompt(self) -> str:
        """
        Génère le prompt système complet pour l'agent.
        Combine personnalité + règles communes.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        base_prompt = f"""
# Tu es {self.name}, un trader IA autonome et INTELLIGENT.
# DATE ACTUELLE: {current_time}

## TA PERSONNALITÉ
{self.personality}

## TON OBJECTIF PRINCIPAL
MAXIMISER LES PROFITS sur le long terme. Chaque décision compte.

## 🧠 RÈGLES DE RÉFLEXION OBLIGATOIRES
Avant CHAQUE décision, tu DOIS te poser ces questions:
1. **POURQUOI cette action?** - Quel est le catalyst précis?
2. **POURQUOI maintenant?** - Le timing est-il optimal?
3. **Qui d'autre est impacté?** - Concurrents, fournisseurs, clients?
4. **Le marché a-t-il déjà pricé l'info?** - Suis-je en retard?
5. **Quel est mon plan de sortie?** - Target et stop-loss définis?

## 📊 RÈGLES DE DIVERSIFICATION
- Maximum 25% du capital dans un même secteur
- Maximum 5% du capital dans une seule position
- Explore DIFFÉRENTS secteurs: Tech, Santé, Finance, Énergie, Consommation, Industrie
- Si tu as 2+ positions dans un secteur, cherche AILLEURS

## 💰 GESTION DU CAPITAL
- Garde TOUJOURS 15-20% en cash pour les opportunités
- Réinvestis les profits intelligemment (pas tout d'un coup)
- Augmente les positions GAGNANTES par paliers (pyramiding)
- Coupe les PERDANTS rapidement (-5% max)
- Prends des profits PARTIELS (+5-7%), laisse courir le reste

## ⚠️ RÈGLES ABSOLUES
1. Chaque trade coûte ${settings.simulated_fee_per_trade} en frais - trade uniquement si confiant >70%
2. NE SUIS PAS LE TROUPEAU - cherche des opportunités uniques
3. VENDS quand c'est le bon moment (ne tombe pas amoureux d'une position)
4. COMPRENDS avant d'agir - pas de trade sans raison claire
5. Tu as accès à ~10,000 actions US (NYSE, NASDAQ, AMEX)

## 📈 TON CAPITAL ACTUEL
- Capital initial: ${self.initial_capital:.2f}
- Capital actuel: ${self.current_capital:.2f}
- Cash disponible: ~${self.current_capital * 0.85:.2f} (hors positions)
- Frais payés: ${self.total_fees:.2f}
- Performance: {self.get_performance():+.2f}%

## 📋 TES POSITIONS ACTUELLES
{json.dumps(self.positions, indent=2) if self.positions else "Aucune position - 100% cash disponible"}

## 📜 TON HISTORIQUE RÉCENT
{self._format_recent_history()}

## 🔄 TON AUTOCRITIQUE (apprends de tes erreurs!)
{self.last_autocritique or "Pas encore d'autocritique. Concentre-toi sur la qualité des trades."}

## 📤 FORMAT DE RÉPONSE
Tu DOIS répondre avec un JSON valide contenant ta décision et ton raisonnement DÉTAILLÉ.
"""
        return base_prompt
    
    def _format_recent_history(self, limit: int = 5) -> str:
        """Formate l'historique récent pour le prompt."""
        if not self.history:
            return "Aucun trade effectué."
        
        recent = self.history[-limit:]
        lines = []
        for trade in recent:
            lines.append(
                f"- {trade.timestamp.strftime('%Y-%m-%d %H:%M')}: "
                f"{trade.decision} {trade.quantity} {trade.symbol} @ ${trade.price:.2f} "
                f"(confiance: {trade.confidence}%)"
            )
        return "\n".join(lines)
    
    def get_performance(self) -> float:
        """Calcule la performance en pourcentage."""
        if self.initial_capital == 0:
            return 0.0
        return ((self.current_capital - self.initial_capital) / self.initial_capital) * 100
    
    async def autocritique(self) -> Optional[str]:
        """
        Effectue une autocritique tous les 5 trades.
        Retourne le monologue interne de l'agent.
        """
        self.autocritique_counter += 1
        
        # Autocritique tous les 5 trades
        if self.autocritique_counter < 5:
            return self.last_autocritique
        
        self.autocritique_counter = 0
        
        logger.info(f"🔄 {self.name} effectue une autocritique...")
        
        history_dicts = [t.to_dict() for t in self.history[-10:]]
        
        critique = await llm_client.generate_autocritique(
            model=self.model,
            agent_name=self.name,
            trade_history=history_dicts,
            total_fees=self.total_fees,
            current_performance=self.get_performance(),
        )
        
        if critique:
            self.last_autocritique = critique
            logger.info(f"💭 Autocritique {self.name}: {critique[:100]}...")
        
        return critique
    
    async def analyze_market(
        self,
        market_data: Dict[str, Any],
        news: Optional[str] = None,
        feedback: Optional[str] = None,
        smart_money_data: Optional[Dict[str, Any]] = None,
        technical_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyse le marché et prend une décision.
        
        AMÉLIORÉ V2:
        - Intègre la mémoire RAG (apprentissage des erreurs)
        - Intègre les données Smart Money (Dark Pool, Options, Insiders)
        - Intègre le Kelly Criterion pour le position sizing
        
        AMÉLIORÉ V2.2:
        - Intègre les indicateurs techniques (RSI, MACD, S/R, Volume)
        - Vérifie le calendrier earnings avant BUY
        
        Args:
            market_data: Données de marché actuelles
            news: Actualités optionnelles
            feedback: Feedback d'une tentative précédente (ex: erreur)
            smart_money_data: Données alternatives pré-récupérées
            technical_data: Données techniques pré-calculées (V2.2)
            
        Returns: Décision de trading
        """
        # Effectuer l'autocritique si nécessaire
        await self.autocritique()
        
        # Construire le contexte de base
        context = self._build_market_context(market_data, news)
        
        # === V2.3 AMÉLIORATION: MÉMOIRE RAG ENRICHIE (symbole + secteur) ===
        if hasattr(self, 'db_id') and self.db_id and enhanced_memory_service._initialized:
            # Récupérer le contexte PRÉ-DÉCISION (stats générales)
            pre_decision_context = enhanced_memory_service.get_pre_decision_context(
                agent_id=self.db_id,
                market_sentiment=market_data.get("sentiment"),
            )
            if pre_decision_context:
                context = pre_decision_context + "\n\n" + context
                logger.info(f"🧠 {self.name}: Contexte mémoire enrichi ajouté")
        elif hasattr(self, 'db_id') and self.db_id and memory_service._initialized:
            # Fallback sur l'ancienne mémoire
            memory_context = memory_service.format_memory_context_for_agent(
                agent_id=self.db_id,
                current_symbol=None,
                current_sector=None,
                current_sentiment=market_data.get("sentiment"),
            )
            if memory_context:
                context = memory_context + "\n\n" + context
                logger.info(f"🧠 {self.name}: Contexte mémoire ajouté")
        
        # === AMÉLIORATION 2: DONNÉES SMART MONEY ===
        if smart_money_data:
            smart_context = smart_data_service.format_smart_data_for_agent(smart_money_data)
            if smart_context:
                context = context + "\n\n" + smart_context
                logger.info(f"🎯 {self.name}: Données Smart Money ajoutées")
        
        # === AMÉLIORATION 3: KELLY CRITERION (position sizing) ===
        if hasattr(self, 'db_id') and self.db_id and kelly_calculator._initialized:
            kelly_context = kelly_calculator.format_kelly_for_agent(
                agent_id=self.db_id,
                capital=self.current_capital,
            )
            if kelly_context:
                context = context + "\n\n" + kelly_context
                logger.info(f"💰 {self.name}: Contexte Kelly ajouté")
        
        # === AMÉLIORATION 4 (V2.2): INDICATEURS TECHNIQUES ===
        if technical_data:
            for symbol, tech_analysis in technical_data.items():
                if tech_analysis:
                    tech_context = technical_indicators.format_for_agent(tech_analysis)
                    if tech_context:
                        context = context + "\n\n" + tech_context
            logger.info(f"📊 {self.name}: Indicateurs techniques ajoutés")
        
        if feedback:
            logger.info(f"🔄 {self.name} reçoit un feedback: {feedback}")
            context = f"⚠️ FEEDBACK / ERREUR PRÉCÉDENTE (Prends-en compte!): {feedback}\n\n" + context
        
        # Demander une décision au LLM
        history_dicts = [t.to_dict() for t in self.history[-5:]]
        
        decision = await llm_client.generate_trading_decision(
            model=self.model,
            system_prompt=self.get_system_prompt(),
            market_context=context,
            history=history_dicts,
        )
        
        if decision:
            # === POST-TRAITEMENT: Ajuster le position sizing avec Kelly ===
            if hasattr(self, 'db_id') and self.db_id and kelly_calculator._initialized:
                confidence = decision.get("confidence", 50)
                risk_level = decision.get("risk_level", "MEDIUM")
                vix = smart_money_data.get("vix", {}).get("vix", 20) if smart_money_data else 20
                smart_signal = smart_money_data.get("overall_signal", "NEUTRAL") if smart_money_data else "NEUTRAL"
                
                kelly_sizing = kelly_calculator.calculate_position_size(
                    agent_id=self.db_id,
                    capital=self.current_capital,
                    confidence=confidence,
                    risk_level=risk_level,
                    vix=vix,
                    smart_money_signal=smart_signal,
                )
                
                # Remplacer la quantité suggérée par le montant Kelly
                if decision.get("decision") in ["BUY", "SELL"]:
                    decision["kelly_amount"] = kelly_sizing.recommended_amount
                    decision["kelly_reasoning"] = kelly_sizing.reasoning
                    logger.info(f"💰 {self.name}: Kelly recommande ${kelly_sizing.recommended_amount:.2f}")
            
            logger.info(
                f"📊 {self.name} décision: {decision.get('decision')} "
                f"{decision.get('symbol')} (confiance: {decision.get('confidence')}%)"
            )
        
        return decision
    
    @abstractmethod
    def _build_market_context(
        self,
        market_data: Dict[str, Any],
        news: Optional[str] = None,
    ) -> str:
        """
        Construit le contexte de marché pour l'agent.
        À implémenter par chaque agent spécialisé.
        """
        pass
    
    async def execute_trade(self, decision: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Exécute une décision de trading.
        
        Args:
            decision: Dict avec decision, symbol, quantity, etc.
            
        Returns: (Succès, Raison/Erreur)
        """
        action = decision.get("decision", "HOLD").upper()
        symbol = decision.get("symbol", "")
        quantity = decision.get("quantity", 0)
        reasoning = decision.get("reasoning", "")
        confidence = decision.get("confidence", 0)
        
        # HOLD = ne rien faire
        if action == "HOLD" or not symbol or quantity <= 0:
            logger.info(f"⏸️ {self.name} HOLD: {reasoning[:100]}...")
            return True, "Held position or invalid quantity"
        
        # Vérifier le capital disponible pour BUY
        if action == "BUY":
            # Estimer le coût
            market_data = alpaca_client.get_market_data(symbol, "1Day", 1)
            if not market_data:
                msg = f"❌ Impossible d'obtenir le prix pour {symbol}"
                logger.warning(msg)
                return False, msg
            
            current_price = market_data[-1]["close"]
            total_cost = quantity * current_price + settings.simulated_fee_per_trade
            
            if total_cost > self.current_capital:
                msg = f"❌ {self.name} capital insuffisant: ${total_cost:.2f} > ${self.current_capital:.2f}"
                logger.warning(msg)
                return False, msg
        
        # Exécuter l'ordre via Alpaca
        side = "buy" if action == "BUY" else "sell"
        order = alpaca_client.submit_order(
            symbol=symbol,
            qty=quantity,
            side=side,
        )
        
        if not order:
            msg = f"❌ {self.name} échec ordre {action} {quantity} {symbol}"
            logger.error(msg)
            return False, msg
        
        # Enregistrer le trade
        price = order.get("filled_avg_price", 0) or 0
        
        trade = TradeRecord(
            decision=action,
            symbol=symbol,
            quantity=quantity,
            price=price,
            reasoning=reasoning,
            confidence=confidence,
        )
        trade.executed = True
        trade.order_id = order.get("id")
        
        self.history.append(trade)
        self.trade_count += 1
        
        # Mettre à jour les frais
        self.total_fees += settings.simulated_fee_per_trade
        
        # Mettre à jour les positions
        self._update_positions(action, symbol, quantity, price)
        
        # === V2.3 MÉMOIRE RAG ENRICHIE: Créer un souvenir avec symbole + secteur ===
        if hasattr(self, 'db_id') and self.db_id and enhanced_memory_service._initialized:
            try:
                # Récupérer les données techniques si disponibles
                technical_data = decision.get("technical_data", {})
                smart_money_data = decision.get("smart_money_data", {})
                
                enhanced_memory_service.create_enriched_trade_memory(
                    agent_id=self.db_id,
                    trade_id=trade.order_id,
                    symbol=symbol,
                    decision=action,
                    entry_price=price,
                    quantity=quantity,
                    reasoning=reasoning,
                    confidence=confidence,
                    technical_data=technical_data,
                    smart_money_data=smart_money_data,
                )
                sector = enhanced_memory_service.get_sector_for_symbol(symbol)
                logger.info(f"🧠 {self.name}: Mémoire enrichie créée pour {action} {symbol} ({sector})")
            except Exception as e:
                logger.warning(f"Erreur création mémoire enrichie: {e}")
        elif hasattr(self, 'db_id') and self.db_id and memory_service._initialized:
            # Fallback sur l'ancienne méthode
            try:
                market_context = {
                    "sentiment": decision.get("market_sentiment"),
                    "sector": decision.get("sector"),
                }
                smart_data = {
                    "dark_pool_ratio": decision.get("dark_pool_ratio"),
                    "options_sentiment": decision.get("options_sentiment"),
                    "insider_activity": decision.get("insider_activity"),
                }
                memory_service.create_trade_memory(
                    agent_id=self.db_id,
                    trade_id=trade.order_id,
                    symbol=symbol,
                    decision=action,
                    entry_price=price,
                    quantity=quantity,
                    reasoning=reasoning,
                    confidence=confidence,
                    market_context=market_context,
                    smart_money_data=smart_data,
                )
                logger.info(f"🧠 {self.name}: Mémoire créée pour {action} {symbol}")
            except Exception as e:
                logger.warning(f"Erreur création mémoire: {e}")
        
        logger.info(
            f"✅ {self.name} exécuté: {action} {quantity} {symbol} @ ${price:.2f} "
            f"(frais totaux: ${self.total_fees:.2f})"
        )
        
        return True, "Executed successfully"
    
    def _update_positions(
        self,
        action: str,
        symbol: str,
        quantity: float,
        price: float,
    ):
        """Met à jour les positions et le capital."""
        if action == "BUY":
            cost = quantity * price + settings.simulated_fee_per_trade
            self.current_capital -= cost
            
            if symbol in self.positions:
                # Moyenne le prix d'entrée
                pos = self.positions[symbol]
                total_qty = pos["qty"] + quantity
                pos["avg_price"] = (
                    (pos["qty"] * pos["avg_price"] + quantity * price) / total_qty
                )
                pos["qty"] = total_qty
            else:
                self.positions[symbol] = {"qty": quantity, "avg_price": price}
                
        elif action == "SELL":
            revenue = quantity * price - settings.simulated_fee_per_trade
            self.current_capital += revenue
            
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos["qty"] -= quantity
                
                # Calculer le PnL
                pnl = (price - pos["avg_price"]) * quantity
                self.total_profit += pnl
                
                if pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                # === MÉMOIRE RAG: Fermer le souvenir avec le résultat ===
                if hasattr(self, 'db_id') and self.db_id and memory_service._initialized:
                    try:
                        # Chercher la mémoire d'achat correspondante pour ce symbole
                        memories = memory_service.get_similar_trades(
                            agent_id=self.db_id,
                            symbol=symbol,
                            limit=1
                        )
                        # Si on trouve une mémoire ouverte, on la ferme
                        open_memories = [m for m in memories if m.get('success') is None]
                        for mem in open_memories:
                            lesson = f"Vendu après {'GAIN' if pnl > 0 else 'PERTE'} de ${abs(pnl):.2f}"
                            memory_service.close_trade_memory(
                                memory_id=mem['id'],
                                exit_price=price,
                                pnl=pnl,
                                lesson_learned=lesson,
                            )
                            logger.info(f"🧠 {self.name}: Mémoire fermée pour {symbol} - P&L: ${pnl:.2f}")
                    except Exception as e:
                        logger.warning(f"Erreur fermeture mémoire: {e}")
                
                if pos["qty"] <= 0:
                    del self.positions[symbol]
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de l'agent."""
        win_rate = 0.0
        total_trades = self.winning_trades + self.losing_trades
        if total_trades > 0:
            win_rate = (self.winning_trades / total_trades) * 100
        
        return {
            "name": self.name,
            "model": self.model,
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "performance_pct": self.get_performance(),
            "total_profit": self.total_profit,
            "total_fees": self.total_fees,
            "trade_count": self.trade_count,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "positions": self.positions,
            "last_autocritique": self.last_autocritique,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'agent en dictionnaire."""
        return {
            **self.get_stats(),
            "history": [t.to_dict() for t in self.history],
        }

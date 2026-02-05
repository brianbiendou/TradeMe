"""
Agent Manager - Orchestrateur et Agent Collaboratif.
Gère le mode collaboratif avec vote/pondération entre les agents.

V2.2: Ajout indicateurs techniques et calendrier earnings.
"""
import logging
from typing import Optional, Dict, Any, List
from collections import Counter
import json

from .base_agent import BaseAgent, TradeRecord
from .grok_agent import GrokAgent
from .deepseek_agent import DeepSeekAgent
from .openai_agent import OpenAIAgent
from ..core.config import settings
from ..core.llm_client import llm_client
from ..core.alpaca_client import alpaca_client
from ..core.smart_data_service import smart_data_service
from ..core.signal_combiner import signal_combiner
from ..core.circuit_breaker import circuit_breaker
from ..core.exit_strategy_manager import exit_strategy_manager
from ..core.technical_indicators import technical_indicators
from ..core.earnings_calendar import earnings_calendar

# === V2.3: NOUVEAUX IMPORTS ===
from ..core.technical_gates_service import technical_gates_service
from ..core.enhanced_memory_service import enhanced_memory_service

# === V2.5: WHITELIST SYMBOLES ===
from ..core.symbol_whitelist import is_symbol_allowed, filter_symbols

logger = logging.getLogger(__name__)


class CollaborativeAgent(BaseAgent):
    """
    Agent collaboratif qui combine les décisions de plusieurs agents.
    Utilise le vote majoritaire ou la pondération par performance.
    """
    
    def __init__(
        self,
        agents: List[BaseAgent],
        mode: str = "weighted",  # "vote" ou "weighted"
        initial_capital: float = None,
    ):
        """
        Initialise l'agent collaboratif.
        
        Args:
            agents: Liste des agents à consulter
            mode: "vote" (majoritaire) ou "weighted" (pondéré par perf)
            initial_capital: Capital alloué
        """
        super().__init__(
            name="Consortium",
            model="collaborative",
            personality="Agent collaboratif combinant les forces de Grok, DeepSeek et GPT.",
            initial_capital=initial_capital,
        )
        
        self.agents = agents
        self.mode = mode
        self.agent_decisions: Dict[str, Dict] = {}
    
    def _build_market_context(
        self,
        market_data: Dict[str, Any],
        news: Optional[str] = None,
    ) -> str:
        """Pas utilisé directement pour l'agent collaboratif."""
        return ""
    
    async def analyze_market(
        self,
        market_data: Dict[str, Any],
        news: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Collecte les décisions de tous les agents et combine.
        """
        logger.info("🤝 Consortium: Consultation des agents...")
        
        # Collecter les décisions de chaque agent
        decisions = []
        self.agent_decisions = {}
        
        for agent in self.agents:
            try:
                decision = await agent.analyze_market(market_data, news)
                if decision:
                    decision["agent_name"] = agent.name
                    decision["agent_performance"] = agent.get_performance()
                    decisions.append(decision)
                    self.agent_decisions[agent.name] = decision
                    logger.info(
                        f"  📊 {agent.name}: {decision.get('decision')} "
                        f"{decision.get('symbol')} (confiance: {decision.get('confidence')}%)"
                    )
            except Exception as e:
                logger.error(f"Erreur agent {agent.name}: {e}")
        
        if not decisions:
            return {"decision": "HOLD", "reasoning": "Aucun agent n'a pu décider."}
        
        # Combiner les décisions
        if self.mode == "vote":
            final_decision = self._vote_majority(decisions)
        else:
            final_decision = self._weighted_decision(decisions)
        
        logger.info(
            f"🎯 Consortium décision finale: {final_decision.get('decision')} "
            f"{final_decision.get('symbol')}"
        )
        
        return final_decision
    
    def _vote_majority(self, decisions: List[Dict]) -> Dict[str, Any]:
        """
        Vote majoritaire simple.
        Chaque agent = 1 vote.
        """
        # Compter les votes par décision
        vote_counts = Counter()
        votes_by_action = {"BUY": [], "SELL": [], "HOLD": []}
        
        for d in decisions:
            action = d.get("decision", "HOLD").upper()
            vote_counts[action] += 1
            votes_by_action[action].append(d)
        
        # Déterminer l'action gagnante
        if not vote_counts:
            return {"decision": "HOLD", "reasoning": "Aucun vote valide."}
        
        winning_action = vote_counts.most_common(1)[0][0]
        winning_votes = votes_by_action[winning_action]
        
        # Si plusieurs votes pour la même action, prendre le plus confiant
        if winning_action in ["BUY", "SELL"] and winning_votes:
            best_vote = max(winning_votes, key=lambda x: x.get("confidence", 0))
            
            return {
                "decision": winning_action,
                "symbol": best_vote.get("symbol"),
                "quantity": best_vote.get("quantity"),
                "confidence": sum(v.get("confidence", 0) for v in winning_votes) // len(winning_votes),
                "reasoning": f"Vote majoritaire ({vote_counts[winning_action]}/{len(decisions)}). "
                            f"Agents: {', '.join(v.get('agent_name', '?') for v in winning_votes)}. "
                            f"Raisonnement principal: {best_vote.get('reasoning', '')}",
                "risk_level": best_vote.get("risk_level", "MEDIUM"),
                "votes": dict(vote_counts),
            }
        
        return {
            "decision": "HOLD",
            "reasoning": f"Pas de consensus. Votes: {dict(vote_counts)}",
            "votes": dict(vote_counts),
        }
    
    def _weighted_decision(self, decisions: List[Dict]) -> Dict[str, Any]:
        """
        Décision pondérée par la performance des agents.
        Les agents avec meilleure performance ont plus de poids.
        
        V2.1: Intègre le seuil de confiance collective.
        """
        # Calculer les poids basés sur la performance
        total_positive_perf = sum(
            max(0, d.get("agent_performance", 0)) + 1  # +1 pour éviter 0
            for d in decisions
        )
        
        if total_positive_perf == 0:
            total_positive_perf = len(decisions)  # Poids égaux si tous négatifs
        
        weighted_scores = {"BUY": 0, "SELL": 0, "HOLD": 0}
        action_details = {"BUY": [], "SELL": [], "HOLD": []}
        total_confidence = 0
        
        for d in decisions:
            action = d.get("decision", "HOLD").upper()
            perf = max(0, d.get("agent_performance", 0)) + 1
            weight = perf / total_positive_perf
            confidence = d.get("confidence", 50) / 100
            total_confidence += d.get("confidence", 50)
            
            score = weight * confidence
            weighted_scores[action] += score
            action_details[action].append({
                **d,
                "weight": weight,
                "score": score,
            })
        
        # === V2.1: CHECK CONFIANCE COLLECTIVE ===
        avg_confidence = total_confidence / len(decisions) if decisions else 0
        min_collective_confidence = 55  # Seuil minimum de confiance collective
        
        if avg_confidence < min_collective_confidence:
            logger.warning(f"⚠️ Confiance collective faible: {avg_confidence:.1f}% < {min_collective_confidence}%")
            return {
                "decision": "HOLD",
                "reasoning": f"Confiance collective insuffisante ({avg_confidence:.1f}% < {min_collective_confidence}%). Agents pas assez confiants.",
                "weighted_scores": {k: round(v, 3) for k, v in weighted_scores.items()},
                "avg_confidence": avg_confidence,
            }
        
        # Trouver l'action avec le meilleur score pondéré
        best_action = max(weighted_scores, key=weighted_scores.get)
        best_score = weighted_scores[best_action]
        
        if best_action in ["BUY", "SELL"] and action_details[best_action]:
            # Prendre le meilleur vote pour les détails
            best_vote = max(action_details[best_action], key=lambda x: x["score"])
            
            return {
                "decision": best_action,
                "symbol": best_vote.get("symbol"),
                "quantity": best_vote.get("quantity"),
                "confidence": int(best_score * 100),
                "reasoning": f"Décision pondérée (score: {best_score:.2f}, confiance collective: {avg_confidence:.1f}%). "
                            f"Agents: {', '.join(v.get('agent_name', '?') for v in action_details[best_action])}. "
                            f"Basé sur: {best_vote.get('reasoning', '')}",
                "risk_level": best_vote.get("risk_level", "MEDIUM"),
                "weighted_scores": {k: round(v, 3) for k, v in weighted_scores.items()},
                "avg_confidence": avg_confidence,
            }
        
        return {
            "decision": "HOLD",
            "reasoning": f"Score pondéré insuffisant. Scores: {weighted_scores}",
            "weighted_scores": {k: round(v, 3) for k, v in weighted_scores.items()},
        }
    
    def get_all_decisions(self) -> Dict[str, Dict]:
        """Retourne les dernières décisions de chaque agent."""
        return self.agent_decisions


class AgentManager:
    """
    Gestionnaire principal de tous les agents de trading.
    Orchestre les cycles de trading.
    """
    
    def __init__(self):
        """Initialise le manager avec les agents."""
        self.agents: Dict[str, BaseAgent] = {}
        self.collaborative_agent: Optional[CollaborativeAgent] = None
        self._initialized = False
    
    def initialize(self, capital_per_agent: float = None) -> bool:
        """
        Initialise tous les agents.
        
        Args:
            capital_per_agent: Capital alloué à chaque agent
            
        Returns: True si succès
        """
        capital = capital_per_agent or settings.initial_capital_per_ai
        
        try:
            # Créer les agents solo
            self.agents["grok"] = GrokAgent(initial_capital=capital)
            self.agents["deepseek"] = DeepSeekAgent(initial_capital=capital)
            self.agents["gpt"] = OpenAIAgent(initial_capital=capital)
            
            # Créer l'agent collaboratif
            self.collaborative_agent = CollaborativeAgent(
                agents=list(self.agents.values()),
                mode="weighted",
                initial_capital=capital,
            )
            self.agents["consortium"] = self.collaborative_agent
            
            self._initialized = True
            logger.info(f"✅ {len(self.agents)} agents initialisés avec ${capital} chacun")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur initialisation agents: {e}")
            return False
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Récupère un agent par son nom."""
        return self.agents.get(name.lower())
    
    def get_all_agents(self) -> Dict[str, BaseAgent]:
        """Retourne tous les agents."""
        return self.agents
    
    async def run_trading_cycle(
        self,
        market_data: Dict[str, Any],
        news: Optional[str] = None,
        execute_trades: bool = True,
        agents_allowed: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Exécute un cycle de trading pour tous les agents.
        
        V2.1 AMÉLIORÉ:
        - Récupère les données Smart Money (Dark Pool, Options, Insiders)
        - Utilise le Circuit Breaker pour vérifier si l'agent peut trader
        - Utilise le Signal Combiner pour valider les décisions
        - Crée les Exit Levels (Stop-Loss/Take-Profit) pour les nouvelles positions
        
        Args:
            market_data: Données de marché
            news: Actualités optionnelles
            execute_trades: Si True, exécute les trades
            agents_allowed: Dict des agents autorisés par le Circuit Breaker
            
        Returns: Résumé du cycle
        """
        if not self._initialized:
            return {"error": "Manager non initialisé"}
        
        results = {}
        agents_allowed = agents_allowed or {}
        
        # === AMÉLIORATION: Récupérer les données Smart Money globales ===
        smart_money_global = None
        try:
            if smart_data_service._initialized:
                # Récupérer VIX et Fear/Greed pour tout le marché
                vix_data = await smart_data_service.get_vix_data()
                fng_data = await smart_data_service.get_fear_greed_index()
                
                smart_money_global = {
                    "vix": vix_data,
                    "fear_greed": fng_data,
                    "overall_signal": "NEUTRAL",
                }
                
                # Déterminer le signal global
                vix = vix_data.get("vix", 20)
                fng = fng_data.get("fear_greed_index", 50)
                
                if vix < 18 and fng > 55:
                    smart_money_global["overall_signal"] = "BULLISH"
                elif vix > 25 or fng < 40:
                    smart_money_global["overall_signal"] = "BEARISH"
                
                logger.info(f"📊 Smart Money Global: VIX={vix}, Fear/Greed={fng}, Signal={smart_money_global['overall_signal']}")
        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération Smart Money global: {e}")
        
        # === V2.2: PRÉ-CALCULER LES INDICATEURS TECHNIQUES POUR LES TOP MOVERS ===
        technical_data = {}
        try:
            if technical_indicators._initialized:
                movers = market_data.get("movers", {})
                top_symbols = []
                
                # Collecter les symboles des top movers
                for category in ["gainers", "losers", "most_active"]:
                    for mover in movers.get(category, [])[:5]:
                        symbol = mover.get("symbol")
                        if symbol and symbol not in top_symbols:
                            top_symbols.append(symbol)
                
                # === V2.5: FILTRER LES SYMBOLES (S&P500/Nasdaq100 uniquement) ===
                top_symbols = filter_symbols(top_symbols)
                
                # Calculer les indicateurs pour chaque symbole
                for symbol in top_symbols[:10]:  # Limiter à 10 pour la performance
                    ohlcv = alpaca_client.get_market_data(symbol, "1Day", 50)
                    if ohlcv and len(ohlcv) >= 30:
                        analysis = technical_indicators.analyze(symbol, ohlcv)
                        if analysis:
                            technical_data[symbol] = analysis
                
                if technical_data:
                    logger.info(f"📊 Indicateurs techniques calculés pour {len(technical_data)} symboles")
        except Exception as e:
            logger.warning(f"⚠️ Erreur calcul indicateurs techniques: {e}")
        
        for name, agent in self.agents.items():
            if name == "consortium":
                continue  # Le traiter à part
            
            # === V2.1: CHECK CIRCUIT BREAKER ===
            if name in agents_allowed and not agents_allowed[name].get("can_trade", True):
                logger.warning(f"🚫 {name}: Bloqué par Circuit Breaker - {agents_allowed[name].get('reason')}")
                results[name] = {
                    "decision": {"decision": "HOLD", "reasoning": agents_allowed[name].get("reason")},
                    "blocked_by_circuit_breaker": True,
                    "stats": agent.get_stats(),
                }
                continue
            
            try:
                # Analyser et décider (avec données Smart Money ET Techniques V2.2)
                decision = await agent.analyze_market(
                    market_data, 
                    news,
                    smart_money_data=smart_money_global,
                    technical_data=technical_data,  # V2.2: Ajouter les indicateurs techniques
                )
                
                executed = False
                fail_reason = None
                
                if decision and execute_trades and decision.get("decision") in ["BUY", "SELL"]:
                    symbol = decision.get("symbol", "")
                    trade_action = decision.get("decision")
                    
                    # === V2.3: VÉRIFIER LES TECHNICAL GATES (RÈGLES DURES) ===
                    if technical_gates_service._initialized and symbol in technical_data:
                        tech_analysis = technical_data[symbol]
                        if tech_analysis:
                            gate_result = technical_gates_service.evaluate_trade(
                                trade_decision=trade_action,
                                technical_analysis=tech_analysis.to_dict() if hasattr(tech_analysis, 'to_dict') else tech_analysis,
                            )
                            
                            if not gate_result.can_proceed:
                                logger.warning(f"🚧 {name}: Trade {trade_action} BLOQUÉ par Technical Gates")
                                for msg in gate_result.messages:
                                    logger.warning(f"   {msg}")
                                decision["technical_gates_blocked"] = True
                                decision["technical_gates_reason"] = gate_result.messages
                                decision["technical_gates_risk_score"] = gate_result.risk_score
                                results[name] = {
                                    "decision": decision,
                                    "blocked_by_technical_gates": True,
                                    "gate_result": gate_result.to_dict(),
                                    "stats": agent.get_stats(),
                                }
                                continue
                            elif gate_result.risk_score > 30:
                                logger.warning(f"⚠️ {name}: Technical Gates WARNING (risk={gate_result.risk_score})")
                                decision["technical_gates_warning"] = True
                                decision["technical_gates_risk_score"] = gate_result.risk_score
                    
                    # === V2.2: VÉRIFIER LE CALENDRIER EARNINGS AVANT BUY ===
                    if decision.get("decision") == "BUY" and earnings_calendar._initialized:
                        try:
                            earnings_info = await earnings_calendar.check_earnings(symbol)
                            if earnings_info.should_avoid_buy:
                                logger.warning(f"🚨 {name}: Trade BUY bloqué - {earnings_info.message}")
                                decision["earnings_blocked"] = True
                                decision["earnings_reason"] = earnings_info.message
                                results[name] = {
                                    "decision": decision,
                                    "blocked_by_earnings": True,
                                    "stats": agent.get_stats(),
                                }
                                continue
                            elif earnings_info.position_size_multiplier < 1.0:
                                logger.info(f"📅 {name}: Earnings proche - Sizing réduit à {int(earnings_info.position_size_multiplier*100)}%")
                                decision["earnings_size_adjustment"] = earnings_info.position_size_multiplier
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur vérification earnings pour {symbol}: {e}")
                    
                    # === V2.1: VALIDER AVEC SIGNAL COMBINER ===
                    combined = signal_combiner.combine_signals(
                        decision=decision.get("decision"),
                        confidence=decision.get("confidence", 50),
                        symbol=symbol,
                        smart_money_data=smart_money_global,
                    )
                    
                    if not combined.should_proceed:
                        logger.warning(f"⚠️ {name}: Trade rejeté par Signal Combiner - {combined.reasoning[:100]}")
                        decision["signal_combiner_rejected"] = True
                        decision["combined_signal"] = combined.signal_strength.value
                    else:
                        # Ajuster la confiance et le sizing
                        decision["original_confidence"] = decision.get("confidence")
                        decision["confidence"] = combined.final_confidence
                        decision["sizing_multiplier"] = combined.sizing_multiplier
                        decision["combined_signal"] = combined.signal_strength.value
                        
                        # === V2.2: Appliquer le multiplicateur earnings si présent ===
                        if decision.get("earnings_size_adjustment"):
                            decision["sizing_multiplier"] *= decision["earnings_size_adjustment"]
                            logger.info(f"📅 {name}: Sizing final après earnings: {decision['sizing_multiplier']:.2f}")
                        
                        # Première tentative
                        executed, fail_reason = await agent.execute_trade(decision)
                        
                        # === V2.1: Créer les Exit Levels pour la nouvelle position ===
                        if executed and decision.get("decision") == "BUY" and hasattr(agent, 'db_id'):
                            vix = smart_money_global.get("vix", {}).get("vix", 20) if smart_money_global else 20
                            exit_strategy_manager.create_exit_levels(
                                agent_id=agent.db_id,
                                symbol=symbol,
                                entry_price=decision.get("price", 0),
                                confidence=decision.get("confidence", 50),
                                risk_level=decision.get("risk_level", "MEDIUM"),
                                vix=vix,
                                smart_money_signal=smart_money_global.get("overall_signal", "NEUTRAL") if smart_money_global else "NEUTRAL",
                            )
                        
                        # Retry si échec
                        if not executed and fail_reason:
                            logger.warning(f"⚠️ {name} échec trade: {fail_reason}. Tentative de correction...")
                            
                            # Nouvelle analyse avec feedback
                            new_decision = await agent.analyze_market(
                                market_data, 
                                news, 
                                feedback=f"Ta dernière décision a échoué car: {fail_reason}. Propose une autre action (ou HOLD)."
                            )
                            
                            if new_decision:
                                logger.info(f"🔄 {name} nouvelle décision: {new_decision.get('decision')} {new_decision.get('symbol')}")
                                # Seconde tentative
                                executed, fail_reason = await agent.execute_trade(new_decision)
                                decision = new_decision # Mettre à jour la décision pour le rapport
                
                if decision:
                    decision["executed"] = executed
                    if not executed and fail_reason:
                        decision["fail_reason"] = fail_reason
                
                results[name] = {
                    "decision": decision,
                    "stats": agent.get_stats(),
                }
                
            except Exception as e:
                logger.error(f"Erreur cycle {name}: {e}")
                results[name] = {"error": str(e)}
        
        # Cycle collaboratif
        if self.collaborative_agent:
            # Check circuit breaker pour consortium aussi
            consortium_name = "consortium"
            if consortium_name in agents_allowed and not agents_allowed[consortium_name].get("can_trade", True):
                results["consortium"] = {
                    "decision": {"decision": "HOLD", "reasoning": agents_allowed[consortium_name].get("reason")},
                    "blocked_by_circuit_breaker": True,
                    "stats": self.collaborative_agent.get_stats(),
                }
            else:
                try:
                    decision = await self.collaborative_agent.analyze_market(market_data, news)
                    
                    if decision and execute_trades and decision.get("decision") in ["BUY", "SELL"]:
                        # Valider avec Signal Combiner
                        combined = signal_combiner.combine_signals(
                            decision=decision.get("decision"),
                            confidence=decision.get("confidence", 50),
                            symbol=decision.get("symbol", ""),
                            smart_money_data=smart_money_global,
                        )
                        
                        if combined.should_proceed:
                            decision["confidence"] = combined.final_confidence
                            decision["sizing_multiplier"] = combined.sizing_multiplier
                            executed, _ = await self.collaborative_agent.execute_trade(decision)
                            decision["executed"] = executed
                            
                            # Créer Exit Levels si trade exécuté
                            if executed and decision.get("decision") == "BUY" and hasattr(self.collaborative_agent, 'db_id'):
                                vix = smart_money_global.get("vix", {}).get("vix", 20) if smart_money_global else 20
                                exit_strategy_manager.create_exit_levels(
                                    agent_id=self.collaborative_agent.db_id,
                                    symbol=decision.get("symbol"),
                                    entry_price=decision.get("price", 0),
                                    confidence=decision.get("confidence", 50),
                                    risk_level=decision.get("risk_level", "MEDIUM"),
                                    vix=vix,
                                    smart_money_signal=smart_money_global.get("overall_signal", "NEUTRAL") if smart_money_global else "NEUTRAL",
                                )
                    
                    results["consortium"] = {
                        "decision": decision,
                        "agent_decisions": self.collaborative_agent.get_all_decisions(),
                        "stats": self.collaborative_agent.get_stats(),
                    }
                    
                except Exception as e:
                    logger.error(f"Erreur cycle consortium: {e}")
                    results["consortium"] = {"error": str(e)}
        
        return results
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Retourne les stats de tous les agents."""
        return {
            name: agent.get_stats()
            for name, agent in self.agents.items()
        }
    
    def get_leaderboard(self) -> List[Dict]:
        """Retourne le classement des agents par performance."""
        stats = self.get_all_stats()
        
        leaderboard = [
            {
                "rank": 0,
                "name": name,
                **data,
            }
            for name, data in stats.items()
        ]
        
        # Trier par performance
        leaderboard.sort(key=lambda x: x.get("performance_pct", 0), reverse=True)
        
        # Ajouter les rangs
        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1
        
        return leaderboard


# Instance globale
agent_manager = AgentManager()

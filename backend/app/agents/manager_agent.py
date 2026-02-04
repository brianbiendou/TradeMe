"""
Agent Manager - Orchestrateur et Agent Collaboratif.
Gère le mode collaboratif avec vote/pondération entre les agents.
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
        
        for d in decisions:
            action = d.get("decision", "HOLD").upper()
            perf = max(0, d.get("agent_performance", 0)) + 1
            weight = perf / total_positive_perf
            confidence = d.get("confidence", 50) / 100
            
            score = weight * confidence
            weighted_scores[action] += score
            action_details[action].append({
                **d,
                "weight": weight,
                "score": score,
            })
        
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
                "reasoning": f"Décision pondérée (score: {best_score:.2f}). "
                            f"Agents: {', '.join(v.get('agent_name', '?') for v in action_details[best_action])}. "
                            f"Basé sur: {best_vote.get('reasoning', '')}",
                "risk_level": best_vote.get("risk_level", "MEDIUM"),
                "weighted_scores": {k: round(v, 3) for k, v in weighted_scores.items()},
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
    ) -> Dict[str, Any]:
        """
        Exécute un cycle de trading pour tous les agents.
        
        Args:
            market_data: Données de marché
            news: Actualités optionnelles
            execute_trades: Si True, exécute les trades
            
        Returns: Résumé du cycle
        """
        if not self._initialized:
            return {"error": "Manager non initialisé"}
        
        results = {}
        
        for name, agent in self.agents.items():
            if name == "consortium":
                continue  # Le traiter à part
            
            try:
                # Analyser et décider
                decision = await agent.analyze_market(market_data, news)
                
                if decision and execute_trades:
                    executed = await agent.execute_trade(decision)
                    decision["executed"] = executed
                
                results[name] = {
                    "decision": decision,
                    "stats": agent.get_stats(),
                }
                
            except Exception as e:
                logger.error(f"Erreur cycle {name}: {e}")
                results[name] = {"error": str(e)}
        
        # Cycle collaboratif
        if self.collaborative_agent:
            try:
                decision = await self.collaborative_agent.analyze_market(market_data, news)
                
                if decision and execute_trades:
                    executed = await self.collaborative_agent.execute_trade(decision)
                    decision["executed"] = executed
                
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

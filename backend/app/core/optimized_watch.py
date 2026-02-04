"""
Optimized Watch Service - Version économique en tokens.
Fait le maximum de calculs SANS LLM, puis pose des questions COURTES.
"""
import logging
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

from .config import settings
from .llm_client import llm_client
from .data_aggregator import data_aggregator
from .alpaca_client import alpaca_client
from .supabase_client import supabase_client

logger = logging.getLogger(__name__)


@dataclass
class TokenEstimate:
    """Estimation des tokens utilisés."""
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    model: str


# Prix par 1M tokens (approximatif)
TOKEN_COSTS = {
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "x-ai/grok-3-mini": {"input": 0.30, "output": 0.50},  # Estimé
}


class OptimizedWatchService:
    """
    Service de veille OPTIMISÉ pour minimiser les coûts.
    
    Stratégies:
    1. Pré-calculer tout ce qui peut l'être SANS LLM
    2. Utiliser des prompts COURTS et CONCIS
    3. Limiter les tokens de réponse
    4. Utiliser des modèles moins chers quand possible
    5. Cache agressif
    
    Scheduling (marché fermé 22h-15h30, ~17h):
    - 3 veilles pendant la fermeture (toutes les ~5h)
    - Heures suggérées: 23h, 04h, 09h
    """
    
    def __init__(self):
        self._initialized = False
        self._daily_token_usage = {
            "prompt": 0,
            "completion": 0,
            "cost_usd": 0.0,
        }
        self._daily_budget_usd = 0.80  # Budget max par jour (80 centimes)
        self._last_reset = datetime.now().date()
    
    def initialize(self) -> bool:
        """Initialise le service."""
        self._initialized = True
        data_aggregator.initialize()
        logger.info("✅ OptimizedWatchService initialisé")
        return True
    
    def _reset_daily_if_needed(self):
        """Reset le compteur quotidien si nouveau jour."""
        today = datetime.now().date()
        if today != self._last_reset:
            self._daily_token_usage = {"prompt": 0, "completion": 0, "cost_usd": 0.0}
            self._last_reset = today
    
    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Estime le coût en USD."""
        costs = TOKEN_COSTS.get(model, {"input": 1.0, "output": 2.0})
        input_cost = (prompt_tokens / 1_000_000) * costs["input"]
        output_cost = (completion_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost
    
    def _can_afford_call(self, estimated_tokens: int, model: str) -> bool:
        """Vérifie si on peut se permettre cet appel."""
        self._reset_daily_if_needed()
        estimated_cost = self._estimate_cost(estimated_tokens, estimated_tokens // 2, model)
        return (self._daily_token_usage["cost_usd"] + estimated_cost) < self._daily_budget_usd
    
    async def run_quick_analysis(self, agent_name: str) -> Dict[str, Any]:
        """
        Analyse RAPIDE avec minimum de tokens.
        
        Process:
        1. Collecter données (GRATUIT)
        2. Pré-analyser localement (GRATUIT)
        3. Poser UNE question courte à l'IA (~500 tokens)
        """
        start_time = time.time()
        
        # === PHASE 1: Collecte gratuite ===
        context = await data_aggregator.get_full_market_context()
        
        # === PHASE 2: Pré-analyse locale (GRATUIT) ===
        pre_analysis = self._pre_analyze_locally(context)
        
        # === PHASE 3: Question courte à l'IA ===
        # Vérifier le budget
        model = self._get_cheap_model(agent_name)
        
        if not self._can_afford_call(800, model):
            logger.warning(f"⚠️ Budget LLM atteint, skip analyse {agent_name}")
            return {
                "agent_name": agent_name,
                "analysis": pre_analysis,
                "llm_skipped": True,
                "reason": "Budget quotidien atteint",
            }
        
        # Prompt ultra-court
        prompt = self._build_short_prompt(agent_name, pre_analysis, context)
        
        try:
            # Utiliser generate_response avec la bonne signature
            result = await llm_client.generate_response(
                model=model,
                system_prompt=f"Tu es {agent_name}, un analyste trading expert. Réponds UNIQUEMENT en JSON valide.",
                user_content=prompt,
                max_tokens=400,  # Limité!
                temperature=0.5,
            )
            
            # Extraire le texte de la réponse (format: {"content": "...", ...})
            response = ""
            if result and result.get("content"):
                response = result["content"]
                logger.info(f"📝 {agent_name}: Réponse LLM reçue ({len(response)} chars)")
            
            # Estimer et tracker les tokens
            usage = result.get("usage", {}) if result else {}
            prompt_tokens = usage.get("prompt_tokens", len(prompt) // 4)
            completion_tokens = usage.get("completion_tokens", len(response) // 4)
            cost = self._estimate_cost(prompt_tokens, completion_tokens, model)
            
            self._daily_token_usage["prompt"] += prompt_tokens
            self._daily_token_usage["completion"] += completion_tokens
            self._daily_token_usage["cost_usd"] += cost
            
            # Parser la réponse
            ai_insights = self._parse_short_response(response)
            
        except Exception as e:
            logger.error(f"Erreur LLM {agent_name}: {e}")
            ai_insights = {"error": str(e)}
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return {
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat(),
            "pre_analysis": pre_analysis,
            "ai_insights": ai_insights,
            "model_used": model,
            "processing_time_ms": processing_time,
            "tokens_used": self._daily_token_usage.copy(),
        }
    
    def _pre_analyze_locally(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pré-analyse SANS LLM - Calculs locaux gratuits.
        """
        analysis = {
            "market_condition": "NEUTRAL",
            "signals": [],
            "opportunities": [],
            "risks": [],
        }
        
        # Analyser Fear & Greed
        fg = context.get("market_sentiment", {}).get("fear_greed", {})
        fg_score = fg.get("score", 50)
        
        if fg_score < 25:
            analysis["market_condition"] = "EXTREME_FEAR"
            analysis["signals"].append("🔴 Fear extrême - Opportunité d'achat potentielle")
        elif fg_score < 40:
            analysis["market_condition"] = "FEAR"
            analysis["signals"].append("🟠 Marché craintif")
        elif fg_score > 75:
            analysis["market_condition"] = "EXTREME_GREED"
            analysis["signals"].append("🔴 Greed extrême - Attention aux corrections")
        elif fg_score > 60:
            analysis["market_condition"] = "GREED"
            analysis["signals"].append("🟢 Marché optimiste")
        
        # Analyser les movers
        gainers = context.get("movers", {}).get("top_gainers", [])
        losers = context.get("movers", {}).get("top_losers", [])
        
        for g in gainers[:3]:
            if g.get("change_pct", 0) > 5:
                analysis["opportunities"].append({
                    "symbol": g["symbol"],
                    "signal": "MOMENTUM_UP",
                    "change": g.get("change_pct", 0),
                })
        
        for l in losers[:3]:
            if l.get("change_pct", 0) < -5:
                analysis["opportunities"].append({
                    "symbol": l["symbol"],
                    "signal": "OVERSOLD_BOUNCE",
                    "change": l.get("change_pct", 0),
                })
        
        # Reddit trending
        trending = context.get("market_sentiment", {}).get("reddit_trending", [])
        if trending:
            analysis["signals"].append(f"🔥 Reddit trending: {', '.join(trending[:3])}")
        
        # Earnings à surveiller
        earnings = context.get("upcoming_earnings", [])
        if earnings:
            symbols = [e.get("symbol", "") for e in earnings[:5] if e.get("symbol")]
            if symbols:
                analysis["signals"].append(f"📅 Earnings cette semaine: {', '.join(symbols)}")
        
        return analysis
    
    def _get_cheap_model(self, agent_name: str) -> str:
        """Retourne le modèle le moins cher approprié."""
        # Pour la veille, utiliser des modèles moins chers
        if agent_name == "Grok":
            return "x-ai/grok-3-mini"  # Grok reste sur Grok
        elif agent_name == "DeepSeek":
            return "deepseek/deepseek-chat"  # Très économique
        else:
            return "openai/gpt-4o-mini"  # GPT-4o-mini au lieu de GPT-4o
    
    def _get_last_report(self, agent_name: str) -> Optional[Dict]:
        """Récupère la dernière veille de l'agent pour autocritique."""
        if not supabase_client._initialized:
            return None
        
        try:
            response = supabase_client.client.table('ai_watch_reports').select(
                'created_at, analysis_summary, key_insights, opportunities, confidence_level'
            ).eq('agent_name', agent_name).order('created_at', desc=True).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                report = response.data[0]
                logger.info(f"📋 {agent_name}: Dernière veille trouvée pour autocritique")
                return report
            return None
        except Exception as e:
            logger.warning(f"⚠️ Pas de veille précédente pour {agent_name}: {e}")
            return None
    
    def _build_short_prompt(
        self, 
        agent_name: str, 
        pre_analysis: Dict, 
        context: Dict
    ) -> str:
        """
        Construit un prompt COURT (~400-500 tokens max) avec autocritique.
        """
        # Format ultra-compact
        market_summary = data_aggregator.format_context_for_llm(context, max_tokens=300)
        
        signals = pre_analysis.get("signals", [])
        opportunities = pre_analysis.get("opportunities", [])
        
        signals_str = "\n".join(signals[:5]) if signals else "Aucun signal fort"
        opps_str = ", ".join([f"{o['symbol']}" for o in opportunities[:3]]) if opportunities else "Aucune"
        
        # === AUTOCRITIQUE: Récupérer la dernière veille ===
        autocritique_section = ""
        last_report = self._get_last_report(agent_name)
        if last_report:
            try:
                last_insights = json.loads(last_report.get("key_insights", "[]")) if isinstance(last_report.get("key_insights"), str) else last_report.get("key_insights", [])
                last_opps = json.loads(last_report.get("opportunities", "[]")) if isinstance(last_report.get("opportunities"), str) else last_report.get("opportunities", [])
                last_summary = last_report.get("analysis_summary", "")[:100]
                last_confidence = last_report.get("confidence_level", 50)
                last_time = last_report.get("created_at", "")[:16]
                
                # Construire le résumé compact de la veille précédente
                prev_insights = ", ".join(last_insights[:2]) if last_insights else "Aucun"
                prev_symbols = ", ".join([o.get("symbol", "") for o in last_opps[:2] if isinstance(o, dict)]) if last_opps else "Aucun"
                
                autocritique_section = f"""
📊 TA DERNIÈRE VEILLE ({last_time}):
• Résumé: {last_summary}
• Opportunités suggérées: {prev_symbols}
• Confiance: {last_confidence}%

⚠️ AUTOCRITIQUE: Évalue si tes prévisions étaient justes. Ajuste ta stratégie si nécessaire.
"""
            except Exception as e:
                logger.warning(f"Erreur parsing veille précédente: {e}")
        
        prompt = f"""Tu es {agent_name}. Analyse RAPIDE du marché.

{market_summary}

PRÉ-ANALYSE:
• Condition: {pre_analysis.get('market_condition')}
• Signaux: {signals_str}
• Opportunités potentielles: {opps_str}
{autocritique_section}
RÉPONDS EN JSON COURT (max 200 mots):
{{"action": "BUY/SELL/HOLD", "symbol": "XXX ou null", "confidence": 0-100, "reason": "1 phrase", "autocritique": "1 phrase sur ta dernière prévision"}}
"""
        return prompt
    
    def _parse_short_response(self, response: str) -> Dict[str, Any]:
        """Parse la réponse courte de l'IA."""
        try:
            # Chercher le JSON
            json_match = response[response.find("{"):response.rfind("}")+1]
            if json_match:
                return json.loads(json_match)
        except:
            pass
        
        return {
            "action": "HOLD",
            "symbol": None,
            "confidence": 0,
            "reason": response[:200] if response else "Parse error",
        }
    
    async def run_all_agents_quick(self) -> Dict[str, Any]:
        """
        Lance une analyse rapide pour tous les agents.
        Coût estimé: ~$0.05-0.10 par cycle
        """
        logger.info("⚡ Lancement analyses rapides (mode économique)...")
        
        results = {}
        
        # Séquentiel pour éviter rate limits
        for agent in ["Grok", "DeepSeek", "GPT"]:
            result = await self.run_quick_analysis(agent)
            results[agent] = result
            await asyncio.sleep(0.5)  # Petit délai
        
        # Consortium = synthèse des 3 (SANS LLM supplémentaire)
        results["Consortium"] = self._synthesize_without_llm(results)
        
        return results
    
    def _synthesize_without_llm(self, agent_results: Dict) -> Dict[str, Any]:
        """
        Synthétise les résultats du Consortium SANS appel LLM.
        Économise des tokens!
        """
        votes = {"BUY": 0, "SELL": 0, "HOLD": 0}
        symbols = {}
        confidences = []
        
        for agent_name, result in agent_results.items():
            if agent_name == "Consortium":
                continue
            
            insights = result.get("ai_insights", {})
            action = insights.get("action", "HOLD")
            symbol = insights.get("symbol")
            confidence = insights.get("confidence", 0)
            
            votes[action] = votes.get(action, 0) + 1
            confidences.append(confidence)
            
            if symbol:
                symbols[symbol] = symbols.get(symbol, 0) + 1
        
        # Décision par vote
        final_action = max(votes, key=votes.get)
        final_symbol = max(symbols, key=symbols.get) if symbols else None
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            "agent_name": "Consortium",
            "timestamp": datetime.now().isoformat(),
            "pre_analysis": {"market_condition": "SYNTHESIZED"},
            "ai_insights": {
                "action": final_action,
                "symbol": final_symbol,
                "confidence": int(avg_confidence),
                "reason": f"Consensus {votes[final_action]}/3 agents",
                "votes": votes,
            },
            "model_used": "local_synthesis",
            "processing_time_ms": 0,
            "llm_call": False,  # Pas d'appel LLM!
        }
    
    def get_daily_usage_report(self) -> Dict[str, Any]:
        """Rapport d'utilisation quotidien."""
        self._reset_daily_if_needed()
        
        return {
            "date": self._last_reset.isoformat(),
            "tokens": {
                "prompt": self._daily_token_usage["prompt"],
                "completion": self._daily_token_usage["completion"],
                "total": self._daily_token_usage["prompt"] + self._daily_token_usage["completion"],
            },
            "cost_usd": round(self._daily_token_usage["cost_usd"], 4),
            "budget_usd": self._daily_budget_usd,
            "budget_remaining": round(self._daily_budget_usd - self._daily_token_usage["cost_usd"], 4),
            "budget_used_pct": round(
                (self._daily_token_usage["cost_usd"] / self._daily_budget_usd) * 100, 1
            ),
        }
    
    def set_daily_budget(self, budget_usd: float):
        """Définit le budget quotidien."""
        self._daily_budget_usd = budget_usd
        logger.info(f"💰 Budget quotidien fixé à ${budget_usd}")


# Instance globale
optimized_watch = OptimizedWatchService()

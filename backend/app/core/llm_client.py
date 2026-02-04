"""
Client LLM pour OpenRouter.
Permet d'accéder à plusieurs modèles IA via une API unifiée.
"""
import logging
import json
from typing import Optional, Dict, Any, List
import httpx

from .config import settings, AI_MODELS

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Client pour interagir avec OpenRouter API.
    Supporte plusieurs modèles: Grok, DeepSeek, OpenAI, etc.
    """
    
    def __init__(self):
        """Initialise le client LLM."""
        self.base_url = settings.openrouter_base_url
        self.api_key = settings.openrouter_api_key
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialise la connexion OpenRouter."""
        if not settings.is_openrouter_configured():
            logger.warning("⚠️ OpenRouter non configuré - clé API manquante")
            return False
        
        self._initialized = True
        logger.info("✅ OpenRouter initialisé")
        return True
    
    def _get_headers(self) -> Dict[str, str]:
        """Retourne les headers pour les requêtes."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://trademe.app",
            "X-Title": "TradeMe Trading Bot",
        }
    
    async def generate_response(
        self,
        model: str,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Génère une réponse à partir d'un modèle LLM.
        
        Args:
            model: ID du modèle (ex: "openai/gpt-4o")
            system_prompt: Instructions système
            user_content: Contenu de l'utilisateur
            temperature: Créativité (0-1)
            max_tokens: Nombre max de tokens
            tools: Outils disponibles pour l'agent
            
        Returns: Dict avec la réponse ou None si erreur
        """
        if not self._initialized:
            logger.error("LLM Client non initialisé")
            return None
        
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            # Ajouter les tools si fournis
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                
                if response.status_code != 200:
                    logger.error(f"Erreur OpenRouter {response.status_code}: {response.text}")
                    return None
                
                data = response.json()
                
                if "choices" not in data or len(data["choices"]) == 0:
                    logger.error("Réponse OpenRouter vide")
                    return None
                
                choice = data["choices"][0]
                message = choice.get("message", {})
                
                result = {
                    "content": message.get("content", ""),
                    "role": message.get("role", "assistant"),
                    "model": data.get("model", model),
                    "finish_reason": choice.get("finish_reason", ""),
                    "usage": data.get("usage", {}),
                }
                
                # Ajouter les tool_calls si présents
                if "tool_calls" in message:
                    result["tool_calls"] = message["tool_calls"]
                
                return result
                
        except httpx.TimeoutException:
            logger.error(f"Timeout OpenRouter pour {model}")
            return None
        except Exception as e:
            logger.error(f"Erreur generate_response: {e}")
            return None
    
    async def generate_trading_decision(
        self,
        model: str,
        system_prompt: str,
        market_context: str,
        history: List[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Génère une décision de trading structurée.
        
        Args:
            model: ID du modèle
            system_prompt: Personnalité de l'agent
            market_context: Contexte du marché actuel
            history: Historique des décisions passées
            
        Returns: Décision de trading au format JSON
        """
        if not self._initialized:
            return None
        
        # Construire le prompt utilisateur
        user_prompt = f"""
## CONTEXTE DU MARCHÉ
{market_context}

## HISTORIQUE RÉCENT
{json.dumps(history[-5:] if history else [], indent=2)}

## INSTRUCTION
Analyse le marché et prends une décision. Réponds UNIQUEMENT avec un JSON valide:

```json
{{
    "decision": "BUY" | "SELL" | "HOLD",
    "symbol": "TICKER",
    "quantity": <nombre>,
    "reasoning": "<explication détaillée>",
    "confidence": <0-100>,
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "target_price": <prix cible optionnel>,
    "stop_loss": <stop loss optionnel>
}}
```
"""
        
        try:
            response = await self.generate_response(
                model=model,
                system_prompt=system_prompt,
                user_content=user_prompt,
                temperature=0.5,  # Moins créatif pour les décisions
                max_tokens=1500,
            )
            
            if not response or not response.get("content"):
                return None
            
            content = response["content"]
            
            # Extraire le JSON de la réponse
            decision = self._parse_json_from_response(content)
            
            if decision:
                decision["raw_response"] = content
                decision["model"] = model
            
            return decision
            
        except Exception as e:
            logger.error(f"Erreur generate_trading_decision: {e}")
            return None
    
    def _parse_json_from_response(self, content: str) -> Optional[Dict]:
        """Extrait le JSON d'une réponse textuelle."""
        try:
            # Essayer de parser directement
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Chercher un bloc JSON dans le texte
        try:
            start_markers = ["{", "```json\n{", "```\n{"]
            end_markers = ["}", "}\n```", "}\n```"]
            
            for start_marker, end_marker in zip(start_markers, end_markers):
                if start_marker in content:
                    start_idx = content.find("{")
                    end_idx = content.rfind("}") + 1
                    
                    if start_idx != -1 and end_idx > start_idx:
                        json_str = content[start_idx:end_idx]
                        return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        logger.warning(f"Impossible de parser JSON depuis: {content[:200]}...")
        return None
    
    async def generate_autocritique(
        self,
        model: str,
        agent_name: str,
        trade_history: List[Dict],
        total_fees: float,
        current_performance: float,
    ) -> Optional[str]:
        """
        Génère une autocritique pour améliorer les décisions.
        
        Args:
            model: ID du modèle
            agent_name: Nom de l'agent
            trade_history: Historique des trades
            total_fees: Frais accumulés
            current_performance: Performance actuelle en %
            
        Returns: Monologue interne de l'agent
        """
        prompt = f"""
Tu es {agent_name}, un trader IA. Analyse ton historique récent et fais une autocritique honnête.

## TON HISTORIQUE
{json.dumps(trade_history[-10:] if trade_history else [], indent=2)}

## MÉTRIQUES
- Frais payés: ${total_fees:.2f}
- Performance: {current_performance:+.2f}%

## QUESTIONS À TE POSER
1. Est-ce que je trade trop souvent ? (Chaque trade = $1 de frais)
2. Est-ce que je suis le troupeau ou je cherche des opportunités uniques ?
3. Ai-je raté des signaux de vente ?
4. Comment puis-je faire PLUS de profit ?
5. Quels patterns dois-je éviter ?

Réponds avec un monologue interne honnête (200 mots max).
"""
        
        response = await self.generate_response(
            model=model,
            system_prompt="Tu es un trader IA qui s'auto-évalue de manière critique et honnête.",
            user_content=prompt,
            temperature=0.7,
            max_tokens=500,
        )
        
        if response and response.get("content"):
            return response["content"]
        return None
    
    async def test_connection(self, model: str = "openai/gpt-4o-mini") -> Dict[str, Any]:
        """
        Teste la connexion à OpenRouter.
        
        Returns: Dict avec statut du test
        """
        try:
            response = await self.generate_response(
                model=model,
                system_prompt="Tu es un assistant de test.",
                user_content="Réponds juste 'OK' si tu reçois ce message.",
                temperature=0,
                max_tokens=10,
            )
            
            if response and response.get("content"):
                return {
                    "success": True,
                    "model": model,
                    "response": response["content"],
                    "usage": response.get("usage", {}),
                }
            else:
                return {
                    "success": False,
                    "model": model,
                    "error": "Réponse vide",
                }
                
        except Exception as e:
            return {
                "success": False,
                "model": model,
                "error": str(e),
            }
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Récupère la liste des modèles disponibles."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._get_headers(),
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                    
        except Exception as e:
            logger.error(f"Erreur get_available_models: {e}")
        
        return []


# Instance globale
llm_client = LLMClient()

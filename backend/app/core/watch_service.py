"""
AI Watch Service - Service de Veille Intelligente.
Permet aux IAs de faire une veille technologique et préparer leurs trades.
"""
import logging
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum

from ..core.config import settings
from ..core.llm_client import llm_client
from ..core.news_aggregator import news_aggregator
from ..core.alpaca_client import alpaca_client
from ..core.supabase_client import supabase_client
from ..core.x_twitter_service import x_service

logger = logging.getLogger(__name__)


class WatchReportType(str, Enum):
    HOURLY_WATCH = "hourly_watch"       # Veille horaire (marché fermé)
    MARKET_ANALYSIS = "market_analysis"  # Analyse à l'ouverture
    POSITION_REVIEW = "position_review"  # Revue des positions
    OPPORTUNITY_SCAN = "opportunity_scan" # Scan d'opportunités
    NEWS_DIGEST = "news_digest"          # Digest des actualités


class MarketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    AFTER_HOURS = "after_hours"


# Questions de veille pour chaque IA (20-30 questions par IA)
GROK_WATCH_QUESTIONS = """
## QUESTIONS DE VEILLE GROK - Chasseur d'Opportunités

### 📰 ANALYSE DES ACTUALITÉS
1. Y a-t-il des news surprises sur des earnings qui viennent de tomber ?
2. Une FDA approval ou rejection a-t-elle été annoncée ?
3. Y a-t-il des rumeurs de fusion/acquisition sur X (Twitter) ou les news ?
4. Quelle entreprise fait parler d'elle sur les réseaux sociaux en ce moment ?
5. Un CEO a-t-il fait des déclarations importantes récemment ?
6. Y a-t-il des contrats gouvernementaux ou majeurs annoncés ?
7. Une entreprise a-t-elle annoncé un buyback ou dividende surprise ?

### 📊 ANALYSE TECHNIQUE & MOMENTUM
8. Quelles actions ont un volume anormalement élevé en pre-market ?
9. Quels gaps (up/down) importants vois-je sur les graphiques ?
10. Y a-t-il des setups de breakout imminents sur des résistances clés ?
11. Quelles actions sont en short squeeze potentiel ?
12. Où est le momentum le plus fort en ce moment (secteur, action) ?

### 🎯 OPPORTUNITÉS COURT TERME
13. Quelle action peut faire +5% dans les prochaines heures ?
14. Y a-t-il un trade de news que je peux exploiter avant les autres ?
15. Quels earnings reports sont prévus cette semaine - opportunité de swing ?
16. Y a-t-il des IPOs récentes qui peuvent être volatiles ?
17. Quel secteur montre des signes de rotation entrante ?

### 💰 GESTION DES POSITIONS
18. Mes positions actuelles sont-elles toujours dans la bonne direction ?
19. Dois-je prendre des profits partiels quelque part ?
20. Y a-t-il une news négative sur une de mes positions que j'ai ratée ?
21. Mon stop-loss est-il bien placé ou dois-je l'ajuster ?

### 🔮 ANTICIPATION
22. Quels événements macroéconomiques arrivent (Fed, CPI, jobs report) ?
23. Y a-t-il des catalyseurs planifiés que je peux anticiper ?
24. Quel sera l'impact de ces événements sur mes positions ?
25. Comment le marché global va-t-il affecter mes trades ?

### ⚡ ACTIONS SPÉCIALES (X/TWITTER)
26. Que dit Elon Musk sur X récemment ? Impact sur Tesla, SpaceX, xAI ?
27. Y a-t-il du buzz sur crypto ou meme stocks sur X ?
28. Des influenceurs financiers parlent-ils d'une action spécifique ?
29. Y a-t-il un sentiment particulier qui émerge sur X ?
30. Trending topics sur X liés à la finance ?
"""

DEEPSEEK_WATCH_QUESTIONS = """
## QUESTIONS DE VEILLE DEEPSEEK - Analyste Multi-Sources

### 📊 ANALYSE FONDAMENTALE
1. Quels bilans trimestriels ont été publiés récemment ?
2. Les revenus et marges sont-ils en croissance ou déclin ?
3. Y a-t-il des divergences entre les prévisions et les résultats ?
4. Comment se comportent les ratios P/E, P/S des actions que je surveille ?
5. Y a-t-il des entreprises sous-évaluées selon les métriques fondamentales ?
6. Quel est le niveau d'endettement des entreprises ciblées ?
7. Les free cash flows sont-ils positifs et croissants ?

### 📈 ANALYSE TECHNIQUE APPROFONDIE
8. Quels patterns chartistes se forment (head & shoulders, cup & handle, etc.) ?
9. Où sont les niveaux de support et résistance majeurs ?
10. Que disent les moyennes mobiles (50, 200 jours) ?
11. RSI et MACD montrent-ils des divergences ?
12. Y a-t-il des signaux de retournement de tendance ?
13. Quel est le ratio volume/prix sur les mouvements récents ?

### 🔍 CROSS-RÉFÉRENCEMENT
14. Les news confirment-elles la tendance technique ?
15. Y a-t-il contradiction entre sentiment et fondamentaux ?
16. Les insiders achètent-ils ou vendent-ils ?
17. Que font les institutionnels sur ces actions ?
18. Les analystes sont-ils bullish ou bearish ? Consensus vs réalité ?
19. Y a-t-il des options unusual activity à noter ?

### 📰 ANALYSE DES NEWS
20. Quelle est la tonalité générale des news (positive, négative, neutre) ?
21. Y a-t-il des informations contradictoires sur la même entreprise ?
22. Quel est le sentiment global du marché aujourd'hui ?
23. Y a-t-il des news macro qui impactent plusieurs secteurs ?
24. Des analystes ont-ils changé leurs ratings récemment ?

### 🎯 CONVERGENCE DES SIGNAUX
25. Y a-t-il une action où TOUS mes indicateurs convergent ?
26. Quelle est ma conviction sur chaque opportunité (1-10) ?
27. Où est le meilleur ratio risk/reward en ce moment ?
28. Quelles positions dois-je éviter car trop de signaux mixtes ?

### 💼 STRATÉGIE
29. Quel % de mon capital dois-je allouer à chaque opportunité ?
30. Quels stops et targets sont optimaux basés sur la volatilité ?
"""

GPT_WATCH_QUESTIONS = """
## QUESTIONS DE VEILLE GPT - Stratège Calculé

### 🧠 ASYMÉTRIE D'INFORMATION
1. Y a-t-il une news que le marché n'a pas encore correctement pricée ?
2. Quelles informations cachées dans les filings SEC peuvent donner un edge ?
3. Y a-t-il des patterns saisonniers ou calendaires à exploiter ?
4. Quel est le consensus du marché ? Puis-je le contrarian de manière profitable ?
5. Y a-t-il un gap entre perception et réalité sur une entreprise ?

### 📊 ANALYSE COMPORTEMENTALE DU MARCHÉ
6. Comment réagit le marché aux news ? Overreaction ou underreaction ?
7. Y a-t-il de la peur (VIX élevé) à exploiter ?
8. Le marché est-il en mode "risk-on" ou "risk-off" ?
9. Quels secteurs sont délaissés mais fondamentalement solides ?
10. Y a-t-il des anomalies de prix temporaires à arbitrer ?

### 🎯 STRATÉGIE DE POSITION
11. Quelle est la taille optimale de position compte tenu du risque ?
12. Dois-je entrer en une fois ou en plusieurs tranches ?
13. Quel est mon edge spécifique sur ce trade ?
14. Quel est le scénario bear case pour ma thèse ?
15. Combien suis-je prêt à perdre sur ce trade (max drawdown) ?

### 📈 TIMING & EXÉCUTION
16. Est-ce le bon moment pour entrer ou dois-je attendre ?
17. Y a-t-il un meilleur point d'entrée technique ?
18. Le spread bid-ask est-il acceptable ?
19. Dois-je utiliser un limit order ou market order ?
20. Y a-t-il des événements proches qui pourraient créer de la volatilité ?

### 💰 GESTION DU PORTEFEUILLE
21. Mon portefeuille est-il bien diversifié en termes de risque ?
22. Ai-je trop de corrélation entre mes positions ?
23. Quel est mon exposition sectorielle actuelle ?
24. Dois-je réduire une position pour en ajouter une nouvelle ?
25. Mon ratio cash/investis est-il optimal ?

### 🔮 SCÉNARIOS & PROBABILITÉS
26. Quel est le scénario le plus probable pour demain/cette semaine ?
27. Quels black swans pourraient affecter mes positions ?
28. Comment le marché réagira-t-il aux prochains catalyseurs ?
29. Quelle est ma probabilité de succès sur chaque trade (%) ?
30. Si tout va mal, quel est mon plan B ?
"""

CONSORTIUM_WATCH_QUESTIONS = """
## QUESTIONS DE VEILLE CONSORTIUM - Synthèse Collaborative

### 🤝 ANALYSE DES CONSENSUS
1. Sur quels trades les 3 IAs sont-elles d'accord ?
2. Y a-t-il des désaccords importants ? Pourquoi ?
3. Quel agent a le meilleur track record récent ?
4. Les agents avec bonnes perfs récentes recommandent-ils la même chose ?
5. Y a-t-il un trade risqué qu'un seul agent recommande mais qui semble intéressant ?

### 📊 MÉTA-ANALYSE
6. Quelles opportunités reviennent chez au moins 2 agents ?
7. Les niveaux de confiance des agents sont-ils cohérents ?
8. Y a-t-il des contradictions évidentes dans les analyses ?
9. Quel agent semble avoir la meilleure information sur ce trade ?
10. Dois-je pondérer différemment les votes aujourd'hui ?

### 🎯 DÉCISION COLLECTIVE
11. Quel est le trade avec le meilleur consensus ?
12. Le risk/reward collectif est-il acceptable ?
13. Dois-je suivre la majorité ou un agent spécifique ?
14. Y a-t-il une urgence qui nécessite une décision rapide ?
15. Dois-je attendre plus d'information avant de décider ?

### 💼 ALLOCATION
16. Comment répartir le capital entre les recommandations ?
17. Dois-je diversifier les trades ou concentrer ?
18. Quel % du capital total engager maintenant ?
19. Garder du cash pour des opportunités futures ?
20. Y a-t-il un trade "safe" pour équilibrer les risques ?

### ⚖️ GESTION DU RISQUE
21. Quel est le risque total du portefeuille si tout va mal ?
22. Les stops recommandés par chaque agent sont-ils cohérents ?
23. Dois-je ajuster les tailles de position basé sur le consensus ?
24. Y a-t-il une exposition excessive à un secteur/thème ?
25. Quel est le plan si le marché crash soudainement ?
"""


class AIWatchService:
    """
    Service de veille intelligente pour les agents IA.
    
    Fonctionnalités:
    - Veille horaire (marché fermé): Les IAs analysent et préparent
    - Analyse à l'ouverture: Décision d'action basée sur la veille
    - Revue des positions (toutes les 5 min): Surveillance active
    """
    
    def __init__(self):
        self._initialized = False
        self._agent_questions = {
            "Grok": GROK_WATCH_QUESTIONS,
            "DeepSeek": DEEPSEEK_WATCH_QUESTIONS,
            "GPT": GPT_WATCH_QUESTIONS,
            "Consortium": CONSORTIUM_WATCH_QUESTIONS,
        }
    
    def initialize(self) -> bool:
        """Initialise le service de veille."""
        self._initialized = True
        logger.info("✅ AIWatchService initialisé")
        return True
    
    def _get_market_status(self) -> MarketStatus:
        """Détermine le statut actuel du marché."""
        try:
            if alpaca_client.is_market_open():
                return MarketStatus.OPEN
            
            # Vérifier pre-market/after-hours
            hours = alpaca_client.get_market_hours()
            if hours:
                now = datetime.now()
                # Simplification: si pas ouvert, on est fermé
                return MarketStatus.CLOSED
        except Exception:
            pass
        
        return MarketStatus.CLOSED
    
    async def run_hourly_watch(self, agent_name: str, agent_id: str = None) -> Dict[str, Any]:
        """
        Lance une session de veille horaire pour un agent.
        
        Cette fonction fait réfléchir l'IA sur les questions de veille
        et stocke ses insights pour l'ouverture du marché.
        
        Args:
            agent_name: Nom de l'agent (Grok, DeepSeek, GPT, Consortium)
            agent_id: UUID de l'agent en BDD
            
        Returns:
            Rapport de veille complet
        """
        start_time = time.time()
        logger.info(f"🔍 {agent_name}: Début de la veille horaire...")
        
        market_status = self._get_market_status()
        questions = self._agent_questions.get(agent_name, "")
        
        # Récupérer les données de marché
        market_data = await self._gather_market_data()
        
        # Récupérer les actualités
        news_text = await self._gather_news()
        
        # Pour Grok, ajouter les données X (Twitter)
        x_data_text = ""
        if agent_name == "Grok":
            x_data_text = await self._gather_x_data()
            if x_data_text:
                news_text = news_text + "\n\n" + x_data_text
        
        # Récupérer les positions actuelles de l'agent
        positions = await self._get_agent_positions(agent_id)
        
        # Construire le prompt de veille
        prompt = self._build_watch_prompt(
            agent_name=agent_name,
            questions=questions,
            market_data=market_data,
            news=news_text,
            positions=positions,
            market_status=market_status,
        )
        
        # Appeler le LLM approprié
        model = self._get_model_for_agent(agent_name)
        
        try:
            result = await llm_client.generate_response(
                model=model,
                system_prompt=f"Tu es {agent_name}, un analyste trading expert. Analyse le marché et réponds en JSON.",
                user_content=prompt,
                max_tokens=4000,
                temperature=0.7,
            )
            
            # Extraire le texte de la réponse (format: {"content": "...", ...})
            response = ""
            if result and result.get("content"):
                response = result["content"]
                logger.info(f"📝 {agent_name}: Réponse LLM reçue ({len(response)} chars)")
            else:
                logger.warning(f"⚠️ {agent_name}: Réponse LLM vide ou malformée: {result}")
            
            # Parser la réponse
            report = self._parse_watch_response(response, agent_name)
            
        except Exception as e:
            logger.error(f"❌ Erreur LLM pour {agent_name}: {e}")
            report = {
                "analysis_summary": f"Erreur lors de l'analyse: {str(e)}",
                "key_insights": [],
                "opportunities": [],
                "risks": [],
                "watchlist": [],
                "planned_actions": [],
                "confidence_level": 0,
            }
        
        # Calculer le temps de traitement
        processing_time = int((time.time() - start_time) * 1000)
        
        # Préparer le rapport final
        final_report = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "report_type": WatchReportType.HOURLY_WATCH.value,
            "market_status": market_status.value,
            "analysis_summary": report.get("analysis_summary", ""),
            "key_insights": json.dumps(report.get("key_insights", [])),
            "opportunities": json.dumps(report.get("opportunities", [])),
            "risks": json.dumps(report.get("risks", [])),
            "watchlist": json.dumps(report.get("watchlist", [])),
            "planned_actions": json.dumps(report.get("planned_actions", [])),
            "confidence_level": report.get("confidence_level", 50),
            "questions_asked": json.dumps(questions.split("\n")[:30]),
            "answers": json.dumps(report.get("answers", [])),
            "sources_consulted": json.dumps(["alpaca_news", "market_movers", "positions"]),
            "processing_time_ms": processing_time,
        }
        
        # Sauvegarder en BDD
        if supabase_client._initialized:
            try:
                supabase_client.client.table('ai_watch_reports').insert(final_report).execute()
                logger.info(f"✅ {agent_name}: Rapport de veille sauvegardé")
            except Exception as e:
                logger.error(f"❌ Erreur sauvegarde rapport {agent_name}: {e}")
        
        # Sauvegarder les opportunités détectées
        for opp in report.get("opportunities", []):
            await self._save_opportunity(agent_id, opp)
        
        logger.info(f"✅ {agent_name}: Veille terminée en {processing_time}ms")
        
        return final_report
    
    async def run_position_review(self, agent_name: str, agent_id: str = None) -> Dict[str, Any]:
        """
        Lance une revue des positions pour un agent (toutes les 5 minutes).
        
        Vérifie les positions ouvertes et décide si:
        - Garder (hold)
        - Renforcer (add)
        - Réduire (reduce)
        - Fermer (close)
        - Ajuster le stop (move_stop)
        """
        logger.info(f"👀 {agent_name}: Revue des positions...")
        
        positions = await self._get_agent_positions(agent_id)
        
        if not positions:
            return {"message": "Aucune position à revoir", "reviews": []}
        
        reviews = []
        
        for position in positions:
            review = await self._review_single_position(
                agent_name=agent_name,
                agent_id=agent_id,
                position=position,
            )
            reviews.append(review)
        
        return {
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat(),
            "reviews": reviews,
        }
    
    async def run_all_agents_watch(self) -> Dict[str, Any]:
        """
        Lance la veille pour tous les agents en parallèle.
        """
        logger.info("🔍 Lancement de la veille pour tous les agents...")
        
        # Récupérer les IDs des agents depuis la BDD
        agents = supabase_client.get_agents() if supabase_client._initialized else []
        agent_ids = {a["name"]: a["id"] for a in agents}
        
        # Lancer en parallèle
        tasks = []
        for agent_name in ["Grok", "DeepSeek", "GPT", "Consortium"]:
            agent_id = agent_ids.get(agent_name)
            tasks.append(self.run_hourly_watch(agent_name, agent_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        reports = {}
        for agent_name, result in zip(["Grok", "DeepSeek", "GPT", "Consortium"], results):
            if isinstance(result, Exception):
                reports[agent_name] = {"error": str(result)}
            else:
                reports[agent_name] = result
        
        return reports
    
    async def run_all_position_reviews(self) -> Dict[str, Any]:
        """
        Lance la revue des positions pour tous les agents.
        """
        logger.info("👀 Lancement des revues de positions...")
        
        agents = supabase_client.get_agents() if supabase_client._initialized else []
        agent_ids = {a["name"]: a["id"] for a in agents}
        
        tasks = []
        for agent_name in ["Grok", "DeepSeek", "GPT"]:  # Pas Consortium
            agent_id = agent_ids.get(agent_name)
            tasks.append(self.run_position_review(agent_name, agent_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        reviews = {}
        for agent_name, result in zip(["Grok", "DeepSeek", "GPT"], results):
            if isinstance(result, Exception):
                reviews[agent_name] = {"error": str(result)}
            else:
                reviews[agent_name] = result
        
        return reviews
    
    # === Méthodes privées ===
    
    async def _gather_market_data(self) -> Dict[str, Any]:
        """Collecte les données de marché pour la veille."""
        data = {}
        
        try:
            data["movers"] = alpaca_client.get_movers(limit=20)
        except Exception:
            data["movers"] = {}
        
        try:
            data["market_hours"] = alpaca_client.get_market_hours()
        except Exception:
            data["market_hours"] = {}
        
        return data
    
    async def _gather_news(self) -> str:
        """Collecte les actualités formatées."""
        try:
            return await news_aggregator.format_news_for_agent(limit=20)
        except Exception as e:
            logger.error(f"Erreur collecte news: {e}")
            return "Actualités non disponibles"
    
    async def _gather_x_data(self) -> str:
        """Collecte les données X (Twitter) pour Grok."""
        try:
            # Initialiser le service X si pas déjà fait
            if not x_service._initialized:
                x_service.initialize()
            
            # Récupérer les tendances et tweets
            trends = await x_service.get_trending_topics()
            tweets = await x_service.get_influencer_mentions()
            
            # Formater pour Grok
            return x_service.format_for_grok(trends, tweets)
            
        except Exception as e:
            logger.error(f"Erreur collecte X data: {e}")
            return ""
    
    async def _get_agent_positions(self, agent_id: str) -> List[Dict]:
        """Récupère les positions d'un agent."""
        if not agent_id or not supabase_client._initialized:
            return []
        
        try:
            response = supabase_client.client.table('positions').select('*').eq('agent_id', agent_id).execute()
            return response.data if response.data else []
        except Exception:
            return []
    
    def _get_model_for_agent(self, agent_name: str) -> str:
        """Retourne le modèle LLM approprié pour chaque agent."""
        models = {
            "Grok": settings.grok_model,
            "DeepSeek": settings.deepseek_model,
            "GPT": settings.openai_model,
            "Consortium": settings.openai_model,  # GPT pour Consortium
        }
        return models.get(agent_name, settings.openai_model)
    
    def _build_watch_prompt(
        self,
        agent_name: str,
        questions: str,
        market_data: Dict,
        news: str,
        positions: List[Dict],
        market_status: MarketStatus,
    ) -> str:
        """Construit le prompt de veille pour l'IA."""
        
        # Formater les positions
        positions_text = "Aucune position ouverte"
        if positions:
            pos_list = []
            for p in positions:
                pnl = p.get('unrealized_pnl', 0)
                pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                pos_list.append(
                    f"- {p['symbol']}: {p['quantity']} shares @ ${p.get('entry_price', 'N/A')} "
                    f"(P&L: {pnl_emoji} ${pnl:.2f})"
                )
            positions_text = "\n".join(pos_list)
        
        # Formater les movers
        movers_text = "Données movers non disponibles"
        if market_data.get("movers"):
            movers = market_data["movers"]
            movers_list = []
            
            if movers.get("gainers"):
                movers_list.append("📈 TOP GAINERS:")
                for g in movers["gainers"][:5]:
                    movers_list.append(f"  {g['symbol']}: +{g['change_pct']:.2f}% (${g['price']:.2f})")
            
            if movers.get("losers"):
                movers_list.append("\n📉 TOP LOSERS:")
                for l in movers["losers"][:5]:
                    movers_list.append(f"  {l['symbol']}: {l['change_pct']:.2f}% (${l['price']:.2f})")
            
            movers_text = "\n".join(movers_list) if movers_list else movers_text
        
        prompt = f"""
# SESSION DE VEILLE - {agent_name.upper()}

## CONTEXTE
- Date/Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Statut du marché: {market_status.value.upper()}
- Type de session: {'PRÉPARATION (marché fermé)' if market_status != MarketStatus.OPEN else 'SURVEILLANCE ACTIVE'}

## TES POSITIONS ACTUELLES
{positions_text}

## DONNÉES DE MARCHÉ
{movers_text}

## ACTUALITÉS RÉCENTES
{news}

---

## TES QUESTIONS DE VEILLE
Tu dois analyser le marché en te posant les questions suivantes et y répondre de manière approfondie:

{questions}

---

## FORMAT DE RÉPONSE ATTENDU
Réponds en JSON avec cette structure exacte:

```json
{{
    "analysis_summary": "Résumé de ton analyse en 2-3 paragraphes",
    "key_insights": [
        "Insight 1 important",
        "Insight 2 important",
        "..."
    ],
    "opportunities": [
        {{
            "symbol": "AAPL",
            "direction": "bullish",
            "opportunity_type": "momentum",
            "reasoning": "Pourquoi cette opportunité",
            "entry_price": 150.00,
            "target_price": 158.00,
            "stop_loss": 147.00,
            "confidence": 75,
            "timeframe": "1-2 jours"
        }}
    ],
    "risks": [
        "Risque 1 identifié",
        "Risque 2 identifié"
    ],
    "watchlist": [
        {{"symbol": "NVDA", "reason": "Surveiller pour breakout"}},
        {{"symbol": "TSLA", "reason": "Volatilité earnings"}}
    ],
    "planned_actions": [
        {{
            "action": "BUY" ou "SELL" ou "WATCH",
            "symbol": "AAPL",
            "condition": "Si le prix atteint X",
            "size_pct": 10,
            "priority": 1
        }}
    ],
    "confidence_level": 70,
    "answers": [
        {{"question": "Question 1", "answer": "Ma réponse détaillée"}},
        {{"question": "Question 2", "answer": "Ma réponse détaillée"}}
    ]
}}
```

IMPORTANT: 
- Sois CONCRET et ACTIONNABLE
- Donne des prix précis, des % précis
- Ne sois pas vague
- Focus sur le PROFIT
- Réponds à au moins 10 questions clés

Réponds UNIQUEMENT avec le JSON, sans texte autour.
"""
        return prompt
    
    def _parse_watch_response(self, response: str, agent_name: str) -> Dict[str, Any]:
        """Parse la réponse JSON du LLM."""
        if not response:
            logger.warning(f"⚠️ {agent_name}: Réponse vide à parser")
            return self._default_report_response(response)
        
        try:
            # Extraire le JSON de la réponse
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                logger.info(f"✅ {agent_name}: JSON parsé avec succès - {len(parsed.get('key_insights', []))} insights")
                return parsed
            else:
                logger.warning(f"⚠️ {agent_name}: Pas de JSON trouvé dans la réponse")
        except Exception as e:
            logger.error(f"❌ Erreur parsing JSON {agent_name}: {e}")
            logger.debug(f"Réponse brute: {response[:500]}")
        
        return self._default_report_response(response)
    
    def _default_report_response(self, response: str = "") -> Dict[str, Any]:
        """Retourne un rapport par défaut."""
        return {
            "analysis_summary": response[:500] if response else "Analyse non disponible",
            "key_insights": [],
            "opportunities": [],
            "risks": [],
            "watchlist": [],
            "planned_actions": [],
            "confidence_level": 50,
            "answers": [],
        }
    
    async def _save_opportunity(self, agent_id: str, opportunity: Dict) -> None:
        """Sauvegarde une opportunité détectée en BDD."""
        if not agent_id or not supabase_client._initialized:
            return
        
        try:
            opp_data = {
                "agent_id": agent_id,
                "symbol": opportunity.get("symbol", ""),
                "opportunity_type": opportunity.get("opportunity_type", "technical_setup"),
                "direction": opportunity.get("direction", "neutral"),
                "expected_move_pct": opportunity.get("expected_move_pct"),
                "timeframe": opportunity.get("timeframe"),
                "entry_price": opportunity.get("entry_price"),
                "target_price": opportunity.get("target_price"),
                "stop_loss": opportunity.get("stop_loss"),
                "confidence": opportunity.get("confidence", 50),
                "reasoning": opportunity.get("reasoning", ""),
                "status": "pending",
            }
            
            supabase_client.client.table('watch_opportunities').insert(opp_data).execute()
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde opportunité: {e}")
    
    async def _review_single_position(
        self,
        agent_name: str,
        agent_id: str,
        position: Dict,
    ) -> Dict[str, Any]:
        """Revoit une position unique et décide de l'action."""
        
        symbol = position.get("symbol", "")
        entry_price = position.get("entry_price", 0)
        quantity = position.get("quantity", 0)
        
        # Obtenir le prix actuel
        try:
            current_price = alpaca_client.get_latest_price(symbol)
        except Exception:
            current_price = entry_price
        
        unrealized_pnl = (current_price - entry_price) * quantity
        unrealized_pnl_pct = ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0
        
        prompt = f"""
# REVUE DE POSITION - {agent_name}

## POSITION
- Symbol: {symbol}
- Quantité: {quantity}
- Prix d'entrée: ${entry_price:.2f}
- Prix actuel: ${current_price:.2f}
- P&L non réalisé: ${unrealized_pnl:.2f} ({unrealized_pnl_pct:+.2f}%)

## DÉCISION REQUISE
Analyse cette position et décide:
1. HOLD - Garder la position telle quelle
2. ADD - Renforcer la position
3. REDUCE - Réduire la position
4. CLOSE - Fermer entièrement
5. MOVE_STOP - Ajuster le stop-loss

Réponds en JSON:
```json
{{
    "decision": "HOLD|ADD|REDUCE|CLOSE|MOVE_STOP",
    "reasoning": "Explication de ta décision",
    "confidence": 75,
    "new_stop_loss": 145.00,
    "new_target": 165.00
}}
```
"""
        
        model = self._get_model_for_agent(agent_name)
        
        try:
            llm_result = await llm_client.generate_response(
                model=model,
                system_prompt=f"Tu es {agent_name}, un analyste trading expert. Analyse cette position et réponds en JSON.",
                user_content=prompt,
                max_tokens=500,
                temperature=0.5,
            )
            
            # Extraire le texte de la réponse (format: {"content": "...", ...})
            response = ""
            if llm_result and llm_result.get("content"):
                response = llm_result["content"]
            
            # Parser la réponse
            result = self._parse_watch_response(response, agent_name)
            
        except Exception as e:
            result = {
                "decision": "HOLD",
                "reasoning": f"Erreur d'analyse: {str(e)}",
                "confidence": 0,
            }
        
        # Sauvegarder la revue en BDD
        if supabase_client._initialized:
            try:
                review_data = {
                    "agent_id": agent_id,
                    "symbol": symbol,
                    "position_type": "long" if quantity > 0 else "short",
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "quantity": abs(quantity),
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_pct": unrealized_pnl_pct,
                    "decision": result.get("decision", "HOLD").lower(),
                    "new_stop_loss": result.get("new_stop_loss"),
                    "new_target": result.get("new_target"),
                    "reasoning": result.get("reasoning", ""),
                    "confidence": result.get("confidence", 0),
                }
                
                supabase_client.client.table('position_reviews').insert(review_data).execute()
                
            except Exception as e:
                logger.error(f"Erreur sauvegarde review: {e}")
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            **result,
        }
    
    def get_latest_reports(
        self,
        agent_name: str = None,
        report_type: str = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Récupère les derniers rapports de veille."""
        if not supabase_client._initialized:
            return []
        
        try:
            query = supabase_client.client.table('ai_watch_reports').select('*')
            
            if agent_name:
                query = query.eq('agent_name', agent_name)
            if report_type:
                query = query.eq('report_type', report_type)
            
            response = query.order('created_at', desc=True).limit(limit).execute()
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Erreur get_latest_reports: {e}")
            return []
    
    def get_active_opportunities(self, agent_name: str = None) -> List[Dict]:
        """Récupère les opportunités actives."""
        if not supabase_client._initialized:
            return []
        
        try:
            query = supabase_client.client.table('watch_opportunities').select('*, agents(name)')
            query = query.eq('status', 'pending')
            
            if agent_name:
                query = query.eq('agents.name', agent_name)
            
            response = query.order('confidence', desc=True).execute()
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Erreur get_active_opportunities: {e}")
            return []


# Instance globale
watch_service = AIWatchService()

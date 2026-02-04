"""
Agent GPT - Le Stratège Patient.
Analyse fondamentale + actualités pour des positions rentables.
"""
import json
from typing import Optional, Dict, Any

from .base_agent import BaseAgent
from ..core.config import settings


OPENAI_PERSONALITY = """
Tu es GPT, le STRATÈGE VISIONNAIRE. Ton UNIQUE OBJECTIF est de GAGNER UN MAXIMUM D'ARGENT.

## TA MISSION ABSOLUE
🎯 FAIRE DU PROFIT avec une VISION SUPÉRIEURE du marché.

## TON STYLE UNIQUE
- Tu penses comme un GESTIONNAIRE DE HEDGE FUND
- Tu vois les GRANDES TENDANCES avant les autres
- Tu comprends les INTERCONNEXIONS entre marchés, secteurs, et économie
- Tu combines PATIENCE stratégique et ACTION décisive

## 🧠 TA MÉTHODE: PENSER EN 3D

### Dimension 1: MACRO (la forêt)
- Où en est le cycle économique? (expansion, peak, contraction, recovery)
- Politique monétaire de la Fed: hawkish ou dovish?
- Inflation, chômage, croissance: quelles tendances?
- Géopolitique: risques et opportunités?
- Flux de capitaux: vers quels actifs?

### Dimension 2: SECTORIELLE (les arbres)
- Quels secteurs bénéficient du contexte macro?
- Rotation sectorielle en cours?
- Comparer les valorisations relatives
- Identifier les leaders vs les retardataires

### Dimension 3: INDIVIDUELLE (les feuilles)
- Cette entreprise est-elle le MEILLEUR choix dans son secteur?
- Avantages compétitifs durables?
- Management quality?
- Catalysts à venir?

## 📰 ANALYSE DES NEWS: LE POURQUOI DU COMMENT
Pour chaque news, construis une CHAÎNE DE CAUSALITÉ:
1. Fait initial → 
2. Impact direct → 
3. Effets secondaires → 
4. Qui gagne/perd vraiment?
5. Le marché a-t-il compris tous les effets?

Exemple: "Intel annonce une nouvelle usine en Arizona"
- Impact direct: Intel+ (capacité)
- Effet 2: Équipementiers semi-conducteurs+ (commandes)
- Effet 3: Constructeurs locaux+ (infrastructure)
- Effet 4: Concurrents TSMC? (perte de parts futures)

## 💰 GESTION DE PORTEFEUILLE SOPHISTIQUÉE

### Allocation du Capital
- 50% Core positions (convictions fortes, holding 1-4 semaines)
- 30% Opportunistic (trades court terme sur catalysts)
- 20% Cash (toujours prêt pour les opportunités)

### Réinvestissement Intelligent
- Profits partiels à +7%: réinvestir 50% dans nouvelles opportunités
- Profits totaux à +15%: 30% en réserve, 70% réinvesti
- Compound les gains: les gagnants financent les nouveaux trades

### Pyramiding (renforcer les gagnants)
- Position initiale: 1% du capital
- Si +3%: ajouter 0.5%
- Si +7%: ajouter encore 0.5%
- Jamais plus de 3% total par position

## 🎯 CRITÈRES DE SÉLECTION STRICTS
1. L'opportunité est-elle ASYMÉTRIQUE? (potentiel gain >> risque)
2. Ai-je un EDGE informationnel? (je comprends mieux que le consensus)
3. Le TIMING est-il bon? (catalyst dans les 2 semaines)
4. La LIQUIDITÉ est-elle suffisante?
5. Comment cette position DIVERSIFIE-t-elle mon portefeuille?

## 🚫 RED FLAGS (ne jamais ignorer)
- Insider selling massif
- Comptabilité douteuse
- Dette excessive vs peers
- Dépendance à un seul client/produit
- Management qui change souvent

## TA PHILOSOPHIE
"Je ne cherche pas à avoir raison souvent, je cherche à avoir raison GROS.
Une seule position bien dimensionnée sur une conviction forte vaut mieux que 
dix petits paris sans conviction. Je comprends le POURQUOI de chaque mouvement,
et c'est ce qui me donne l'avantage."

## QUESTIONS AVANT CHAQUE TRADE
1. Quelle est ma THÈSE en une phrase?
2. Qu'est-ce qui INVALIDERAIT ma thèse?
3. Quel est le RATIO risque/récompense?
4. Pourquoi MAINTENANT?
5. Cette position AMÉLIORE-t-elle mon portefeuille global?
"""


class OpenAIAgent(BaseAgent):
    """
    Agent OpenAI/GPT - Investisseur long terme.
    """
    
    def __init__(self, initial_capital: float = None):
        super().__init__(
            name="GPT",
            model=settings.openai_model,
            personality=OPENAI_PERSONALITY,
            initial_capital=initial_capital,
        )
    
    def _build_market_context(
        self,
        market_data: Dict[str, Any],
        news: Optional[str] = None,
    ) -> str:
        """
        Construit le contexte de marché pour GPT.
        Met l'accent sur les fondamentaux et le long terme.
        """
        context_parts = []
        
        # Vision macro
        context_parts.append("## ANALYSE MACRO")
        context_parts.append("Considère:")
        context_parts.append("- La tendance générale du marché")
        context_parts.append("- Les taux d'intérêt et politique Fed")
        context_parts.append("- Le sentiment général des investisseurs")
        
        # Actions à analyser
        if "fundamental_data" in market_data:
            context_parts.append("\n## DONNÉES FONDAMENTALES")
            for symbol, data in market_data["fundamental_data"].items():
                context_parts.append(f"\n### {symbol}")
                if "metrics" in data:
                    m = data["metrics"]
                    if "pe_ratio" in m:
                        context_parts.append(f"  - P/E Ratio: {m['pe_ratio']:.2f}")
                    if "market_cap" in m:
                        context_parts.append(f"  - Market Cap: ${m['market_cap']:,.0f}")
                    if "revenue_growth" in m:
                        context_parts.append(f"  - Revenue Growth: {m['revenue_growth']:.1f}%")
        
        # Top Movers (pour info, pas pour suivre)
        if "movers" in market_data:
            movers = market_data["movers"]
            context_parts.append("\n## MOVERS DU JOUR (info seulement, ne pas FOMO)")
            
            if movers.get("gainers"):
                top3 = movers["gainers"][:3]
                context_parts.append("Top gainers: " + ", ".join(
                    f"{g['symbol']} (+{g['change_pct']:.1f}%)" for g in top3
                ))
            
            if movers.get("losers"):
                top3 = movers["losers"][:3]
                context_parts.append("Top losers: " + ", ".join(
                    f"{l['symbol']} ({l['change_pct']:.1f}%)" for l in top3
                ))
        
        # Actualités (important pour les fondamentaux)
        if news:
            context_parts.append(f"\n## ACTUALITÉS IMPORTANTES\n{news}")
        
        # Compte
        if "account" in market_data:
            account = market_data["account"]
            context_parts.append(f"\n## COMPTE")
            context_parts.append(f"- Cash disponible: ${account.get('cash', 0):.2f}")
            context_parts.append(f"- Valeur portfolio: ${account.get('portfolio_value', 0):.2f}")
        
        # Positions (focus sur le long terme)
        if "positions" in market_data and market_data["positions"]:
            context_parts.append("\n## TES POSITIONS LONG TERME")
            context_parts.append("(Ne vends que si le fondamental a changé)")
            for pos in market_data["positions"]:
                pnl = pos.get('unrealized_pl', 0)
                context_parts.append(
                    f"- {pos['symbol']}: {pos['qty']} actions "
                    f"(P&L: ${pnl:+.2f})"
                )
        
        # Rappel de discipline
        context_parts.append("\n## RAPPEL")
        context_parts.append("- Trades cette semaine: " + str(
            sum(1 for t in self.history[-20:] 
                if t.decision in ["BUY", "SELL"])
        ))
        context_parts.append("- Objectif: MAX 2-3 trades/semaine")
        context_parts.append("- Chaque trade = $1 de frais")
        
        return "\n".join(context_parts)

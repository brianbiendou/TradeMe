"""
Agent Grok - Le Chasseur de Profit.
Analyse les actualités, prend des risques, cherche le gain maximum.
"""
import json
from typing import Optional, Dict, Any

from .base_agent import BaseAgent
from ..core.config import settings


GROK_PERSONALITY = """
Tu es GROK, un trader AGRESSIF mais INTELLIGENT dont l'UNIQUE OBJECTIF est de GAGNER UN MAXIMUM D'ARGENT.

## TA MISSION ABSOLUE
🎯 FAIRE DU PROFIT. Être le MEILLEUR trader de l'équipe.

## TON STYLE UNIQUE
- Tu prends des RISQUES CALCULÉS pour des gains ÉLEVÉS
- Tu analyses TOUTES les actualités pour trouver des pépites AVANT les autres
- Tu n'as AUCUNE restriction de secteur - tu vas où est l'argent
- Tu penses "CONTRARIAN" - quand tout le monde vend dans la panique, tu cherches l'opportunité
- Tu es RAPIDE mais pas IMPULSIF

## 🔍 DIVERSIFICATION OBLIGATOIRE
- NE JAMAIS mettre plus de 20% du capital dans un seul secteur
- Explorer des secteurs DIFFÉRENTS à chaque analyse (tech, santé, énergie, finance, consommation...)
- Si tu as déjà une position tech, cherche ailleurs!
- VARIER les types de trades: momentum, valeur, événementiel

## 📊 ANALYSE MULTI-DIMENSIONNELLE
1. **NEWS**: Lis CHAQUE actualité et pose-toi ces questions:
   - Qui bénéficie? Qui perd?
   - Le marché a-t-il déjà réagi?
   - Y a-t-il des effets de second ordre? (ex: hausse pétrole → quel impact sur les transporteurs?)

2. **CORRÉLATIONS**: 
   - Si une action monte, quels sont ses concurrents/partenaires?
   - Quel est l'impact sur la supply chain?
   - Y a-t-il des ETFs sectoriels à considérer?

3. **TIMING**:
   - Pre-market et after-hours sont souvent sous-exploités
   - Les réactions excessives créent des opportunités

## CE QUI TE FAIT ACHETER
- Actualité positive surprise (earnings beat, FDA approval, contrat majeur)
- Rumeur de rachat/fusion VÉRIFIABLE
- Panique excessive créant une opportunité contrarian
- Short squeeze setup avec catalyst
- Secteur en rotation entrante

## 💰 GESTION DU CAPITAL
- Réinvestis 70% des gains, garde 30% en réserve pour les opportunités
- Augmente les positions gagnantes (pyramiding)
- Coupe vite les perdants (-5% max)
- Prends des profits partiels à +5%, laisse courir le reste

## CE QUI TE FAIT VENDRE
- Prise de profit partielle sur +5%, total sur +10%
- Actualité négative MAJEURE sur une position
- Thèse d'investissement invalidée
- Meilleure opportunité ailleurs (rotation)

## TA PHILOSOPHIE
"L'argent n'attend pas, mais je ne suis pas aveugle. Je cherche les opportunités que les autres 
ne voient pas encore. Je comprends le POURQUOI avant d'agir. Quand je vois une asymétrie 
risque/récompense en ma faveur, je fonce."

## 🎯 QUESTIONS À TE POSER AVANT CHAQUE TRADE
1. Pourquoi CETTE action et pas une autre?
2. Quel est le catalyst précis?
3. Quel est mon objectif de prix?
4. Où est mon stop-loss?
5. Est-ce que je diversifie ou je concentre trop?
"""


class GrokAgent(BaseAgent):
    """
    Agent Grok - Sniper contrarian spécialisé biotech/pharma.
    """
    
    def __init__(self, initial_capital: float = None):
        super().__init__(
            name="Grok",
            model=settings.grok_model,
            personality=GROK_PERSONALITY,
            initial_capital=initial_capital,
        )
    
    def _build_market_context(
        self,
        market_data: Dict[str, Any],
        news: Optional[str] = None,
    ) -> str:
        """
        Construit le contexte de marché pour Grok.
        Met l'accent sur les biotech, les rumeurs, et les movers.
        """
        context_parts = []
        
        # Top Movers
        if "movers" in market_data:
            movers = market_data["movers"]
            context_parts.append("## TOP MOVERS (cherche les opportunités cachées)")
            
            if movers.get("gainers"):
                context_parts.append("### 📈 Top Gainers")
                for g in movers["gainers"][:5]:
                    vol_str = f", vol: {g['volume']:,}" if 'volume' in g else ""
                    context_parts.append(
                        f"- {g['symbol']}: +{g['change_pct']:.2f}% "
                        f"(${g['price']:.2f}{vol_str})"
                    )
            
            if movers.get("losers"):
                context_parts.append("### 📉 Top Losers (opportunité contrarian?)")
                for l in movers["losers"][:5]:
                    vol_str = f", vol: {l['volume']:,}" if 'volume' in l else ""
                    context_parts.append(
                        f"- {l['symbol']}: {l['change_pct']:.2f}% "
                        f"(${l['price']:.2f}{vol_str})"
                    )
        
        # Secteurs biotech/pharma (focus de Grok)
        context_parts.append("\n## FOCUS BIOTECH/PHARMA")
        context_parts.append("Cherche les actions avec:")
        context_parts.append("- Annonces FDA imminentes")
        context_parts.append("- Résultats d'essais cliniques")
        context_parts.append("- Rumeurs d'acquisitions")
        context_parts.append("- Actions sous-évaluées après correction")
        
        # News et rumeurs
        if news:
            context_parts.append(f"\n## ACTUALITÉS & RUMEURS\n{news}")
        
        # Compte
        if "account" in market_data:
            account = market_data["account"]
            context_parts.append(f"\n## TON COMPTE ALPACA")
            context_parts.append(f"- Cash disponible: ${account.get('cash', 0):.2f}")
            context_parts.append(f"- Portfolio: ${account.get('portfolio_value', 0):.2f}")
            context_parts.append(f"- Buying power: ${account.get('buying_power', 0):.2f}")
        
        # Positions actuelles
        if "positions" in market_data and market_data["positions"]:
            context_parts.append("\n## TES POSITIONS")
            for pos in market_data["positions"]:
                pnl = pos.get('unrealized_pl', 0)
                pnl_sign = "+" if pnl >= 0 else ""
                context_parts.append(
                    f"- {pos['symbol']}: {pos['qty']} actions @ ${pos['avg_entry_price']:.2f} "
                    f"(actuel: ${pos['current_price']:.2f}, P&L: {pnl_sign}${pnl:.2f})"
                )
        
        return "\n".join(context_parts)

"""
Agent DeepSeek - L'Analyste Multi-Sources.
Croise les informations techniques et fondamentales pour maximiser les profits.
"""
import json
from typing import Optional, Dict, Any

from .base_agent import BaseAgent
from ..core.config import settings


DEEPSEEK_PERSONALITY = """
Tu es DEEPSEEK, le DÉTECTIVE du marché. Ton UNIQUE OBJECTIF est de GAGNER UN MAXIMUM D'ARGENT.

## TA MISSION ABSOLUE
🎯 FAIRE DU PROFIT en COMPRENANT ce que les autres ne comprennent pas.

## TON STYLE UNIQUE
- Tu es le SHERLOCK HOLMES du trading
- Tu CREUSES chaque information pour trouver la vérité cachée
- Tu CROISES systématiquement technique + fondamental + actualités + sentiment
- Tu cherches les INCOHÉRENCES qui révèlent des opportunités

## 🔍 TA MÉTHODE D'INVESTIGATION
### Étape 1: COMPRENDRE LE CONTEXTE
- Que se passe-t-il dans l'économie globale?
- Quels secteurs sont en rotation?
- Y a-t-il des événements macro importants (Fed, inflation, géopolitique)?

### Étape 2: ANALYSER LES NEWS EN PROFONDEUR
Pour CHAQUE news importante, demande-toi:
- QUI profite vraiment? (pas juste l'évidence)
- Y a-t-il des EFFETS DE SECOND ORDRE? 
  (ex: pénurie de puces → Apple souffre, mais AUSSI les fournisseurs de packaging)
- Le marché a-t-il SUR-réagi ou SOUS-réagi?
- Quelle est la FIABILITÉ de la source?

### Étape 3: CROISER LES DONNÉES
- Prix en hausse + Volume en hausse + News positive = SIGNAL FORT
- Prix en hausse + Volume faible + Pas de news = MÉFIANCE
- Prix en baisse + News positive = OPPORTUNITÉ POTENTIELLE (creuser pourquoi)

### Étape 4: VÉRIFIER LES CORRÉLATIONS
- Comment se comportent les CONCURRENTS?
- Les FOURNISSEURS et CLIENTS sont-ils impactés?
- Y a-t-il des INDICES sectoriels qui confirment?

## 📊 INDICATEURS QUE TU SURVEILLES
- RSI: <30 = survente potentielle, >70 = surachat
- MACD: croisements et divergences
- Volume: confirmation du mouvement
- Support/Résistance: zones clés
- Fear & Greed Index: sentiment extrême = opportunité contrarian

## 🎯 CRITÈRES D'ENTRÉE (besoin de 3+ signaux alignés)
1. ✅ News avec impact clair
2. ✅ Technique favorable (tendance, support, indicateurs)
3. ✅ Volume confirmant
4. ✅ Sentiment cohérent
5. ✅ Pas de red flags (insider selling, dette excessive, etc.)

## 💰 GESTION DU CAPITAL INTELLIGENTE
- Réserve 20% en cash pour les opportunités
- Position sizing basé sur la conviction (1-3% du capital par trade)
- Augmente les gagnants par paliers
- Objectif +5% à +15% selon la qualité du setup
- Stop-loss strict à -3%

## 🔄 DIVERSIFICATION STRATÉGIQUE
- Maximum 2 positions dans le même secteur
- Cherche des actifs DÉCORRÉLÉS
- Équilibre entre trades momentum et value

## TA PHILOSOPHIE
"Je ne trade pas des actions, je trade des HISTOIRES que je comprends parfaitement.
Chaque trade est une hypothèse que j'ai VÉRIFIÉE sous plusieurs angles.
Quand les pièces du puzzle s'alignent, j'agis avec conviction."

## 🚫 TU N'AGIS PAS SI:
- Tu ne comprends pas pourquoi le prix bouge
- Les signaux sont contradictoires
- Tu as déjà 3 positions ouvertes dans le même secteur
"""


class DeepSeekAgent(BaseAgent):
    """
    Agent DeepSeek - Analyste technique.
    """
    
    def __init__(self, initial_capital: float = None):
        super().__init__(
            name="DeepSeek",
            model=settings.deepseek_model,
            personality=DEEPSEEK_PERSONALITY,
            initial_capital=initial_capital,
        )
    
    def _build_market_context(
        self,
        market_data: Dict[str, Any],
        news: Optional[str] = None,
    ) -> str:
        """
        Construit le contexte de marché pour DeepSeek.
        Met l'accent sur les données techniques et les patterns.
        """
        context_parts = []
        
        # Données techniques par symbole
        if "technical_data" in market_data:
            context_parts.append("## ANALYSE TECHNIQUE")
            for symbol, data in market_data["technical_data"].items():
                context_parts.append(f"\n### {symbol}")
                
                if "bars" in data:
                    bars = data["bars"][-5:]  # 5 dernières barres
                    context_parts.append("Dernières bougies (OHLCV):")
                    for bar in bars:
                        context_parts.append(
                            f"  {bar['timestamp'][:10]}: "
                            f"O:{bar['open']:.2f} H:{bar['high']:.2f} "
                            f"L:{bar['low']:.2f} C:{bar['close']:.2f} "
                            f"V:{bar['volume']:,}"
                        )
                
                if "indicators" in data:
                    ind = data["indicators"]
                    context_parts.append("Indicateurs:")
                    if "rsi" in ind:
                        rsi = ind["rsi"]
                        status = "SURACHAT" if rsi > 70 else "SURVENTE" if rsi < 30 else "NEUTRE"
                        context_parts.append(f"  - RSI(14): {rsi:.1f} ({status})")
                    if "sma_20" in ind:
                        context_parts.append(f"  - SMA20: ${ind['sma_20']:.2f}")
                    if "sma_50" in ind:
                        context_parts.append(f"  - SMA50: ${ind['sma_50']:.2f}")
        
        # Top Movers
        if "movers" in market_data:
            movers = market_data["movers"]
            context_parts.append("\n## MOVERS (analyse le momentum)")
            
            if movers.get("gainers"):
                context_parts.append("### Momentum haussier")
                for g in movers["gainers"][:5]:
                    vol_str = f" (vol: {g['volume']:,})" if 'volume' in g else ""
                    context_parts.append(
                        f"- {g['symbol']}: +{g['change_pct']:.2f}%{vol_str}"
                    )
            
            if movers.get("losers"):
                context_parts.append("### Momentum baissier")
                for l in movers["losers"][:5]:
                    vol_str = f" (vol: {l['volume']:,})" if 'volume' in l else ""
                    context_parts.append(
                        f"- {l['symbol']}: {l['change_pct']:.2f}%{vol_str}"
                    )
        
        # Compte
        if "account" in market_data:
            account = market_data["account"]
            context_parts.append(f"\n## COMPTE")
            context_parts.append(f"- Cash: ${account.get('cash', 0):.2f}")
            context_parts.append(f"- Portfolio: ${account.get('portfolio_value', 0):.2f}")
        
        # Positions
        if "positions" in market_data and market_data["positions"]:
            context_parts.append("\n## POSITIONS (analyse le P&L)")
            for pos in market_data["positions"]:
                pnl_pct = pos.get('unrealized_plpc', 0) * 100
                context_parts.append(
                    f"- {pos['symbol']}: {pos['qty']} @ ${pos['avg_entry_price']:.2f} "
                    f"→ ${pos['current_price']:.2f} ({pnl_pct:+.2f}%)"
                )
        
        # News (moins important pour l'analyse technique)
        if news:
            context_parts.append(f"\n## ACTUALITÉS (contexte)\n{news[:500]}...")
        
        return "\n".join(context_parts)

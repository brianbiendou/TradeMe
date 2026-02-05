"""
Signal Combiner - Combine intelligemment tous les signaux pour des décisions optimales.
Intègre: Smart Money, Memory RAG, Sentiment, Technique.

LOGIQUE DE COMBINAISON:
1. Signal de base (IA): confiance 0-100
2. Smart Money boost/malus: +/-30% max
3. Memory RAG boost/malus: +/-20% max
4. Market Regime filter: peut bloquer entièrement

RÈGLES:
- Score final < 50% → SKIP le trade
- Score final 50-70% → Réduire la taille
- Score final > 85% → Trade fort
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Force du signal combiné."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WEAK_BUY = "WEAK_BUY"
    NEUTRAL = "NEUTRAL"
    WEAK_SELL = "WEAK_SELL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    BLOCKED = "BLOCKED"


@dataclass
class CombinedSignal:
    """Résultat de la combinaison des signaux."""
    original_decision: str  # BUY, SELL, HOLD
    original_confidence: int
    final_confidence: int
    signal_strength: SignalStrength
    should_proceed: bool
    sizing_multiplier: float  # 0.5 à 1.5
    
    # Détails des composants
    smart_money_score: float  # -1 à +1
    memory_score: float  # -1 à +1
    market_regime_ok: bool
    
    # Raisons
    adjustments: List[str]
    warnings: List[str]
    reasoning: str


class SignalCombiner:
    """
    Combine tous les signaux disponibles pour optimiser les décisions de trading.
    """
    
    def __init__(self):
        self._initialized = False
        
        # === POIDS DES COMPOSANTS ===
        self.smart_money_weight = 0.30  # 30% du score
        self.memory_weight = 0.20  # 20% du score
        self.ai_base_weight = 0.50  # 50% du score (la décision de l'IA)
        
        # === SEUILS ===
        self.min_confidence_to_trade = 50  # Score minimum pour trader
        self.high_confidence_threshold = 85  # Score pour trade "fort"
        self.weak_confidence_threshold = 65  # En dessous = trade faible
        
        # === MULTIPLICATEURS SMART MONEY ===
        self.dark_pool_bullish_threshold = 0.55  # >55% dark pool = bullish
        self.dark_pool_bearish_threshold = 0.45  # <45% = bearish
        self.put_call_bullish_threshold = 0.7  # P/C < 0.7 = bullish
        self.put_call_bearish_threshold = 1.3  # P/C > 1.3 = bearish
        
        # === FILTRES MARKET REGIME ===
        self.vix_extreme_threshold = 40  # VIX > 40 = bloquer les achats
        self.fear_extreme_low = 20  # Fear < 20 = trop de peur
        self.greed_extreme_high = 80  # Greed > 80 = trop de cupidité
    
    def initialize(self) -> bool:
        """Initialise le combiner."""
        self._initialized = True
        logger.info("✅ Signal Combiner initialisé")
        return True
    
    def combine_signals(
        self,
        decision: str,
        confidence: int,
        symbol: str,
        smart_money_data: Optional[Dict[str, Any]] = None,
        memory_context: Optional[Dict[str, Any]] = None,
        agent_stats: Optional[Dict[str, Any]] = None,
    ) -> CombinedSignal:
        """
        Combine tous les signaux pour produire une décision finale.
        
        Args:
            decision: Décision de l'IA (BUY, SELL, HOLD)
            confidence: Confiance de l'IA (0-100)
            symbol: Symbole tradé
            smart_money_data: Données Smart Money
            memory_context: Contexte mémoire RAG
            agent_stats: Statistiques de l'agent
        
        Returns:
            CombinedSignal avec la décision finale ajustée
        """
        adjustments = []
        warnings = []
        
        # === 1. SCORE DE BASE (IA) ===
        base_score = confidence / 100.0  # 0-1
        
        # === 2. SCORE SMART MONEY ===
        smart_score = 0.0
        if smart_money_data:
            smart_score = self._calculate_smart_money_score(
                decision, smart_money_data, adjustments, warnings
            )
        
        # === 3. SCORE MÉMOIRE ===
        memory_score = 0.0
        if memory_context:
            memory_score = self._calculate_memory_score(
                decision, symbol, memory_context, adjustments, warnings
            )
        
        # === 4. CHECK MARKET REGIME ===
        market_ok = True
        if smart_money_data:
            market_ok, regime_warning = self._check_market_regime(
                decision, smart_money_data
            )
            if not market_ok:
                warnings.append(regime_warning)
        
        # === 5. COMBINER LES SCORES ===
        final_score = (
            base_score * self.ai_base_weight +
            (smart_score + 1) / 2 * self.smart_money_weight +  # Normalise -1/+1 vers 0/1
            (memory_score + 1) / 2 * self.memory_weight
        )
        
        final_confidence = int(final_score * 100)
        
        # === 6. DÉTERMINER LA FORCE DU SIGNAL ===
        signal_strength = self._determine_signal_strength(
            decision, final_confidence, market_ok
        )
        
        # === 7. CALCULER LE MULTIPLICATEUR DE SIZING ===
        sizing_multiplier = self._calculate_sizing_multiplier(
            final_confidence, smart_score, memory_score
        )
        
        # === 8. DÉCISION FINALE ===
        should_proceed = (
            market_ok and 
            final_confidence >= self.min_confidence_to_trade and
            signal_strength not in [SignalStrength.BLOCKED, SignalStrength.NEUTRAL]
        )
        
        # Construire le raisonnement
        reasoning = self._build_reasoning(
            decision, confidence, final_confidence,
            smart_score, memory_score, market_ok,
            adjustments, warnings
        )
        
        return CombinedSignal(
            original_decision=decision,
            original_confidence=confidence,
            final_confidence=final_confidence,
            signal_strength=signal_strength,
            should_proceed=should_proceed,
            sizing_multiplier=sizing_multiplier,
            smart_money_score=smart_score,
            memory_score=memory_score,
            market_regime_ok=market_ok,
            adjustments=adjustments,
            warnings=warnings,
            reasoning=reasoning,
        )
    
    def _calculate_smart_money_score(
        self,
        decision: str,
        data: Dict[str, Any],
        adjustments: List[str],
        warnings: List[str],
    ) -> float:
        """
        Calcule le score Smart Money (-1 à +1).
        +1 = confirme fortement la décision
        -1 = contredit fortement la décision
        """
        score = 0.0
        is_bullish_decision = decision == "BUY"
        
        # === VIX ===
        vix = data.get("vix", {}).get("vix", 20)
        if vix < 15:
            vix_signal = 0.3  # VIX bas = bullish
        elif vix > 30:
            vix_signal = -0.3  # VIX haut = bearish
        else:
            vix_signal = 0
        
        # Ajuster selon la décision
        if is_bullish_decision:
            score += vix_signal
            if vix_signal != 0:
                adjustments.append(f"VIX={vix}: {'+' if vix_signal > 0 else '-'}{abs(vix_signal)*100:.0f}%")
        else:
            score -= vix_signal  # Inverse pour SELL
        
        # === FEAR & GREED ===
        fng = data.get("fear_greed", {}).get("fear_greed_index", 50)
        if fng < 25:
            fng_signal = 0.2  # Peur extrême = opportunité d'achat
        elif fng > 75:
            fng_signal = -0.2  # Cupidité extrême = attention
        else:
            fng_signal = 0
        
        if is_bullish_decision:
            score += fng_signal
            if fng_signal != 0:
                adjustments.append(f"Fear/Greed={fng}: {'+' if fng_signal > 0 else '-'}{abs(fng_signal)*100:.0f}%")
        
        # === OPTIONS PUT/CALL ===
        options = data.get("options", {})
        if options:
            pc_ratio = options.get("put_call_ratio", 1.0)
            if pc_ratio < self.put_call_bullish_threshold:
                opt_signal = 0.25  # Bullish options flow
            elif pc_ratio > self.put_call_bearish_threshold:
                opt_signal = -0.25  # Bearish options flow
            else:
                opt_signal = 0
            
            if is_bullish_decision:
                score += opt_signal
                if opt_signal != 0:
                    sentiment = "BULLISH" if opt_signal > 0 else "BEARISH"
                    adjustments.append(f"Options P/C={pc_ratio:.2f} ({sentiment})")
        
        # === DARK POOL ===
        dark_pool = data.get("dark_pool", {})
        if dark_pool:
            dp_ratio = dark_pool.get("dark_pool_ratio", 0.5)
            if dp_ratio > self.dark_pool_bullish_threshold:
                dp_signal = 0.2  # Institutions accumulent
            elif dp_ratio < self.dark_pool_bearish_threshold:
                dp_signal = -0.2  # Institutions vendent
            else:
                dp_signal = 0
            
            if is_bullish_decision:
                score += dp_signal
                if dp_signal != 0:
                    direction = "ACCUMULATION" if dp_signal > 0 else "DISTRIBUTION"
                    adjustments.append(f"Dark Pool: {direction}")
        
        # === INSIDER TRADING ===
        insiders = data.get("insiders", {})
        if insiders:
            net_insider = insiders.get("net_insider_sentiment", 0)
            if net_insider > 0.5:
                ins_signal = 0.3  # Insiders achètent = très bullish
            elif net_insider < -0.5:
                ins_signal = -0.3  # Insiders vendent = bearish
                warnings.append(f"⚠️ INSIDERS VENDENT {insiders.get('symbol', '')}")
            else:
                ins_signal = 0
            
            if is_bullish_decision:
                score += ins_signal
                if ins_signal != 0:
                    direction = "BUYING" if ins_signal > 0 else "SELLING"
                    adjustments.append(f"Insiders: {direction}")
        
        return max(-1, min(1, score))  # Borné -1 à +1
    
    def _calculate_memory_score(
        self,
        decision: str,
        symbol: str,
        memory: Dict[str, Any],
        adjustments: List[str],
        warnings: List[str],
    ) -> float:
        """
        Calcule le score basé sur la mémoire passée (-1 à +1).
        """
        score = 0.0
        
        # Win rate historique sur ce symbole
        symbol_stats = memory.get("symbol_stats", {})
        if symbol_stats:
            win_rate = symbol_stats.get("win_rate", 0.5)
            if win_rate > 0.7:
                score += 0.3
                adjustments.append(f"Historique {symbol}: Win Rate {win_rate*100:.0f}% ✅")
            elif win_rate < 0.4:
                score -= 0.3
                warnings.append(f"⚠️ Historique {symbol} mauvais: Win Rate {win_rate*100:.0f}%")
        
        # Win rate par niveau de confiance
        confidence_stats = memory.get("confidence_stats", {})
        if confidence_stats:
            relevant_bucket = confidence_stats.get("current_bucket", {})
            if relevant_bucket:
                bucket_wr = relevant_bucket.get("win_rate", 0.5)
                if bucket_wr > 0.65:
                    score += 0.2
                elif bucket_wr < 0.45:
                    score -= 0.2
                    warnings.append(f"⚠️ Historique à ce niveau de confiance: seulement {bucket_wr*100:.0f}% win rate")
        
        # Leçons apprises
        lessons = memory.get("lessons", [])
        negative_lessons = [l for l in lessons if "PERTE" in l or "❌" in l]
        if len(negative_lessons) >= 2:
            score -= 0.2
            warnings.append(f"⚠️ {len(negative_lessons)} trades perdants récents sur ce pattern")
        
        return max(-1, min(1, score))
    
    def _check_market_regime(
        self,
        decision: str,
        data: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Vérifie si le régime de marché permet le trade.
        Retourne (ok, warning_message).
        """
        vix = data.get("vix", {}).get("vix", 20)
        fng = data.get("fear_greed", {}).get("fear_greed_index", 50)
        
        # VIX extrême bloque les achats
        if decision == "BUY" and vix > self.vix_extreme_threshold:
            return False, f"🚫 VIX EXTRÊME ({vix}) - Achats bloqués"
        
        # Peur extrême + VIX haut = danger
        if fng < self.fear_extreme_low and vix > 30:
            return False, f"🚫 PANIQUE MARCHÉ (Fear={fng}, VIX={vix}) - Trading risqué"
        
        # Cupidité extrême = attention aux achats
        if decision == "BUY" and fng > self.greed_extreme_high:
            # Ne pas bloquer mais avertir
            return True, f"⚠️ CUPIDITÉ EXTRÊME ({fng}) - Marché potentiellement suracheté"
        
        return True, ""
    
    def _determine_signal_strength(
        self,
        decision: str,
        confidence: int,
        market_ok: bool,
    ) -> SignalStrength:
        """Détermine la force du signal final."""
        if not market_ok:
            return SignalStrength.BLOCKED
        
        if decision == "HOLD":
            return SignalStrength.NEUTRAL
        
        if decision == "BUY":
            if confidence >= self.high_confidence_threshold:
                return SignalStrength.STRONG_BUY
            elif confidence >= self.weak_confidence_threshold:
                return SignalStrength.BUY
            elif confidence >= self.min_confidence_to_trade:
                return SignalStrength.WEAK_BUY
            else:
                return SignalStrength.NEUTRAL
        
        if decision == "SELL":
            if confidence >= self.high_confidence_threshold:
                return SignalStrength.STRONG_SELL
            elif confidence >= self.weak_confidence_threshold:
                return SignalStrength.SELL
            elif confidence >= self.min_confidence_to_trade:
                return SignalStrength.WEAK_SELL
            else:
                return SignalStrength.NEUTRAL
        
        return SignalStrength.NEUTRAL
    
    def _calculate_sizing_multiplier(
        self,
        confidence: int,
        smart_score: float,
        memory_score: float,
    ) -> float:
        """
        Calcule le multiplicateur pour le position sizing.
        0.5 = petite position, 1.5 = grosse position.
        """
        base = 1.0
        
        # Ajustement confiance
        if confidence >= 90:
            base *= 1.3
        elif confidence >= 80:
            base *= 1.1
        elif confidence < 60:
            base *= 0.7
        
        # Ajustement Smart Money
        if smart_score > 0.5:
            base *= 1.2
        elif smart_score < -0.5:
            base *= 0.6
        
        # Ajustement Memory
        if memory_score > 0.5:
            base *= 1.1
        elif memory_score < -0.5:
            base *= 0.8
        
        return max(0.5, min(1.5, base))
    
    def _build_reasoning(
        self,
        decision: str,
        original_conf: int,
        final_conf: int,
        smart_score: float,
        memory_score: float,
        market_ok: bool,
        adjustments: List[str],
        warnings: List[str],
    ) -> str:
        """Construit l'explication de la combinaison."""
        
        parts = [
            f"📊 **Signal Combiné: {decision}**",
            f"",
            f"**Confiance:**",
            f"- IA originale: {original_conf}%",
            f"- Score final: {final_conf}%",
            f"- Variation: {final_conf - original_conf:+d}%",
            f"",
            f"**Composants:**",
            f"- Smart Money: {smart_score:+.2f} ({'+' if smart_score > 0 else '-'})",
            f"- Memory: {memory_score:+.2f} ({'+' if memory_score > 0 else '-'})",
            f"- Market OK: {'✅' if market_ok else '❌'}",
        ]
        
        if adjustments:
            parts.append("\n**Ajustements:**")
            for adj in adjustments:
                parts.append(f"  • {adj}")
        
        if warnings:
            parts.append("\n**⚠️ Avertissements:**")
            for warn in warnings:
                parts.append(f"  • {warn}")
        
        return "\n".join(parts)
    
    def format_signal_for_agent(self, combined: CombinedSignal) -> str:
        """Formate le signal combiné pour inclusion dans le prompt."""
        
        emoji = {
            SignalStrength.STRONG_BUY: "🟢🟢",
            SignalStrength.BUY: "🟢",
            SignalStrength.WEAK_BUY: "🟡",
            SignalStrength.NEUTRAL: "⚪",
            SignalStrength.WEAK_SELL: "🟡",
            SignalStrength.SELL: "🔴",
            SignalStrength.STRONG_SELL: "🔴🔴",
            SignalStrength.BLOCKED: "🚫",
        }.get(combined.signal_strength, "⚪")
        
        lines = [
            f"\n## 🎯 SIGNAL COMBINÉ",
            f"{emoji} **{combined.signal_strength.value}** - Confiance: {combined.final_confidence}%",
            f"",
            f"Décision IA: {combined.original_confidence}% → Ajusté: {combined.final_confidence}%",
            f"Sizing recommandé: x{combined.sizing_multiplier:.2f}",
        ]
        
        if combined.warnings:
            lines.append("\n**⚠️ ATTENTION:**")
            for w in combined.warnings[:3]:
                lines.append(f"  {w}")
        
        if not combined.should_proceed:
            lines.append("\n🚫 **TRADE NON RECOMMANDÉ** - Conditions non réunies")
        
        return "\n".join(lines)


# Instance globale
signal_combiner = SignalCombiner()

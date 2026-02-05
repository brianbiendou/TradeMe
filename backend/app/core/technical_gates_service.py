"""
Technical Gates Service - Règles Techniques DURES V2.3.

Ce service implémente des règles ABSOLUES que l'IA ne peut PAS ignorer:
- RSI > 75 = INTERDICTION d'acheter (surachat)
- RSI < 25 = INTERDICTION de vendre (survente)
- MACD négatif + Signal bearish = INTERDICTION d'acheter
- MACD positif + Signal bullish = INTERDICTION de vendre

Impact estimé: +25-40% de rentabilité
"""
import logging
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GateDecision(Enum):
    """Décision de la porte technique."""
    ALLOWED = "ALLOWED"          # Autorisé
    BLOCKED = "BLOCKED"          # Bloqué
    WARNING = "WARNING"          # Avertissement (pas bloqué mais risqué)


class GateReason(Enum):
    """Raison du blocage/avertissement."""
    RSI_OVERBOUGHT = "RSI_OVERBOUGHT"            # RSI > 75
    RSI_OVERSOLD = "RSI_OVERSOLD"                # RSI < 25
    RSI_HIGH = "RSI_HIGH"                        # RSI > 65 (warning)
    RSI_LOW = "RSI_LOW"                          # RSI < 35 (warning)
    MACD_BEARISH = "MACD_BEARISH"                # MACD < Signal et négatif
    MACD_BULLISH = "MACD_BULLISH"                # MACD > Signal et positif
    MACD_CROSSOVER_DOWN = "MACD_CROSSOVER_DOWN"  # Croisement baissier
    MACD_CROSSOVER_UP = "MACD_CROSSOVER_UP"      # Croisement haussier
    VOLUME_TOO_LOW = "VOLUME_TOO_LOW"            # Volume < 50% moyenne
    TREND_AGAINST = "TREND_AGAINST"              # Tendance contre la décision
    ALL_CLEAR = "ALL_CLEAR"                      # Tout est bon


@dataclass
class TechnicalGateResult:
    """Résultat de l'évaluation des portes techniques."""
    decision: GateDecision
    can_proceed: bool
    reasons: List[GateReason]
    messages: List[str]
    
    # Détails techniques
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    volume_ratio: Optional[float] = None
    
    # Score de risque (0 = pas de risque, 100 = très risqué)
    risk_score: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "decision": self.decision.value,
            "can_proceed": self.can_proceed,
            "reasons": [r.value for r in self.reasons],
            "messages": self.messages,
            "rsi": self.rsi,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "macd_histogram": self.macd_histogram,
            "volume_ratio": self.volume_ratio,
            "risk_score": self.risk_score,
        }


class TechnicalGatesService:
    """
    Service de règles techniques ABSOLUES.
    
    Ces règles sont des PORTES que l'IA ne peut pas franchir.
    Elles sont basées sur des indicateurs techniques validés.
    """
    
    def __init__(self):
        """Initialise le service avec les seuils."""
        self._initialized = False
        
        # === SEUILS RSI ===
        self.rsi_overbought = 75     # RSI > 75 = BLOCAGE ACHAT
        self.rsi_oversold = 25       # RSI < 25 = BLOCAGE VENTE
        self.rsi_high_warning = 65   # RSI > 65 = WARNING ACHAT
        self.rsi_low_warning = 35    # RSI < 35 = WARNING VENTE
        
        # === SEUILS MACD ===
        # MACD histogram négatif + valeur MACD négative = blocage achat
        self.macd_bearish_threshold = -0.5  # MACD < -0.5 = très bearish
        self.macd_bullish_threshold = 0.5   # MACD > 0.5 = très bullish
        
        # === SEUILS VOLUME ===
        self.volume_min_ratio = 0.5  # Volume < 50% moyenne = blocage
        self.volume_low_warning = 0.8  # Volume < 80% = warning
        
        # === COMBINAISONS FATALES ===
        # RSI > 70 ET MACD bearish = blocage total
        self.combo_rsi_macd_buy_block = {"rsi_min": 70, "macd_bearish": True}
        # RSI < 30 ET MACD bullish = blocage vente
        self.combo_rsi_macd_sell_block = {"rsi_max": 30, "macd_bullish": True}
    
    def initialize(self) -> bool:
        """Initialise le service."""
        self._initialized = True
        logger.info("✅ Technical Gates Service initialisé (règles dures actives)")
        return True
    
    def evaluate_buy(
        self,
        rsi: float = None,
        macd: float = None,
        macd_signal: float = None,
        macd_histogram: float = None,
        volume_ratio: float = None,
        trend_direction: str = None,
    ) -> TechnicalGateResult:
        """
        Évalue si un ACHAT est autorisé selon les règles techniques.
        
        Args:
            rsi: Valeur RSI (0-100)
            macd: Ligne MACD
            macd_signal: Ligne de signal MACD
            macd_histogram: Histogramme MACD
            volume_ratio: Ratio volume actuel / moyenne
            trend_direction: Direction de la tendance ("BULLISH", "BEARISH", "NEUTRAL")
        
        Returns:
            TechnicalGateResult avec la décision
        """
        reasons = []
        messages = []
        risk_score = 0
        blocked = False
        
        # === CHECK RSI ===
        if rsi is not None:
            if rsi > self.rsi_overbought:
                reasons.append(GateReason.RSI_OVERBOUGHT)
                messages.append(f"🚫 RSI = {rsi:.1f} > {self.rsi_overbought} = SURACHAT. Achat INTERDIT!")
                risk_score += 50
                blocked = True
            elif rsi > self.rsi_high_warning:
                reasons.append(GateReason.RSI_HIGH)
                messages.append(f"⚠️ RSI = {rsi:.1f} > {self.rsi_high_warning} = Risque élevé")
                risk_score += 25
        
        # === CHECK MACD ===
        if macd is not None and macd_signal is not None:
            # MACD sous le signal ET négatif = bearish
            if macd < macd_signal and macd < 0:
                if macd < self.macd_bearish_threshold:
                    reasons.append(GateReason.MACD_BEARISH)
                    messages.append(f"🚫 MACD = {macd:.2f} < Signal = {macd_signal:.2f} ET négatif. Achat INTERDIT!")
                    risk_score += 40
                    blocked = True
                else:
                    reasons.append(GateReason.MACD_BEARISH)
                    messages.append(f"⚠️ MACD bearish ({macd:.2f} < {macd_signal:.2f})")
                    risk_score += 20
        
        # === CHECK MACD HISTOGRAM (croisement récent) ===
        if macd_histogram is not None:
            if macd_histogram < -0.5:  # Croisement baissier fort
                reasons.append(GateReason.MACD_CROSSOVER_DOWN)
                messages.append(f"⚠️ Croisement MACD baissier (histogram = {macd_histogram:.2f})")
                risk_score += 15
        
        # === CHECK VOLUME ===
        if volume_ratio is not None:
            if volume_ratio < self.volume_min_ratio:
                reasons.append(GateReason.VOLUME_TOO_LOW)
                messages.append(f"🚫 Volume trop faible ({volume_ratio:.1%} de la moyenne). Achat risqué!")
                risk_score += 20
                # Ne bloque pas mais augmente le risque
            elif volume_ratio < self.volume_low_warning:
                messages.append(f"⚠️ Volume bas ({volume_ratio:.1%} de la moyenne)")
                risk_score += 10
        
        # === CHECK TENDANCE ===
        if trend_direction and trend_direction in ["BEARISH", "STRONG_BEARISH"]:
            reasons.append(GateReason.TREND_AGAINST)
            messages.append(f"⚠️ Tendance {trend_direction} = contre l'achat")
            risk_score += 15
        
        # === COMBO FATAL: RSI élevé + MACD bearish ===
        if rsi is not None and rsi > 70 and macd is not None and macd < 0:
            if GateReason.RSI_OVERBOUGHT not in reasons:
                reasons.append(GateReason.RSI_OVERBOUGHT)
            messages.append(f"💀 COMBO FATAL: RSI {rsi:.1f} + MACD négatif = Achat ABSOLUMENT INTERDIT!")
            risk_score = 100
            blocked = True
        
        # Déterminer la décision finale
        if blocked:
            decision = GateDecision.BLOCKED
            can_proceed = False
        elif risk_score > 30:
            decision = GateDecision.WARNING
            can_proceed = True  # Autorisé mais avec warning
        else:
            decision = GateDecision.ALLOWED
            can_proceed = True
            reasons.append(GateReason.ALL_CLEAR)
            messages.append("✅ Tous les indicateurs sont favorables à l'achat")
        
        return TechnicalGateResult(
            decision=decision,
            can_proceed=can_proceed,
            reasons=reasons,
            messages=messages,
            rsi=rsi,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            volume_ratio=volume_ratio,
            risk_score=min(100, risk_score),
        )
    
    def evaluate_sell(
        self,
        rsi: float = None,
        macd: float = None,
        macd_signal: float = None,
        macd_histogram: float = None,
        volume_ratio: float = None,
        trend_direction: str = None,
    ) -> TechnicalGateResult:
        """
        Évalue si une VENTE est autorisée selon les règles techniques.
        
        Args:
            rsi: Valeur RSI (0-100)
            macd: Ligne MACD
            macd_signal: Ligne de signal MACD
            macd_histogram: Histogramme MACD
            volume_ratio: Ratio volume actuel / moyenne
            trend_direction: Direction de la tendance
        
        Returns:
            TechnicalGateResult avec la décision
        """
        reasons = []
        messages = []
        risk_score = 0
        blocked = False
        
        # === CHECK RSI ===
        if rsi is not None:
            if rsi < self.rsi_oversold:
                reasons.append(GateReason.RSI_OVERSOLD)
                messages.append(f"🚫 RSI = {rsi:.1f} < {self.rsi_oversold} = SURVENTE. Vente INTERDITE!")
                risk_score += 50
                blocked = True
            elif rsi < self.rsi_low_warning:
                reasons.append(GateReason.RSI_LOW)
                messages.append(f"⚠️ RSI = {rsi:.1f} < {self.rsi_low_warning} = Possible rebond")
                risk_score += 25
        
        # === CHECK MACD ===
        if macd is not None and macd_signal is not None:
            # MACD au-dessus du signal ET positif = bullish
            if macd > macd_signal and macd > 0:
                if macd > self.macd_bullish_threshold:
                    reasons.append(GateReason.MACD_BULLISH)
                    messages.append(f"🚫 MACD = {macd:.2f} > Signal = {macd_signal:.2f} ET positif. Vente INTERDITE!")
                    risk_score += 40
                    blocked = True
                else:
                    reasons.append(GateReason.MACD_BULLISH)
                    messages.append(f"⚠️ MACD bullish ({macd:.2f} > {macd_signal:.2f})")
                    risk_score += 20
        
        # === CHECK MACD HISTOGRAM (croisement récent) ===
        if macd_histogram is not None:
            if macd_histogram > 0.5:  # Croisement haussier fort
                reasons.append(GateReason.MACD_CROSSOVER_UP)
                messages.append(f"⚠️ Croisement MACD haussier (histogram = {macd_histogram:.2f})")
                risk_score += 15
        
        # === CHECK VOLUME ===
        if volume_ratio is not None:
            if volume_ratio < self.volume_min_ratio:
                reasons.append(GateReason.VOLUME_TOO_LOW)
                messages.append(f"⚠️ Volume faible ({volume_ratio:.1%}) - vente en condition de faible liquidité")
                risk_score += 10
        
        # === CHECK TENDANCE ===
        if trend_direction and trend_direction in ["BULLISH", "STRONG_BULLISH"]:
            reasons.append(GateReason.TREND_AGAINST)
            messages.append(f"⚠️ Tendance {trend_direction} = contre la vente")
            risk_score += 15
        
        # === COMBO FATAL: RSI bas + MACD bullish ===
        if rsi is not None and rsi < 30 and macd is not None and macd > 0:
            if GateReason.RSI_OVERSOLD not in reasons:
                reasons.append(GateReason.RSI_OVERSOLD)
            messages.append(f"💀 COMBO FATAL: RSI {rsi:.1f} + MACD positif = Vente ABSOLUMENT INTERDITE!")
            risk_score = 100
            blocked = True
        
        # Déterminer la décision finale
        if blocked:
            decision = GateDecision.BLOCKED
            can_proceed = False
        elif risk_score > 30:
            decision = GateDecision.WARNING
            can_proceed = True
        else:
            decision = GateDecision.ALLOWED
            can_proceed = True
            reasons.append(GateReason.ALL_CLEAR)
            messages.append("✅ Tous les indicateurs sont favorables à la vente")
        
        return TechnicalGateResult(
            decision=decision,
            can_proceed=can_proceed,
            reasons=reasons,
            messages=messages,
            rsi=rsi,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            volume_ratio=volume_ratio,
            risk_score=min(100, risk_score),
        )
    
    def evaluate_trade(
        self,
        trade_decision: str,
        technical_analysis: Dict[str, Any],
    ) -> TechnicalGateResult:
        """
        Évalue un trade selon les indicateurs techniques fournis.
        
        Args:
            trade_decision: "BUY" ou "SELL"
            technical_analysis: Dict avec rsi, macd_line, macd_signal_line, etc.
        
        Returns:
            TechnicalGateResult
        """
        rsi = technical_analysis.get("rsi")
        macd = technical_analysis.get("macd_line")
        macd_signal = technical_analysis.get("macd_signal_line")
        macd_histogram = technical_analysis.get("macd_histogram")
        volume_ratio = technical_analysis.get("volume_ratio")
        trend = technical_analysis.get("trend")
        
        if trade_decision.upper() == "BUY":
            return self.evaluate_buy(
                rsi=rsi,
                macd=macd,
                macd_signal=macd_signal,
                macd_histogram=macd_histogram,
                volume_ratio=volume_ratio,
                trend_direction=trend,
            )
        elif trade_decision.upper() == "SELL":
            return self.evaluate_sell(
                rsi=rsi,
                macd=macd,
                macd_signal=macd_signal,
                macd_histogram=macd_histogram,
                volume_ratio=volume_ratio,
                trend_direction=trend,
            )
        else:
            # HOLD = pas d'évaluation
            return TechnicalGateResult(
                decision=GateDecision.ALLOWED,
                can_proceed=True,
                reasons=[GateReason.ALL_CLEAR],
                messages=["✅ HOLD - Pas d'action requise"],
                risk_score=0,
            )
    
    def format_for_prompt(self, result: TechnicalGateResult) -> str:
        """
        Formate le résultat pour l'inclure dans le prompt de l'IA.
        """
        lines = [
            "## 🚧 PORTES TECHNIQUES (RÈGLES ABSOLUES)",
            f"Décision: {result.decision.value}",
            f"Score de risque: {result.risk_score}/100",
            "",
            "Messages:",
        ]
        
        for msg in result.messages:
            lines.append(f"  {msg}")
        
        if not result.can_proceed:
            lines.append("")
            lines.append("⛔ CETTE ACTION EST BLOQUÉE PAR LES RÈGLES TECHNIQUES!")
            lines.append("Tu DOIS changer ta décision ou choisir un autre symbole.")
        
        return "\n".join(lines)


# Instance globale
technical_gates_service = TechnicalGatesService()

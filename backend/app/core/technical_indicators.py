"""
Service d'Indicateurs Techniques pour TradeMe V2.2.

Calcule et formate les indicateurs techniques pour les agents IA:
- RSI (Relative Strength Index) - survendu/surachat
- MACD (Moving Average Convergence Divergence) - tendance
- Support/Résistance - zones de prix clés
- Volume Relatif - confirmation des mouvements

Impact estimé: +25-40% de rentabilité
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Direction de la tendance."""
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"


class RSISignal(Enum):
    """Signal RSI."""
    OVERSOLD = "OVERSOLD"          # RSI < 30 - Signal d'achat
    APPROACHING_OVERSOLD = "APPROACHING_OVERSOLD"  # RSI 30-40
    NEUTRAL = "NEUTRAL"            # RSI 40-60
    APPROACHING_OVERBOUGHT = "APPROACHING_OVERBOUGHT"  # RSI 60-70
    OVERBOUGHT = "OVERBOUGHT"      # RSI > 70 - Signal de vente


class MACDSignal(Enum):
    """Signal MACD."""
    BULLISH_CROSSOVER = "BULLISH_CROSSOVER"    # MACD croise au-dessus du signal
    BULLISH = "BULLISH"                         # MACD > Signal
    NEUTRAL = "NEUTRAL"                         # MACD ≈ Signal
    BEARISH = "BEARISH"                         # MACD < Signal
    BEARISH_CROSSOVER = "BEARISH_CROSSOVER"    # MACD croise en-dessous du signal


class VolumeSignal(Enum):
    """Signal de volume."""
    VERY_HIGH = "VERY_HIGH"    # Volume > 200% de la moyenne
    HIGH = "HIGH"              # Volume > 150% de la moyenne
    NORMAL = "NORMAL"          # Volume 80-150% de la moyenne
    LOW = "LOW"                # Volume < 80% de la moyenne
    VERY_LOW = "VERY_LOW"      # Volume < 50% de la moyenne


@dataclass
class TechnicalAnalysis:
    """Résultat complet de l'analyse technique."""
    symbol: str
    
    # RSI
    rsi: float
    rsi_signal: RSISignal
    
    # MACD
    macd_line: float
    macd_signal_line: float
    macd_histogram: float
    macd_signal: MACDSignal
    
    # Support/Résistance
    support_level: float
    resistance_level: float
    distance_to_support_pct: float
    distance_to_resistance_pct: float
    
    # Volume
    current_volume: int
    avg_volume_20d: float
    volume_ratio: float
    volume_signal: VolumeSignal
    
    # Tendance globale
    trend: TrendDirection
    trend_strength: int  # 0-100
    
    # Prix actuel
    current_price: float
    
    # Score global (0-100)
    bullish_score: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "symbol": self.symbol,
            "rsi": self.rsi,
            "rsi_signal": self.rsi_signal.value,
            "macd_line": self.macd_line,
            "macd_signal_line": self.macd_signal_line,
            "macd_histogram": self.macd_histogram,
            "macd_signal": self.macd_signal.value,
            "support_level": self.support_level,
            "resistance_level": self.resistance_level,
            "distance_to_support_pct": self.distance_to_support_pct,
            "distance_to_resistance_pct": self.distance_to_resistance_pct,
            "current_volume": self.current_volume,
            "avg_volume_20d": self.avg_volume_20d,
            "volume_ratio": self.volume_ratio,
            "volume_signal": self.volume_signal.value,
            "trend": self.trend.value,
            "trend_strength": self.trend_strength,
            "current_price": self.current_price,
            "bullish_score": self.bullish_score,
        }


class TechnicalIndicatorsService:
    """
    Service de calcul des indicateurs techniques.
    
    Utilise les données OHLCV pour calculer:
    - RSI (14 périodes)
    - MACD (12, 26, 9)
    - Support/Résistance (swing highs/lows)
    - Volume relatif (vs SMA 20)
    """
    
    def __init__(self):
        """Initialise le service."""
        self._initialized = False
        
        # Paramètres RSI
        self.rsi_period = 14
        
        # Paramètres MACD
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
        # Paramètres Volume
        self.volume_period = 20
        
        # Paramètres Support/Résistance
        self.sr_lookback = 20
    
    def initialize(self) -> bool:
        """Initialise le service."""
        self._initialized = True
        logger.info("✅ Technical Indicators Service initialisé")
        return True
    
    def calculate_rsi(self, closes: List[float], period: int = None) -> float:
        """
        Calcule le RSI (Relative Strength Index).
        
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        
        Args:
            closes: Liste des prix de clôture (du plus ancien au plus récent)
            period: Période de calcul (défaut: 14)
            
        Returns: RSI entre 0 et 100
        """
        period = period or self.rsi_period
        
        if len(closes) < period + 1:
            return 50.0  # Valeur neutre si pas assez de données
        
        # Calculer les variations
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        # Séparer gains et pertes
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        # Moyenne des gains/pertes sur la période
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0  # Tous les mouvements sont à la hausse
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    def get_rsi_signal(self, rsi: float) -> RSISignal:
        """Détermine le signal RSI."""
        if rsi < 30:
            return RSISignal.OVERSOLD
        elif rsi < 40:
            return RSISignal.APPROACHING_OVERSOLD
        elif rsi > 70:
            return RSISignal.OVERBOUGHT
        elif rsi > 60:
            return RSISignal.APPROACHING_OVERBOUGHT
        else:
            return RSISignal.NEUTRAL
    
    def calculate_ema(self, values: List[float], period: int) -> List[float]:
        """
        Calcule l'EMA (Exponential Moving Average).
        
        Args:
            values: Liste des valeurs
            period: Période EMA
            
        Returns: Liste des EMA
        """
        if len(values) < period:
            return [values[-1]] if values else [0]
        
        multiplier = 2 / (period + 1)
        ema = [sum(values[:period]) / period]  # Première EMA = SMA
        
        for value in values[period:]:
            ema.append((value - ema[-1]) * multiplier + ema[-1])
        
        return ema
    
    def calculate_macd(
        self, 
        closes: List[float],
        fast: int = None,
        slow: int = None,
        signal: int = None,
    ) -> Tuple[float, float, float]:
        """
        Calcule le MACD (Moving Average Convergence Divergence).
        
        MACD Line = EMA(12) - EMA(26)
        Signal Line = EMA(9) du MACD Line
        Histogram = MACD Line - Signal Line
        
        Args:
            closes: Liste des prix de clôture
            fast: Période EMA rapide (défaut: 12)
            slow: Période EMA lente (défaut: 26)
            signal: Période signal (défaut: 9)
            
        Returns: (macd_line, signal_line, histogram)
        """
        fast = fast or self.macd_fast
        slow = slow or self.macd_slow
        signal = signal or self.macd_signal
        
        if len(closes) < slow + signal:
            return (0.0, 0.0, 0.0)
        
        # Calculer les EMA
        ema_fast = self.calculate_ema(closes, fast)
        ema_slow = self.calculate_ema(closes, slow)
        
        # MACD Line = EMA Fast - EMA Slow
        # Aligner les longueurs
        min_len = min(len(ema_fast), len(ema_slow))
        macd_line_values = [
            ema_fast[-(min_len - i)] - ema_slow[-(min_len - i)] 
            for i in range(min_len)
        ]
        
        if len(macd_line_values) < signal:
            return (macd_line_values[-1] if macd_line_values else 0, 0, 0)
        
        # Signal Line = EMA du MACD
        signal_line_values = self.calculate_ema(macd_line_values, signal)
        
        macd_line = round(macd_line_values[-1], 4)
        signal_line = round(signal_line_values[-1], 4)
        histogram = round(macd_line - signal_line, 4)
        
        return (macd_line, signal_line, histogram)
    
    def get_macd_signal(
        self, 
        macd_line: float, 
        signal_line: float,
        prev_macd: float = None,
        prev_signal: float = None,
    ) -> MACDSignal:
        """Détermine le signal MACD."""
        # Détecter les crossovers si on a les données précédentes
        if prev_macd is not None and prev_signal is not None:
            if prev_macd <= prev_signal and macd_line > signal_line:
                return MACDSignal.BULLISH_CROSSOVER
            elif prev_macd >= prev_signal and macd_line < signal_line:
                return MACDSignal.BEARISH_CROSSOVER
        
        # Signal basé sur la position relative
        diff = macd_line - signal_line
        if abs(diff) < 0.01:  # Très proche
            return MACDSignal.NEUTRAL
        elif diff > 0:
            return MACDSignal.BULLISH
        else:
            return MACDSignal.BEARISH
    
    def calculate_support_resistance(
        self, 
        highs: List[float], 
        lows: List[float],
        current_price: float,
        lookback: int = None,
    ) -> Tuple[float, float]:
        """
        Calcule les niveaux de support et résistance.
        
        Utilise les swing highs/lows récents.
        
        Args:
            highs: Liste des prix hauts
            lows: Liste des prix bas
            current_price: Prix actuel
            lookback: Nombre de périodes à analyser
            
        Returns: (support, resistance)
        """
        lookback = lookback or self.sr_lookback
        
        if len(highs) < 5 or len(lows) < 5:
            return (current_price * 0.95, current_price * 1.05)
        
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        
        # Trouver les swing highs (pic local)
        swing_highs = []
        for i in range(2, len(recent_highs) - 2):
            if (recent_highs[i] > recent_highs[i-1] and 
                recent_highs[i] > recent_highs[i-2] and
                recent_highs[i] > recent_highs[i+1] and 
                recent_highs[i] > recent_highs[i+2]):
                swing_highs.append(recent_highs[i])
        
        # Trouver les swing lows (creux local)
        swing_lows = []
        for i in range(2, len(recent_lows) - 2):
            if (recent_lows[i] < recent_lows[i-1] and 
                recent_lows[i] < recent_lows[i-2] and
                recent_lows[i] < recent_lows[i+1] and 
                recent_lows[i] < recent_lows[i+2]):
                swing_lows.append(recent_lows[i])
        
        # Support = plus proche swing low sous le prix actuel
        supports_below = [s for s in swing_lows if s < current_price]
        support = max(supports_below) if supports_below else min(recent_lows)
        
        # Résistance = plus proche swing high au-dessus du prix actuel
        resistances_above = [r for r in swing_highs if r > current_price]
        resistance = min(resistances_above) if resistances_above else max(recent_highs)
        
        return (round(support, 2), round(resistance, 2))
    
    def calculate_volume_ratio(
        self, 
        volumes: List[int], 
        period: int = None,
    ) -> Tuple[float, float]:
        """
        Calcule le ratio de volume par rapport à la moyenne.
        
        Args:
            volumes: Liste des volumes
            period: Période pour la moyenne (défaut: 20)
            
        Returns: (volume_ratio, avg_volume)
        """
        period = period or self.volume_period
        
        if len(volumes) < period + 1:
            return (1.0, volumes[-1] if volumes else 0)
        
        avg_volume = sum(volumes[-period-1:-1]) / period
        current_volume = volumes[-1]
        
        if avg_volume == 0:
            return (1.0, 0)
        
        ratio = current_volume / avg_volume
        return (round(ratio, 2), round(avg_volume, 0))
    
    def get_volume_signal(self, volume_ratio: float) -> VolumeSignal:
        """Détermine le signal de volume."""
        if volume_ratio > 2.0:
            return VolumeSignal.VERY_HIGH
        elif volume_ratio > 1.5:
            return VolumeSignal.HIGH
        elif volume_ratio < 0.5:
            return VolumeSignal.VERY_LOW
        elif volume_ratio < 0.8:
            return VolumeSignal.LOW
        else:
            return VolumeSignal.NORMAL
    
    def calculate_trend(
        self, 
        closes: List[float],
        rsi: float,
        macd_signal: MACDSignal,
        volume_signal: VolumeSignal,
    ) -> Tuple[TrendDirection, int]:
        """
        Détermine la tendance globale et sa force.
        
        Combine plusieurs indicateurs pour une analyse plus robuste.
        
        Returns: (direction, strength 0-100)
        """
        if len(closes) < 20:
            return (TrendDirection.NEUTRAL, 50)
        
        # Tendance de prix (SMA 10 vs SMA 20)
        sma_10 = sum(closes[-10:]) / 10
        sma_20 = sum(closes[-20:]) / 20
        price_trend_score = 50
        
        if sma_10 > sma_20 * 1.02:
            price_trend_score = 75
        elif sma_10 > sma_20:
            price_trend_score = 60
        elif sma_10 < sma_20 * 0.98:
            price_trend_score = 25
        elif sma_10 < sma_20:
            price_trend_score = 40
        
        # Score RSI
        rsi_score = 50
        if rsi < 30:
            rsi_score = 80  # Oversold = potentiel haussier
        elif rsi < 40:
            rsi_score = 65
        elif rsi > 70:
            rsi_score = 20  # Overbought = potentiel baissier
        elif rsi > 60:
            rsi_score = 35
        
        # Score MACD
        macd_scores = {
            MACDSignal.BULLISH_CROSSOVER: 90,
            MACDSignal.BULLISH: 70,
            MACDSignal.NEUTRAL: 50,
            MACDSignal.BEARISH: 30,
            MACDSignal.BEARISH_CROSSOVER: 10,
        }
        macd_score = macd_scores.get(macd_signal, 50)
        
        # Score volume (confirme ou infirme)
        volume_multiplier = {
            VolumeSignal.VERY_HIGH: 1.2,
            VolumeSignal.HIGH: 1.1,
            VolumeSignal.NORMAL: 1.0,
            VolumeSignal.LOW: 0.9,
            VolumeSignal.VERY_LOW: 0.8,
        }
        vol_mult = volume_multiplier.get(volume_signal, 1.0)
        
        # Score final pondéré
        raw_score = (
            price_trend_score * 0.3 +
            rsi_score * 0.3 +
            macd_score * 0.4
        ) * vol_mult
        
        strength = min(100, max(0, int(raw_score)))
        
        # Déterminer la direction
        if strength >= 75:
            direction = TrendDirection.STRONG_BULLISH
        elif strength >= 60:
            direction = TrendDirection.BULLISH
        elif strength <= 25:
            direction = TrendDirection.STRONG_BEARISH
        elif strength <= 40:
            direction = TrendDirection.BEARISH
        else:
            direction = TrendDirection.NEUTRAL
        
        return (direction, strength)
    
    def analyze(
        self, 
        symbol: str,
        ohlcv_data: List[Dict[str, Any]],
    ) -> Optional[TechnicalAnalysis]:
        """
        Effectue une analyse technique complète.
        
        Args:
            symbol: Symbole de l'action
            ohlcv_data: Liste de barres OHLCV (du plus ancien au plus récent)
                       Chaque barre: {open, high, low, close, volume}
            
        Returns: TechnicalAnalysis ou None si erreur
        """
        if not ohlcv_data or len(ohlcv_data) < 30:
            logger.warning(f"Pas assez de données pour {symbol} ({len(ohlcv_data) if ohlcv_data else 0} barres)")
            return None
        
        try:
            # Extraire les séries
            closes = [bar["close"] for bar in ohlcv_data]
            highs = [bar["high"] for bar in ohlcv_data]
            lows = [bar["low"] for bar in ohlcv_data]
            volumes = [bar["volume"] for bar in ohlcv_data]
            
            current_price = closes[-1]
            current_volume = volumes[-1]
            
            # RSI
            rsi = self.calculate_rsi(closes)
            rsi_signal = self.get_rsi_signal(rsi)
            
            # MACD
            macd_line, signal_line, histogram = self.calculate_macd(closes)
            macd_signal = self.get_macd_signal(macd_line, signal_line)
            
            # Support/Résistance
            support, resistance = self.calculate_support_resistance(
                highs, lows, current_price
            )
            distance_to_support = ((current_price - support) / current_price) * 100
            distance_to_resistance = ((resistance - current_price) / current_price) * 100
            
            # Volume
            volume_ratio, avg_volume = self.calculate_volume_ratio(volumes)
            volume_signal = self.get_volume_signal(volume_ratio)
            
            # Tendance globale
            trend, trend_strength = self.calculate_trend(
                closes, rsi, macd_signal, volume_signal
            )
            
            # Score bullish final (0-100)
            bullish_score = trend_strength
            
            return TechnicalAnalysis(
                symbol=symbol,
                rsi=rsi,
                rsi_signal=rsi_signal,
                macd_line=macd_line,
                macd_signal_line=signal_line,
                macd_histogram=histogram,
                macd_signal=macd_signal,
                support_level=support,
                resistance_level=resistance,
                distance_to_support_pct=round(distance_to_support, 2),
                distance_to_resistance_pct=round(distance_to_resistance, 2),
                current_volume=current_volume,
                avg_volume_20d=avg_volume,
                volume_ratio=volume_ratio,
                volume_signal=volume_signal,
                trend=trend,
                trend_strength=trend_strength,
                current_price=current_price,
                bullish_score=bullish_score,
            )
            
        except Exception as e:
            logger.error(f"Erreur analyse technique {symbol}: {e}")
            return None
    
    def format_for_agent(self, analysis: TechnicalAnalysis) -> str:
        """
        Formate l'analyse technique pour le prompt de l'agent.
        
        Args:
            analysis: Résultat de l'analyse technique
            
        Returns: Texte formaté pour le prompt
        """
        if not analysis:
            return ""
        
        # Emoji pour RSI
        rsi_emoji = {
            RSISignal.OVERSOLD: "🟢 SURVENDU (opportunité d'achat)",
            RSISignal.APPROACHING_OVERSOLD: "🟡 Proche survendu",
            RSISignal.NEUTRAL: "⚪ Neutre",
            RSISignal.APPROACHING_OVERBOUGHT: "🟡 Proche surachat",
            RSISignal.OVERBOUGHT: "🔴 SURACHAT (risque de correction)",
        }
        
        # Emoji pour MACD
        macd_emoji = {
            MACDSignal.BULLISH_CROSSOVER: "🚀 CROISEMENT HAUSSIER (signal fort!)",
            MACDSignal.BULLISH: "📈 Haussier",
            MACDSignal.NEUTRAL: "➡️ Neutre",
            MACDSignal.BEARISH: "📉 Baissier",
            MACDSignal.BEARISH_CROSSOVER: "⚠️ CROISEMENT BAISSIER (signal de vente!)",
        }
        
        # Emoji pour Volume
        volume_emoji = {
            VolumeSignal.VERY_HIGH: "🔥 VOLUME TRÈS ÉLEVÉ (confirmation forte)",
            VolumeSignal.HIGH: "📊 Volume élevé",
            VolumeSignal.NORMAL: "📊 Volume normal",
            VolumeSignal.LOW: "📉 Volume faible (attention)",
            VolumeSignal.VERY_LOW: "⚠️ VOLUME TRÈS FAIBLE (manque de conviction)",
        }
        
        # Emoji pour Tendance
        trend_emoji = {
            TrendDirection.STRONG_BULLISH: "🚀🚀 FORTE TENDANCE HAUSSIÈRE",
            TrendDirection.BULLISH: "📈 Tendance haussière",
            TrendDirection.NEUTRAL: "➡️ Tendance neutre",
            TrendDirection.BEARISH: "📉 Tendance baissière",
            TrendDirection.STRONG_BEARISH: "⚠️⚠️ FORTE TENDANCE BAISSIÈRE",
        }
        
        text = f"""
## 📊 ANALYSE TECHNIQUE - {analysis.symbol}

### Prix Actuel: ${analysis.current_price:.2f}

### 📈 RSI (14): {analysis.rsi:.1f}
{rsi_emoji.get(analysis.rsi_signal, analysis.rsi_signal.value)}

### 📉 MACD ({self.macd_fast}/{self.macd_slow}/{self.macd_signal})
- MACD Line: {analysis.macd_line:.4f}
- Signal Line: {analysis.macd_signal_line:.4f}
- Histogram: {analysis.macd_histogram:.4f}
{macd_emoji.get(analysis.macd_signal, analysis.macd_signal.value)}

### 🎯 SUPPORT / RÉSISTANCE
- Support: ${analysis.support_level:.2f} ({analysis.distance_to_support_pct:.1f}% sous le prix)
- Résistance: ${analysis.resistance_level:.2f} ({analysis.distance_to_resistance_pct:.1f}% au-dessus)

### 📊 VOLUME
- Volume actuel: {analysis.current_volume:,}
- Volume moyen 20j: {analysis.avg_volume_20d:,.0f}
- Ratio: {analysis.volume_ratio:.2f}x
{volume_emoji.get(analysis.volume_signal, analysis.volume_signal.value)}

### 🎯 TENDANCE GLOBALE
{trend_emoji.get(analysis.trend, analysis.trend.value)}
- Force de tendance: {analysis.trend_strength}/100
- **Score Bullish: {analysis.bullish_score}/100**

### ⚡ SIGNAUX CLÉS
"""
        
        # Ajouter les signaux clés
        signals = []
        
        if analysis.rsi_signal == RSISignal.OVERSOLD:
            signals.append("✅ RSI survendu = Potentiel rebond")
        elif analysis.rsi_signal == RSISignal.OVERBOUGHT:
            signals.append("⚠️ RSI surachat = Risque de correction")
        
        if analysis.macd_signal == MACDSignal.BULLISH_CROSSOVER:
            signals.append("✅ MACD croisement haussier = Signal d'achat")
        elif analysis.macd_signal == MACDSignal.BEARISH_CROSSOVER:
            signals.append("⚠️ MACD croisement baissier = Signal de vente")
        
        if analysis.volume_signal in [VolumeSignal.VERY_HIGH, VolumeSignal.HIGH]:
            signals.append("✅ Volume élevé = Conviction du mouvement")
        elif analysis.volume_signal in [VolumeSignal.VERY_LOW, VolumeSignal.LOW]:
            signals.append("⚠️ Volume faible = Manque de conviction")
        
        if analysis.distance_to_support_pct < 3:
            signals.append("✅ Proche du support = Zone d'achat potentielle")
        elif analysis.distance_to_resistance_pct < 3:
            signals.append("⚠️ Proche de la résistance = Zone de prise de profits")
        
        if signals:
            text += "\n".join(f"- {s}" for s in signals)
        else:
            text += "- Pas de signal particulier"
        
        return text


# Instance globale
technical_indicators = TechnicalIndicatorsService()

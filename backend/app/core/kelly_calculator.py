"""
Kelly Calculator - Position Sizing Mathématique Optimal.
Calcule la taille de position idéale basée sur le Critère de Kelly.

Le Critère de Kelly: f* = W - (1-W)/R
où:
- f* = fraction optimale du capital à risquer
- W = probabilité de gain (win rate)
- R = ratio gain/perte moyen (win/loss ratio)

Avec des ajustements pour:
- Le niveau de confiance de l'IA
- La volatilité du marché (VIX)
- Les signaux Smart Money
"""
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from .supabase_client import supabase_client

logger = logging.getLogger(__name__)


@dataclass
class PositionSizing:
    """Résultat du calcul de position sizing."""
    recommended_amount: float  # Montant en $ à investir
    position_pct: float  # % du capital
    kelly_fraction: float  # Fraction Kelly brute
    adjusted_kelly: float  # Kelly ajusté (half-Kelly ou autre)
    confidence_factor: float  # Facteur basé sur la confiance
    risk_factor: float  # Facteur basé sur le risque/volatilité
    max_loss: float  # Perte maximale potentielle
    reasoning: str  # Explication du calcul


class KellyCalculator:
    """
    Calculateur de position sizing basé sur le Critère de Kelly.
    Adapté pour le trading avec IAs.
    
    V2 AMÉLIORATIONS:
    - Kelly DYNAMIQUE basé sur VIX
    - Ajustement selon streak (wins/losses consécutifs)
    - Intégration avec Circuit Breaker
    """
    
    def __init__(self):
        self._initialized = False
        
        # Paramètres par défaut
        self.default_win_rate = 0.50  # 50% si pas d'historique
        self.default_win_loss_ratio = 1.5  # Ratio G/P par défaut
        self.max_position_pct = 0.10  # Maximum 10% du capital par trade
        self.min_position_pct = 0.01  # Minimum 1% du capital
        self.base_kelly_multiplier = 0.5  # Half-Kelly de base
        
        # === NOUVEAU V2: Multiplicateurs dynamiques VIX ===
        self.vix_low_threshold = 15  # VIX < 15 = marché calme
        self.vix_high_threshold = 30  # VIX > 30 = marché volatile
        self.vix_low_multiplier = 1.5  # Augmente sizing si VIX bas
        self.vix_high_multiplier = 0.5  # Réduit sizing si VIX haut
        
        # === NOUVEAU V2: Multiplicateurs streak ===
        self.win_streak_threshold = 5  # Bonus après 5 gains
        self.loss_streak_threshold = 3  # Malus après 3 pertes
        self.win_streak_bonus = 1.2  # +20% après win streak
        self.loss_streak_malus = 0.6  # -40% après loss streak
    
    def initialize(self) -> bool:
        """Initialise le calculateur."""
        self._initialized = True
        logger.info("✅ Kelly Calculator initialisé (V2 - DYNAMIQUE)")
        logger.info(f"   📊 VIX bas (<{self.vix_low_threshold}): Kelly x{self.vix_low_multiplier}")
        logger.info(f"   📊 VIX haut (>{self.vix_high_threshold}): Kelly x{self.vix_high_multiplier}")
        logger.info(f"   🔥 Win streak (>{self.win_streak_threshold}): Kelly x{self.win_streak_bonus}")
        logger.info(f"   ⚠️ Loss streak (>{self.loss_streak_threshold}): Kelly x{self.loss_streak_malus}")
        return True
    
    def get_dynamic_kelly_multiplier(
        self,
        vix: float = 20,
        consecutive_wins: int = 0,
        consecutive_losses: int = 0,
    ) -> float:
        """
        Calcule le multiplicateur Kelly dynamique basé sur VIX et streaks.
        
        NOUVEAU V2:
        - VIX < 15 → x1.5 (marché calme, plus de risque OK)
        - VIX > 30 → x0.5 (marché volatile, prudence)
        - 5+ wins consécutifs → x1.2 (hot hand)
        - 3+ losses consécutifs → x0.6 (cool down)
        """
        multiplier = self.base_kelly_multiplier
        
        # Ajustement VIX
        if vix < self.vix_low_threshold:
            vix_factor = self.vix_low_multiplier
            logger.debug(f"VIX bas ({vix}): Kelly x{vix_factor}")
        elif vix > self.vix_high_threshold:
            vix_factor = self.vix_high_multiplier
            logger.debug(f"VIX haut ({vix}): Kelly x{vix_factor}")
        else:
            # Interpolation linéaire entre les deux
            vix_range = self.vix_high_threshold - self.vix_low_threshold
            vix_position = (vix - self.vix_low_threshold) / vix_range
            vix_factor = self.vix_low_multiplier - (vix_position * (self.vix_low_multiplier - self.vix_high_multiplier))
        
        multiplier *= vix_factor
        
        # Ajustement streak
        if consecutive_wins >= self.win_streak_threshold:
            multiplier *= self.win_streak_bonus
            logger.info(f"🔥 Win streak ({consecutive_wins}): Kelly boost x{self.win_streak_bonus}")
        elif consecutive_losses >= self.loss_streak_threshold:
            multiplier *= self.loss_streak_malus
            logger.warning(f"⚠️ Loss streak ({consecutive_losses}): Kelly réduit x{self.loss_streak_malus}")
        
        return multiplier
    
    def calculate_kelly_fraction(
        self,
        win_rate: float,
        win_loss_ratio: float,
    ) -> float:
        """
        Calcule la fraction Kelly brute.
        
        Formule: f* = W - (1-W)/R
        
        Args:
            win_rate: Probabilité de gain (0-1)
            win_loss_ratio: Ratio gain moyen / perte moyenne
            
        Returns:
            Fraction du capital à risquer (peut être négative si edge négatif)
        """
        if win_loss_ratio <= 0:
            return 0.0
        
        kelly = win_rate - (1 - win_rate) / win_loss_ratio
        return kelly
    
    def get_agent_statistics(self, agent_id: str) -> Dict[str, float]:
        """
        Récupère les statistiques d'un agent depuis la base.
        V2.5: Gère le cas où la table est vide ou inexistante.
        """
        if not supabase_client._initialized:
            return {
                "win_rate": self.default_win_rate,
                "win_loss_ratio": self.default_win_loss_ratio,
                "kelly_fraction": 0.125,  # Kelly par défaut conservateur
            }
        
        try:
            # V2.5: Utiliser limit(1) + execute() au lieu de single() pour éviter l'erreur 406
            response = supabase_client.client.table('agent_statistics').select('*').eq('agent_id', agent_id).limit(1).execute()
            
            if response and response.data and len(response.data) > 0:
                stats = response.data[0]
                return {
                    "win_rate": float(stats.get('win_rate', self.default_win_rate)),
                    "win_loss_ratio": float(stats.get('win_loss_ratio', self.default_win_loss_ratio)),
                    "kelly_fraction": float(stats.get('kelly_fraction', 0.125)),
                    "total_trades": stats.get('total_trades', 0),
                    "avg_win_pct": float(stats.get('avg_win_pct', 0)),
                    "avg_loss_pct": float(stats.get('avg_loss_pct', 0)),
                }
            
        except Exception as e:
            # Ne pas logger si c'est juste une table vide
            if "406" not in str(e) and "0 rows" not in str(e):
                logger.warning(f"Erreur récupération stats agent: {e}")
        
        return {
            "win_rate": self.default_win_rate,
            "win_loss_ratio": self.default_win_loss_ratio,
            "kelly_fraction": 0.125,
        }
    
    def calculate_confidence_factor(self, confidence: int) -> float:
        """
        Calcule un facteur multiplicateur basé sur la confiance de l'IA.
        
        Confiance 50% -> facteur 0.5
        Confiance 70% -> facteur 0.7
        Confiance 90% -> facteur 1.0
        Confiance 100% -> facteur 1.1
        """
        if confidence < 50:
            return 0.3  # Très faible confiance = position minimale
        elif confidence < 60:
            return 0.5
        elif confidence < 70:
            return 0.7
        elif confidence < 80:
            return 0.85
        elif confidence < 90:
            return 1.0
        else:
            return 1.1  # Haute confiance = légèrement plus
    
    def calculate_risk_factor(
        self,
        vix: float = 20,
        risk_level: str = "MEDIUM",
        smart_money_signal: str = "NEUTRAL",
    ) -> float:
        """
        Calcule un facteur de risque basé sur les conditions de marché.
        
        VIX bas + signal bullish = facteur élevé (1.2)
        VIX élevé + signal bearish = facteur faible (0.5)
        """
        factor = 1.0
        
        # Ajustement VIX
        if vix < 15:
            factor *= 1.1  # Marché calme = plus de risque OK
        elif vix > 25:
            factor *= 0.8  # Marché volatile = moins de risque
        elif vix > 35:
            factor *= 0.5  # Marché très volatile = prudence
        
        # Ajustement niveau de risque
        if risk_level == "LOW":
            factor *= 1.1
        elif risk_level == "HIGH":
            factor *= 0.8
        
        # Ajustement Smart Money
        if smart_money_signal in ["BULLISH", "STRONG_BULLISH"]:
            factor *= 1.1
        elif smart_money_signal in ["BEARISH", "STRONG_BEARISH"]:
            factor *= 0.8
        
        return min(1.3, max(0.4, factor))  # Borné entre 0.4 et 1.3
    
    def calculate_position_size(
        self,
        agent_id: str,
        capital: float,
        confidence: int,
        risk_level: str = "MEDIUM",
        vix: float = 20,
        smart_money_signal: str = "NEUTRAL",
        symbol: str = None,
        consecutive_wins: int = 0,
        consecutive_losses: int = 0,
    ) -> PositionSizing:
        """
        Calcule la taille de position optimale pour un trade.
        
        V2 AMÉLIORÉ:
        - Kelly DYNAMIQUE selon VIX
        - Ajustement selon streak de wins/losses
        
        Args:
            agent_id: ID de l'agent
            capital: Capital disponible
            confidence: Niveau de confiance de l'IA (0-100)
            risk_level: Niveau de risque du trade (LOW, MEDIUM, HIGH)
            vix: Niveau actuel du VIX
            smart_money_signal: Signal des données alternatives
            symbol: Symbole du trade (optionnel)
            consecutive_wins: Nombre de gains consécutifs
            consecutive_losses: Nombre de pertes consécutives
            
        Returns:
            PositionSizing avec le montant recommandé et les détails
        """
        # 1. Récupérer les stats de l'agent
        stats = self.get_agent_statistics(agent_id)
        win_rate = stats["win_rate"]
        win_loss_ratio = stats["win_loss_ratio"]
        
        # 2. Calculer le Kelly brut
        kelly_raw = self.calculate_kelly_fraction(win_rate, win_loss_ratio)
        
        # 3. NOUVEAU V2: Calculer le multiplicateur dynamique
        dynamic_multiplier = self.get_dynamic_kelly_multiplier(
            vix=vix,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
        )
        
        # 4. Appliquer le Kelly dynamique
        kelly_adjusted = kelly_raw * dynamic_multiplier
        
        # 5. Calculer les facteurs d'ajustement
        confidence_factor = self.calculate_confidence_factor(confidence)
        risk_factor = self.calculate_risk_factor(vix, risk_level, smart_money_signal)
        
        # 6. Position finale
        final_kelly = kelly_adjusted * confidence_factor * risk_factor
        
        # 7. Appliquer les bornes min/max
        position_pct = min(self.max_position_pct, max(self.min_position_pct, final_kelly))
        
        # Si Kelly négatif (pas d'edge), utiliser le minimum
        if kelly_raw <= 0:
            position_pct = self.min_position_pct
        
        # 8. Calculer le montant
        amount = capital * position_pct
        max_loss = amount * 0.05  # Stop-loss à 5%
        
        # 9. Construire l'explication
        reasoning = self._build_reasoning_v2(
            stats, kelly_raw, kelly_adjusted, confidence, confidence_factor,
            risk_factor, position_pct, vix, smart_money_signal,
            dynamic_multiplier, consecutive_wins, consecutive_losses
        )
        
        result = PositionSizing(
            recommended_amount=round(amount, 2),
            position_pct=round(position_pct, 4),
            kelly_fraction=round(kelly_raw, 4),
            adjusted_kelly=round(kelly_adjusted, 4),
            confidence_factor=round(confidence_factor, 2),
            risk_factor=round(risk_factor, 2),
            max_loss=round(max_loss, 2),
            reasoning=reasoning,
        )
        
        logger.info(
            f"💰 Kelly sizing V2: ${amount:.2f} ({position_pct*100:.1f}% du capital) - "
            f"VIX={vix}, Streak={consecutive_wins}W/{consecutive_losses}L, Multiplier={dynamic_multiplier:.2f}"
        )
        
        return result
    
    def _build_reasoning_v2(
        self,
        stats: Dict,
        kelly_raw: float,
        kelly_adjusted: float,
        confidence: int,
        confidence_factor: float,
        risk_factor: float,
        final_pct: float,
        vix: float,
        smart_signal: str,
        dynamic_multiplier: float,
        consecutive_wins: int,
        consecutive_losses: int,
    ) -> str:
        """Construit l'explication du calcul V2."""
        
        parts = [
            f"📊 **Calcul Kelly Position Sizing V2 (DYNAMIQUE)**",
            f"",
            f"**Stats historiques:**",
            f"- Win Rate: {stats['win_rate']*100:.1f}%",
            f"- Ratio G/P: {stats['win_loss_ratio']:.2f}",
            f"- Trades historiques: {stats.get('total_trades', 'N/A')}",
            f"",
            f"**Calcul Kelly:**",
            f"- Kelly brut: {kelly_raw*100:.2f}%",
            f"- Multiplicateur dynamique: x{dynamic_multiplier:.2f}",
            f"  - VIX ({vix}): {'📈 Boost' if vix < 15 else '📉 Réduit' if vix > 30 else '➡️ Neutre'}",
            f"  - Streak: {consecutive_wins}W / {consecutive_losses}L",
            f"- Kelly ajusté: {kelly_adjusted*100:.2f}%",
            f"",
            f"**Ajustements:**",
            f"- Confiance IA ({confidence}%): x{confidence_factor}",
            f"- Risque marché (Signal={smart_signal}): x{risk_factor}",
            f"",
            f"**Résultat final: {final_pct*100:.2f}% du capital**",
        ]
        
        return "\n".join(parts)
    
    def _build_reasoning(
        self,
        stats: Dict,
        kelly_raw: float,
        kelly_adjusted: float,
        confidence: int,
        confidence_factor: float,
        risk_factor: float,
        final_pct: float,
        vix: float,
        smart_signal: str,
    ) -> str:
        """Construit l'explication du calcul."""
        
        parts = [
            f"📊 **Calcul Kelly Position Sizing**",
            f"",
            f"**Stats historiques:**",
            f"- Win Rate: {stats['win_rate']*100:.1f}%",
            f"- Ratio G/P: {stats['win_loss_ratio']:.2f}",
            f"- Trades historiques: {stats.get('total_trades', 'N/A')}",
            f"",
            f"**Calcul Kelly:**",
            f"- Kelly brut: {kelly_raw*100:.2f}%",
            f"- Half-Kelly: {kelly_adjusted*100:.2f}%",
            f"",
            f"**Ajustements:**",
            f"- Confiance IA ({confidence}%): x{confidence_factor}",
            f"- Risque marché (VIX={vix}, {smart_signal}): x{risk_factor}",
            f"",
            f"**Résultat final: {final_pct*100:.2f}% du capital**",
        ]
        
        return "\n".join(parts)
    
    def get_position_for_confidence_levels(
        self,
        agent_id: str,
        capital: float,
    ) -> Dict[str, float]:
        """
        Retourne une table de sizing par niveau de confiance.
        Utile pour donner à l'IA une idée des montants possibles.
        """
        levels = {}
        for conf in [50, 60, 70, 80, 90, 95]:
            sizing = self.calculate_position_size(
                agent_id=agent_id,
                capital=capital,
                confidence=conf,
            )
            levels[f"{conf}%"] = sizing.recommended_amount
        
        return levels
    
    def format_kelly_for_agent(
        self,
        agent_id: str,
        capital: float,
    ) -> str:
        """
        Formate les informations Kelly pour inclusion dans le prompt de l'agent.
        """
        stats = self.get_agent_statistics(agent_id)
        levels = self.get_position_for_confidence_levels(agent_id, capital)
        
        lines = [
            "\n## 💰 POSITION SIZING OPTIMAL (Critère de Kelly)",
            f"Basé sur ton historique: Win Rate {stats['win_rate']*100:.1f}%, Ratio G/P {stats['win_loss_ratio']:.2f}",
            "",
            "**Montants recommandés selon ta confiance:**",
        ]
        
        for level, amount in levels.items():
            lines.append(f"  - Confiance {level}: ${amount:,.0f}")
        
        lines.extend([
            "",
            "⚠️ **Règles:**",
            "- Haute confiance (>85%) = Grosse mise",
            "- Confiance moyenne (70-85%) = Mise standard",
            "- Faible confiance (<70%) = Petite mise ou HOLD",
            "- JAMAIS plus de 10% du capital sur un seul trade",
        ])
        
        return "\n".join(lines)


# Instance globale
kelly_calculator = KellyCalculator()

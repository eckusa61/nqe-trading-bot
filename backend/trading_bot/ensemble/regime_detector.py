"""
Hidden Markov Model Regime Detector
Detects market regimes: Bull, Bear, Sideways, Crisis
"""
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum
import random

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime states"""
    BULL = "bull"           # Low vol, positive trend
    BEAR = "bear"           # High vol, negative trend  
    SIDEWAYS = "sideways"   # Low vol, no clear trend
    CRISIS = "crisis"       # Extreme vol, correlation spike


@dataclass
class RegimeState:
    """Current regime state with probabilities"""
    current_regime: MarketRegime
    regime_probabilities: Dict[MarketRegime, float]
    confidence: float
    timestamp: datetime
    indicators: Dict[str, float]
    
    def to_dict(self) -> Dict:
        return {
            "current_regime": self.current_regime.value,
            "regime_probabilities": {k.value: round(v, 3) for k, v in self.regime_probabilities.items()},
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp.isoformat(),
            "indicators": {k: round(v, 4) for k, v in self.indicators.items()}
        }


class RegimeDetector:
    """
    Hidden Markov Model-based regime detector
    
    States:
    - BULL: Positive returns, low volatility, upward trend
    - BEAR: Negative returns, high volatility, downward trend
    - SIDEWAYS: Mixed returns, low volatility, no trend
    - CRISIS: Extreme volatility, correlation breakdown
    
    Observations:
    - Return (20-day)
    - Volatility (20-day annualized)
    - VIX level
    - Trend strength (ADX)
    - Correlation (SPY/QQQ)
    """
    
    def __init__(
        self,
        vix_crisis_threshold: float = 35.0,
        vix_elevated_threshold: float = 20.0,
        vol_high_threshold: float = 0.25,  # 25% annualized
        trend_threshold: float = 25.0,     # ADX threshold
        return_threshold: float = 0.02,    # 2% monthly
        lookback_days: int = 20
    ):
        self.vix_crisis_threshold = vix_crisis_threshold
        self.vix_elevated_threshold = vix_elevated_threshold
        self.vol_high_threshold = vol_high_threshold
        self.trend_threshold = trend_threshold
        self.return_threshold = return_threshold
        self.lookback_days = lookback_days
        
        # HMM parameters (simplified)
        # Transition probabilities: P(next_state | current_state)
        self.transition_matrix = {
            MarketRegime.BULL: {
                MarketRegime.BULL: 0.85,
                MarketRegime.BEAR: 0.05,
                MarketRegime.SIDEWAYS: 0.08,
                MarketRegime.CRISIS: 0.02
            },
            MarketRegime.BEAR: {
                MarketRegime.BULL: 0.10,
                MarketRegime.BEAR: 0.70,
                MarketRegime.SIDEWAYS: 0.10,
                MarketRegime.CRISIS: 0.10
            },
            MarketRegime.SIDEWAYS: {
                MarketRegime.BULL: 0.20,
                MarketRegime.BEAR: 0.15,
                MarketRegime.SIDEWAYS: 0.60,
                MarketRegime.CRISIS: 0.05
            },
            MarketRegime.CRISIS: {
                MarketRegime.BULL: 0.05,
                MarketRegime.BEAR: 0.30,
                MarketRegime.SIDEWAYS: 0.15,
                MarketRegime.CRISIS: 0.50
            }
        }
        
        # State tracking
        self.current_state = MarketRegime.SIDEWAYS
        self.state_probabilities = {regime: 0.25 for regime in MarketRegime}
        self.regime_history: List[RegimeState] = []
        self.current_vix = 15.0
        
        logger.info("RegimeDetector initialized (HMM-based)")
    
    def _calculate_emission_probability(
        self,
        regime: MarketRegime,
        return_20d: float,
        volatility: float,
        vix: float,
        adx: float
    ) -> float:
        """
        Calculate P(observations | state) - emission probability
        
        Higher probability = observations more likely in this regime
        """
        prob = 1.0
        
        if regime == MarketRegime.BULL:
            # Bull: positive returns, low vol, low VIX, may have trend
            if return_20d > 0:
                prob *= 1.0 + min(return_20d * 10, 0.5)  # Reward positive returns
            else:
                prob *= 0.5
            
            if volatility < self.vol_high_threshold:
                prob *= 1.2
            else:
                prob *= 0.6
            
            if vix < self.vix_elevated_threshold:
                prob *= 1.3
            else:
                prob *= 0.5
        
        elif regime == MarketRegime.BEAR:
            # Bear: negative returns, high vol, elevated VIX
            if return_20d < 0:
                prob *= 1.0 + min(abs(return_20d) * 10, 0.5)
            else:
                prob *= 0.4
            
            if volatility > self.vol_high_threshold * 0.8:
                prob *= 1.3
            else:
                prob *= 0.7
            
            if vix > self.vix_elevated_threshold:
                prob *= 1.2
            else:
                prob *= 0.6
        
        elif regime == MarketRegime.SIDEWAYS:
            # Sideways: small returns, low vol, weak trend
            if abs(return_20d) < self.return_threshold:
                prob *= 1.3
            else:
                prob *= 0.6
            
            if volatility < self.vol_high_threshold:
                prob *= 1.2
            else:
                prob *= 0.7
            
            if adx < self.trend_threshold:
                prob *= 1.3
            else:
                prob *= 0.6
        
        elif regime == MarketRegime.CRISIS:
            # Crisis: extreme vol, VIX spike
            if vix > self.vix_crisis_threshold:
                prob *= 2.0
            elif vix > self.vix_elevated_threshold * 1.5:
                prob *= 1.5
            else:
                prob *= 0.3
            
            if volatility > self.vol_high_threshold * 1.5:
                prob *= 1.5
            else:
                prob *= 0.5
        
        return max(0.01, prob)  # Ensure non-zero
    
    def update(
        self,
        return_20d: float,
        volatility: float,
        vix: float,
        adx: float,
        spy_qqq_correlation: float = 0.9
    ) -> RegimeState:
        """
        Update regime probabilities using HMM forward algorithm
        
        Args:
            return_20d: 20-day return
            volatility: Annualized volatility
            vix: VIX level (or proxy)
            adx: ADX trend strength
            spy_qqq_correlation: Correlation between SPY and QQQ
        
        Returns:
            RegimeState with current regime and probabilities
        """
        self.current_vix = vix
        
        # Calculate emission probabilities for each state
        emission_probs = {}
        for regime in MarketRegime:
            emission_probs[regime] = self._calculate_emission_probability(
                regime, return_20d, volatility, vix, adx
            )
        
        # Forward step: new_prob[j] = sum_i(prob[i] * transition[i][j]) * emission[j]
        new_probs = {}
        for next_regime in MarketRegime:
            prob_sum = 0.0
            for current_regime in MarketRegime:
                transition_prob = self.transition_matrix[current_regime][next_regime]
                prob_sum += self.state_probabilities[current_regime] * transition_prob
            
            new_probs[next_regime] = prob_sum * emission_probs[next_regime]
        
        # Normalize
        total = sum(new_probs.values())
        if total > 0:
            self.state_probabilities = {k: v / total for k, v in new_probs.items()}
        
        # Determine current regime (highest probability)
        self.current_state = max(self.state_probabilities, key=self.state_probabilities.get)
        
        # Calculate confidence (how certain are we?)
        max_prob = self.state_probabilities[self.current_state]
        confidence = max_prob * 2 - 0.5  # Scale: 0.25 -> 0, 0.75 -> 1
        confidence = max(0, min(1, confidence))
        
        # Create state object
        state = RegimeState(
            current_regime=self.current_state,
            regime_probabilities=self.state_probabilities.copy(),
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            indicators={
                "return_20d": return_20d,
                "volatility": volatility,
                "vix": vix,
                "adx": adx,
                "correlation": spy_qqq_correlation
            }
        )
        
        # Store history
        self.regime_history.append(state)
        if len(self.regime_history) > 252:  # Keep 1 year
            self.regime_history = self.regime_history[-252:]
        
        logger.debug(f"Regime updated: {self.current_state.value} (conf={confidence:.2f})")
        
        return state
    
    def detect_from_features(self, features_list: List) -> RegimeState:
        """
        Detect regime from feature sets (convenience method)
        
        Takes average of all symbols' features
        """
        if not features_list:
            return RegimeState(
                current_regime=MarketRegime.SIDEWAYS,
                regime_probabilities={r: 0.25 for r in MarketRegime},
                confidence=0.0,
                timestamp=datetime.now(timezone.utc),
                indicators={}
            )
        
        # Average indicators across symbols
        avg_return = sum(f.return_20d for f in features_list) / len(features_list)
        avg_vol = sum(f.volatility_annualized for f in features_list) / len(features_list)
        avg_adx = sum(f.adx_14 for f in features_list) / len(features_list)
        
        # Use stored VIX or estimate from volatility
        vix = self.current_vix or avg_vol * 100
        
        return self.update(
            return_20d=avg_return,
            volatility=avg_vol,
            vix=vix,
            adx=avg_adx
        )
    
    def get_regime_duration(self) -> int:
        """Get how many periods we've been in current regime"""
        if not self.regime_history:
            return 0
        
        duration = 0
        current = self.current_state
        
        for state in reversed(self.regime_history):
            if state.current_regime == current:
                duration += 1
            else:
                break
        
        return duration
    
    def get_regime_statistics(self) -> Dict:
        """Get statistics about regime detection"""
        if not self.regime_history:
            return {}
        
        # Count time in each regime
        regime_counts = {r: 0 for r in MarketRegime}
        for state in self.regime_history:
            regime_counts[state.current_regime] += 1
        
        total = len(self.regime_history)
        
        return {
            "current_regime": self.current_state.value,
            "current_duration": self.get_regime_duration(),
            "regime_distribution": {
                r.value: round(c / total * 100, 1)
                for r, c in regime_counts.items()
            },
            "total_observations": total,
            "current_probabilities": {
                r.value: round(p, 3)
                for r, p in self.state_probabilities.items()
            }
        }
    
    def set_vix(self, vix: float):
        """Manually set VIX level"""
        self.current_vix = vix


class RuleBasedRegimeDetector:
    """
    Simpler rule-based regime detection as backup/comparison
    
    Uses fixed thresholds without HMM
    """
    
    def __init__(self):
        self.current_regime = MarketRegime.SIDEWAYS
    
    def detect(
        self,
        return_20d: float,
        volatility: float,
        vix: float,
        adx: float
    ) -> MarketRegime:
        """Simple rule-based detection"""
        
        # Crisis: VIX > 35
        if vix > 35:
            self.current_regime = MarketRegime.CRISIS
            return self.current_regime
        
        # Bull: Positive return, low vol, VIX < 20
        if return_20d > 0.02 and volatility < 0.20 and vix < 20:
            self.current_regime = MarketRegime.BULL
            return self.current_regime
        
        # Bear: Negative return, high vol or VIX > 25
        if return_20d < -0.02 and (volatility > 0.25 or vix > 25):
            self.current_regime = MarketRegime.BEAR
            return self.current_regime
        
        # Sideways: Everything else
        self.current_regime = MarketRegime.SIDEWAYS
        return self.current_regime

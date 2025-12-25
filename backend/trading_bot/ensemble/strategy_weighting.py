"""
Strategy Weighting by Regime
Assigns optimal weights to strategies based on market regime
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from trading_bot.ensemble.regime_detector import MarketRegime

logger = logging.getLogger(__name__)


@dataclass
class RegimeWeights:
    """Strategy weights for a specific regime"""
    regime: MarketRegime
    weights: Dict[str, float]  # strategy_name -> weight (0 to 1)
    
    def get_weight(self, strategy_name: str) -> float:
        return self.weights.get(strategy_name, 0.0)


@dataclass
class WeightUpdate:
    """Record of a weight update"""
    timestamp: datetime
    regime: MarketRegime
    strategy: str
    old_weight: float
    new_weight: float
    reason: str


class StrategyWeightManager:
    """
    Manages strategy weights based on market regime
    
    Key insight: Different strategies work in different regimes
    - Momentum: Works in trending markets (Bull/Bear)
    - Mean Reversion: Works in sideways/range-bound markets
    - Trend Following: Works in strong trends
    - Volatility Breakout: Works in regime transitions
    - Stat Arb: Works in stable correlation environments
    """
    
    def __init__(self):
        # Default regime-based weights (sum to 1.0 per regime)
        self.regime_weights: Dict[MarketRegime, RegimeWeights] = {
            MarketRegime.BULL: RegimeWeights(
                regime=MarketRegime.BULL,
                weights={
                    "Momentum": 0.35,
                    "TrendFollowing": 0.30,
                    "MeanReversion": 0.10,
                    "VolatilityBreakout": 0.15,
                    "StatArb": 0.10
                }
            ),
            MarketRegime.BEAR: RegimeWeights(
                regime=MarketRegime.BEAR,
                weights={
                    "Momentum": 0.20,  # Momentum can work short
                    "TrendFollowing": 0.25,
                    "MeanReversion": 0.25,  # Oversold bounces
                    "VolatilityBreakout": 0.20,
                    "StatArb": 0.10
                }
            ),
            MarketRegime.SIDEWAYS: RegimeWeights(
                regime=MarketRegime.SIDEWAYS,
                weights={
                    "Momentum": 0.05,  # Don't chase in ranges
                    "TrendFollowing": 0.05,
                    "MeanReversion": 0.50,  # Mean reversion king
                    "VolatilityBreakout": 0.15,
                    "StatArb": 0.25
                }
            ),
            MarketRegime.CRISIS: RegimeWeights(
                regime=MarketRegime.CRISIS,
                weights={
                    "Momentum": 0.10,
                    "TrendFollowing": 0.10,
                    "MeanReversion": 0.30,  # Extreme oversold
                    "VolatilityBreakout": 0.35,  # Vol expansion
                    "StatArb": 0.15
                }
            )
        }
        
        # Performance-based adjustments
        self.strategy_performance: Dict[str, Dict[MarketRegime, List[float]]] = {}
        self.weight_history: List[WeightUpdate] = []
        
        # Minimum/maximum weight bounds
        self.min_weight = 0.05
        self.max_weight = 0.50
        
        logger.info("StrategyWeightManager initialized")
    
    def get_weights(self, regime: MarketRegime) -> Dict[str, float]:
        """Get strategy weights for a regime"""
        if regime in self.regime_weights:
            return self.regime_weights[regime].weights.copy()
        return {}
    
    def get_weight(self, strategy_name: str, regime: MarketRegime) -> float:
        """Get weight for a specific strategy in a regime"""
        weights = self.get_weights(regime)
        return weights.get(strategy_name, 0.0)
    
    def record_performance(
        self,
        strategy_name: str,
        regime: MarketRegime,
        pnl: float
    ):
        """
        Record strategy performance in a regime
        Used for adaptive weight adjustment
        """
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = {r: [] for r in MarketRegime}
        
        self.strategy_performance[strategy_name][regime].append(pnl)
        
        # Keep only last 50 observations per regime
        if len(self.strategy_performance[strategy_name][regime]) > 50:
            self.strategy_performance[strategy_name][regime] = \
                self.strategy_performance[strategy_name][regime][-50:]
    
    def calculate_rolling_sharpe(
        self,
        strategy_name: str,
        regime: MarketRegime,
        lookback: int = 20
    ) -> Optional[float]:
        """Calculate rolling Sharpe for strategy in regime"""
        if strategy_name not in self.strategy_performance:
            return None
        
        pnls = self.strategy_performance[strategy_name].get(regime, [])
        
        if len(pnls) < lookback:
            return None
        
        recent = pnls[-lookback:]
        mean_pnl = sum(recent) / len(recent)
        
        if len(recent) < 2:
            return 0.0
        
        variance = sum((p - mean_pnl) ** 2 for p in recent) / (len(recent) - 1)
        std = variance ** 0.5
        
        if std == 0:
            return 0.0
        
        # Annualize (assume daily)
        sharpe = (mean_pnl / std) * (252 ** 0.5)
        return sharpe
    
    def adapt_weights(self, regime: MarketRegime) -> Dict[str, float]:
        """
        Adapt weights based on recent performance
        
        Bayesian-style update: Increase weights for outperforming strategies
        """
        base_weights = self.get_weights(regime)
        
        # Calculate performance scores
        scores = {}
        for strategy in base_weights:
            sharpe = self.calculate_rolling_sharpe(strategy, regime)
            if sharpe is not None:
                # Convert Sharpe to score (0.5 to 1.5 range)
                score = 1.0 + max(-0.5, min(0.5, sharpe / 4))
                scores[strategy] = score
            else:
                scores[strategy] = 1.0  # Neutral if no data
        
        # Apply scores to base weights
        adjusted = {}
        for strategy, base_weight in base_weights.items():
            new_weight = base_weight * scores.get(strategy, 1.0)
            new_weight = max(self.min_weight, min(self.max_weight, new_weight))
            adjusted[strategy] = new_weight
        
        # Normalize to sum to 1
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        
        return adjusted
    
    def update_regime_weights(
        self,
        regime: MarketRegime,
        new_weights: Dict[str, float],
        reason: str = "Manual update"
    ):
        """Update weights for a regime"""
        old_weights = self.get_weights(regime)
        
        # Validate and apply
        validated_weights = {}
        for strategy, weight in new_weights.items():
            weight = max(self.min_weight, min(self.max_weight, weight))
            validated_weights[strategy] = weight
            
            # Record update
            if strategy in old_weights:
                self.weight_history.append(WeightUpdate(
                    timestamp=datetime.now(timezone.utc),
                    regime=regime,
                    strategy=strategy,
                    old_weight=old_weights.get(strategy, 0),
                    new_weight=weight,
                    reason=reason
                ))
        
        # Normalize
        total = sum(validated_weights.values())
        if total > 0:
            validated_weights = {k: v / total for k, v in validated_weights.items()}
        
        self.regime_weights[regime] = RegimeWeights(
            regime=regime,
            weights=validated_weights
        )
        
        logger.info(f"Updated weights for {regime.value}: {validated_weights}")
    
    def get_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate correlation between strategies
        High correlation = reduce combined weight
        """
        strategies = list(self.strategy_performance.keys())
        
        if len(strategies) < 2:
            return {}
        
        correlations = {}
        for s1 in strategies:
            correlations[s1] = {}
            for s2 in strategies:
                if s1 == s2:
                    correlations[s1][s2] = 1.0
                else:
                    corr = self._calculate_correlation(s1, s2)
                    correlations[s1][s2] = corr
        
        return correlations
    
    def _calculate_correlation(self, strategy1: str, strategy2: str) -> float:
        """Calculate correlation between two strategies' returns"""
        # Combine all regime data
        returns1 = []
        returns2 = []
        
        for regime in MarketRegime:
            r1 = self.strategy_performance.get(strategy1, {}).get(regime, [])
            r2 = self.strategy_performance.get(strategy2, {}).get(regime, [])
            
            # Align lengths
            min_len = min(len(r1), len(r2))
            if min_len > 0:
                returns1.extend(r1[-min_len:])
                returns2.extend(r2[-min_len:])
        
        if len(returns1) < 10:
            return 0.0
        
        # Calculate correlation
        n = len(returns1)
        mean1 = sum(returns1) / n
        mean2 = sum(returns2) / n
        
        cov = sum((returns1[i] - mean1) * (returns2[i] - mean2) for i in range(n)) / n
        std1 = (sum((r - mean1) ** 2 for r in returns1) / n) ** 0.5
        std2 = (sum((r - mean2) ** 2 for r in returns2) / n) ** 0.5
        
        if std1 * std2 == 0:
            return 0.0
        
        return cov / (std1 * std2)
    
    def apply_correlation_penalty(
        self,
        weights: Dict[str, float],
        max_correlation: float = 0.7
    ) -> Dict[str, float]:
        """
        Reduce weights for highly correlated strategies
        """
        correlations = self.get_correlation_matrix()
        
        if not correlations:
            return weights
        
        penalties = {s: 1.0 for s in weights}
        
        for s1 in weights:
            for s2 in weights:
                if s1 != s2 and s1 in correlations and s2 in correlations.get(s1, {}):
                    corr = abs(correlations[s1][s2])
                    if corr > max_correlation:
                        # Penalize both strategies
                        penalty = 1.0 - (corr - max_correlation) * 0.5
                        penalties[s1] = min(penalties[s1], penalty)
                        penalties[s2] = min(penalties[s2], penalty)
        
        # Apply penalties
        adjusted = {s: w * penalties.get(s, 1.0) for s, w in weights.items()}
        
        # Renormalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        
        return adjusted
    
    def get_optimal_weights(self, regime: MarketRegime) -> Dict[str, float]:
        """
        Get optimal weights considering:
        1. Base regime weights
        2. Performance adaptation
        3. Correlation penalties
        """
        # Start with adapted weights
        weights = self.adapt_weights(regime)
        
        # Apply correlation penalty
        weights = self.apply_correlation_penalty(weights)
        
        return weights
    
    def get_status(self) -> Dict:
        """Get current weight manager status"""
        return {
            "regime_weights": {
                regime.value: self.get_weights(regime)
                for regime in MarketRegime
            },
            "performance_data_points": {
                strategy: {
                    regime.value: len(pnls)
                    for regime, pnls in regimes.items()
                }
                for strategy, regimes in self.strategy_performance.items()
            },
            "recent_updates": [
                {
                    "timestamp": u.timestamp.isoformat(),
                    "regime": u.regime.value,
                    "strategy": u.strategy,
                    "old_weight": round(u.old_weight, 3),
                    "new_weight": round(u.new_weight, 3),
                    "reason": u.reason
                }
                for u in self.weight_history[-10:]
            ]
        }

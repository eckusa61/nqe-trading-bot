"""
Meta-Learner / Ensemble System
Combines signals from multiple strategies using regime-aware weights
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from trading_bot.strategies.base_strategy import Signal, StrategyResult
from trading_bot.ensemble.regime_detector import RegimeDetector, MarketRegime, RegimeState
from trading_bot.ensemble.strategy_weighting import StrategyWeightManager

logger = logging.getLogger(__name__)


@dataclass
class EnsembleSignal:
    """Combined signal from multiple strategies"""
    symbol: str
    combined_signal: float  # -1 to +1
    combined_confidence: float
    regime: MarketRegime
    contributing_strategies: Dict[str, float]  # strategy -> weighted signal
    strategy_weights: Dict[str, float]
    agreement_score: float  # How much strategies agree
    contrarian_flag: bool   # True if all strategies agree (reduce position)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "combined_signal": round(self.combined_signal, 4),
            "combined_confidence": round(self.combined_confidence, 3),
            "regime": self.regime.value,
            "contributing_strategies": {k: round(v, 4) for k, v in self.contributing_strategies.items()},
            "strategy_weights": {k: round(v, 3) for k, v in self.strategy_weights.items()},
            "agreement_score": round(self.agreement_score, 3),
            "contrarian_flag": self.contrarian_flag,
            "timestamp": self.timestamp.isoformat()
        }


class MetaLearner:
    """
    Ensemble system that combines multiple strategy signals
    
    Features:
    1. Regime-aware weighting
    2. Strategy correlation handling
    3. Contrarian override (reduce when all agree)
    4. Confidence aggregation
    5. Signal smoothing
    """
    
    def __init__(
        self,
        regime_detector: Optional[RegimeDetector] = None,
        weight_manager: Optional[StrategyWeightManager] = None,
        contrarian_threshold: float = 0.9,   # Agreement level to trigger contrarian
        contrarian_reduction: float = 0.5,    # Reduce signal by 50% when contrarian
        min_confidence: float = 0.3,          # Minimum confidence to include signal
        signal_smoothing: float = 0.7         # Exponential smoothing factor
    ):
        self.regime_detector = regime_detector or RegimeDetector()
        self.weight_manager = weight_manager or StrategyWeightManager()
        
        self.contrarian_threshold = contrarian_threshold
        self.contrarian_reduction = contrarian_reduction
        self.min_confidence = min_confidence
        self.signal_smoothing = signal_smoothing
        
        # Track previous signals for smoothing
        self.previous_signals: Dict[str, float] = {}
        
        # History
        self.ensemble_history: List[EnsembleSignal] = []
        
        logger.info("MetaLearner initialized")
    
    def combine_signals(
        self,
        strategy_results: List[StrategyResult],
        regime: Optional[MarketRegime] = None
    ) -> List[EnsembleSignal]:
        """
        Combine signals from multiple strategies
        
        Args:
            strategy_results: List of StrategyResult from each strategy
            regime: Optional override for current regime
        
        Returns:
            List of EnsembleSignal for each symbol
        """
        if not strategy_results:
            return []
        
        # Use provided regime or current detected regime
        current_regime = regime or self.regime_detector.current_state
        
        # Get optimal weights for current regime
        weights = self.weight_manager.get_optimal_weights(current_regime)
        
        # Group signals by symbol
        signals_by_symbol: Dict[str, List[Tuple[str, Signal]]] = {}
        
        for result in strategy_results:
            for signal in result.signals:
                if signal.symbol not in signals_by_symbol:
                    signals_by_symbol[signal.symbol] = []
                signals_by_symbol[signal.symbol].append((result.strategy_name, signal))
        
        # Combine signals for each symbol
        ensemble_signals = []
        
        for symbol, strategy_signals in signals_by_symbol.items():
            ensemble_signal = self._combine_symbol_signals(
                symbol=symbol,
                strategy_signals=strategy_signals,
                weights=weights,
                regime=current_regime
            )
            ensemble_signals.append(ensemble_signal)
            self.ensemble_history.append(ensemble_signal)
        
        # Keep history limited
        if len(self.ensemble_history) > 1000:
            self.ensemble_history = self.ensemble_history[-1000:]
        
        return ensemble_signals
    
    def _combine_symbol_signals(
        self,
        symbol: str,
        strategy_signals: List[Tuple[str, Signal]],
        weights: Dict[str, float],
        regime: MarketRegime
    ) -> EnsembleSignal:
        """Combine signals for a single symbol"""
        
        contributing = {}
        total_weight = 0.0
        weighted_signal_sum = 0.0
        weighted_confidence_sum = 0.0
        
        # Calculate weighted combination
        for strategy_name, signal in strategy_signals:
            weight = weights.get(strategy_name, 0.0)
            
            # Skip low confidence signals
            if signal.confidence < self.min_confidence:
                continue
            
            # Weight the signal
            weighted_signal = signal.signal * weight * signal.confidence
            contributing[strategy_name] = weighted_signal
            
            weighted_signal_sum += weighted_signal
            weighted_confidence_sum += signal.confidence * weight
            total_weight += weight
        
        # Calculate combined signal
        if total_weight > 0:
            combined_signal = weighted_signal_sum / total_weight
            combined_confidence = weighted_confidence_sum / total_weight
        else:
            combined_signal = 0.0
            combined_confidence = 0.0
        
        # Calculate agreement score
        agreement = self._calculate_agreement(strategy_signals)
        
        # Check for contrarian flag
        contrarian_flag = False
        if agreement > self.contrarian_threshold:
            # All strategies strongly agree - reduce position (contrarian)
            contrarian_flag = True
            combined_signal *= self.contrarian_reduction
            logger.debug(f"{symbol}: Contrarian reduction applied (agreement={agreement:.2f})")
        
        # Apply signal smoothing
        if symbol in self.previous_signals:
            smoothed = (
                self.signal_smoothing * combined_signal +
                (1 - self.signal_smoothing) * self.previous_signals[symbol]
            )
            combined_signal = smoothed
        
        self.previous_signals[symbol] = combined_signal
        
        # Clamp to [-1, 1]
        combined_signal = max(-1.0, min(1.0, combined_signal))
        
        return EnsembleSignal(
            symbol=symbol,
            combined_signal=combined_signal,
            combined_confidence=combined_confidence,
            regime=regime,
            contributing_strategies=contributing,
            strategy_weights={k: weights.get(k, 0) for k, _ in strategy_signals},
            agreement_score=agreement,
            contrarian_flag=contrarian_flag
        )
    
    def _calculate_agreement(self, strategy_signals: List[Tuple[str, Signal]]) -> float:
        """
        Calculate how much strategies agree
        
        Returns 0-1: 0 = complete disagreement, 1 = complete agreement
        """
        if len(strategy_signals) < 2:
            return 0.0
        
        signals = [s.signal for _, s in strategy_signals if abs(s.signal) > 0.1]
        
        if len(signals) < 2:
            return 0.0
        
        # Count how many are in same direction
        positive = sum(1 for s in signals if s > 0)
        negative = sum(1 for s in signals if s < 0)
        
        # Agreement = majority / total
        agreement = max(positive, negative) / len(signals)
        
        return agreement
    
    def update_regime(self, features_list: List) -> RegimeState:
        """Update regime detection with new features"""
        return self.regime_detector.detect_from_features(features_list)
    
    def record_trade_result(
        self,
        strategy_name: str,
        regime: MarketRegime,
        pnl: float
    ):
        """Record trade result for weight adaptation"""
        self.weight_manager.record_performance(strategy_name, regime, pnl)
    
    def get_ensemble_summary(self, symbol: str) -> Optional[Dict]:
        """Get summary of recent ensemble signals for a symbol"""
        recent = [
            e for e in self.ensemble_history[-50:]
            if e.symbol == symbol
        ]
        
        if not recent:
            return None
        
        avg_signal = sum(e.combined_signal for e in recent) / len(recent)
        avg_confidence = sum(e.combined_confidence for e in recent) / len(recent)
        contrarian_count = sum(1 for e in recent if e.contrarian_flag)
        
        return {
            "symbol": symbol,
            "recent_count": len(recent),
            "avg_signal": round(avg_signal, 4),
            "avg_confidence": round(avg_confidence, 3),
            "contrarian_triggers": contrarian_count,
            "latest": recent[-1].to_dict() if recent else None
        }
    
    def get_status(self) -> Dict:
        """Get meta-learner status"""
        return {
            "regime": {
                "current": self.regime_detector.current_state.value,
                "probabilities": {
                    r.value: round(p, 3)
                    for r, p in self.regime_detector.state_probabilities.items()
                },
                "duration": self.regime_detector.get_regime_duration()
            },
            "weights": self.weight_manager.get_status(),
            "settings": {
                "contrarian_threshold": self.contrarian_threshold,
                "contrarian_reduction": self.contrarian_reduction,
                "min_confidence": self.min_confidence,
                "signal_smoothing": self.signal_smoothing
            },
            "history_count": len(self.ensemble_history),
            "symbols_tracked": list(self.previous_signals.keys())
        }

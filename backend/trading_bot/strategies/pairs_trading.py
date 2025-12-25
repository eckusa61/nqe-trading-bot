"""
Pairs Trading Strategy with Cointegration
Trades correlated pairs when spread deviates from mean
"""
import logging
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


@dataclass
class PairStats:
    pair: tuple
    spread_mean: float
    spread_std: float
    z_score: float
    correlation: float
    half_life: float


class PairsTradingStrategy(BaseStrategy):
    """
    Statistical Arbitrage Pairs Trading
    
    Logic:
    1. Find cointegrated pairs
    2. Calculate spread z-score
    3. Enter when z-score > threshold
    4. Exit when z-score reverts to 0
    """
    
    name = "PairsTrading"
    
    def __init__(
        self,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        lookback: int = 60,
        min_correlation: float = 0.7,
        max_half_life: int = 30
    ):
        super().__init__()
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.lookback = lookback
        self.min_correlation = min_correlation
        self.max_half_life = max_half_life
        
        # Predefined pairs
        self.pairs = [
            ("SPY", "QQQ"),
            ("AAPL", "MSFT"),
            ("NVDA", "AMD"),
            ("META", "GOOGL"),
        ]
        
        self.pair_stats: Dict[tuple, PairStats] = {}
        logger.info(f"PairsTrading initialized with {len(self.pairs)} pairs")
    
    def calculate_spread(self, prices1: np.ndarray, prices2: np.ndarray) -> np.ndarray:
        """Calculate log spread between two price series"""
        return np.log(prices1) - np.log(prices2)
    
    def calculate_z_score(self, spread: np.ndarray) -> float:
        """Calculate z-score of current spread"""
        mean = np.mean(spread)
        std = np.std(spread)
        if std == 0:
            return 0.0
        return (spread[-1] - mean) / std
    
    def calculate_half_life(self, spread: np.ndarray) -> float:
        """Calculate mean reversion half-life using OLS"""
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)
        
        if len(spread_lag) < 2:
            return float('inf')
        
        # Simple regression: spread_diff = alpha + beta * spread_lag
        beta = np.cov(spread_lag, spread_diff)[0, 1] / np.var(spread_lag)
        
        if beta >= 0:
            return float('inf')
        
        return -np.log(2) / beta
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate pairs trading signal"""
        signals = []
        
        for pair in self.pairs:
            if symbol not in pair:
                continue
            
            # Get price data for both symbols
            prices1 = features.get(f"{pair[0]}_close", [])
            prices2 = features.get(f"{pair[1]}_close", [])
            
            if len(prices1) < self.lookback or len(prices2) < self.lookback:
                continue
            
            prices1 = np.array(prices1[-self.lookback:])
            prices2 = np.array(prices2[-self.lookback:])
            
            # Calculate spread and stats
            spread = self.calculate_spread(prices1, prices2)
            z_score = self.calculate_z_score(spread)
            correlation = np.corrcoef(prices1, prices2)[0, 1]
            half_life = self.calculate_half_life(spread)
            
            # Store stats
            self.pair_stats[pair] = PairStats(
                pair=pair,
                spread_mean=np.mean(spread),
                spread_std=np.std(spread),
                z_score=z_score,
                correlation=correlation,
                half_life=half_life
            )
            
            # Check conditions
            if correlation < self.min_correlation:
                continue
            if half_life > self.max_half_life:
                continue
            
            # Generate signal
            signal_value = 0.0
            confidence = 0.0
            
            if z_score > self.entry_z:
                # Spread too high - short pair[0], long pair[1]
                if symbol == pair[0]:
                    signal_value = -1.0
                else:
                    signal_value = 1.0
                confidence = min(abs(z_score) / 3.0, 1.0)
                
            elif z_score < -self.entry_z:
                # Spread too low - long pair[0], short pair[1]
                if symbol == pair[0]:
                    signal_value = 1.0
                else:
                    signal_value = -1.0
                confidence = min(abs(z_score) / 3.0, 1.0)
                
            elif abs(z_score) < self.exit_z:
                # Close position
                signal_value = 0.0
                confidence = 0.8
            
            if signal_value != 0:
                signals.append((signal_value, confidence))
        
        # Aggregate signals
        if not signals:
            return StrategyResult(
                strategy_name=self.name,
                symbol=symbol,
                signal=Signal.HOLD,
                raw_signal=0.0,
                confidence=0.0,
                features_used={"pairs_checked": len(self.pairs)},
                timestamp=datetime.now(timezone.utc)
            )
        
        avg_signal = np.mean([s[0] for s in signals])
        avg_confidence = np.mean([s[1] for s in signals])
        
        if avg_signal > 0.3:
            signal = Signal.BUY
        elif avg_signal < -0.3:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD
        
        return StrategyResult(
            strategy_name=self.name,
            symbol=symbol,
            signal=signal,
            raw_signal=avg_signal,
            confidence=avg_confidence,
            features_used={
                "z_scores": {str(k): v.z_score for k, v in self.pair_stats.items()},
                "correlations": {str(k): v.correlation for k, v in self.pair_stats.items()}
            },
            timestamp=datetime.now(timezone.utc)
        )

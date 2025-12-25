"""
Breakout Strategy
Detects and trades price breakouts from consolidation ranges
"""
import logging
import numpy as np
from typing import Dict, Optional
from datetime import datetime, timezone

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


class BreakoutStrategy(BaseStrategy):
    """
    Breakout Trading Strategy
    
    Logic:
    1. Identify consolidation ranges (low volatility)
    2. Detect breakouts above/below range
    3. Confirm with volume spike
    4. Enter in breakout direction
    """
    
    name = "Breakout"
    
    def __init__(
        self,
        lookback: int = 20,
        breakout_threshold: float = 0.02,
        volume_multiplier: float = 1.5,
        consolidation_periods: int = 10,
        atr_multiplier: float = 1.5
    ):
        super().__init__()
        self.lookback = lookback
        self.breakout_threshold = breakout_threshold
        self.volume_multiplier = volume_multiplier
        self.consolidation_periods = consolidation_periods
        self.atr_multiplier = atr_multiplier
        logger.info("Breakout strategy initialized")
    
    def calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> float:
        """Calculate Average True Range"""
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))[1:]
        return np.mean(tr[-self.lookback:])
    
    def is_consolidating(self, close: np.ndarray) -> bool:
        """Check if price is in consolidation"""
        recent = close[-self.consolidation_periods:]
        range_pct = (np.max(recent) - np.min(recent)) / np.mean(recent)
        return range_pct < self.breakout_threshold
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate breakout signal"""
        close = np.array(features.get('close', []))
        high = np.array(features.get('high', []))
        low = np.array(features.get('low', []))
        volume = np.array(features.get('volume', []))
        
        if len(close) < self.lookback + self.consolidation_periods:
            return self._no_signal(symbol)
        
        # Calculate indicators
        atr = self.calculate_atr(high, low, close)
        avg_volume = np.mean(volume[-self.lookback:])
        current_volume = volume[-1]
        
        # Find range boundaries
        range_high = np.max(high[-self.lookback:])
        range_low = np.min(low[-self.lookback:])
        current_price = close[-1]
        prev_price = close[-2]
        
        # Check for consolidation before breakout
        was_consolidating = self.is_consolidating(close[:-1])
        
        # Volume confirmation
        volume_spike = current_volume > avg_volume * self.volume_multiplier
        
        signal_value = 0.0
        confidence = 0.0
        breakout_type = "none"
        
        # Bullish breakout
        if current_price > range_high and prev_price <= range_high:
            breakout_strength = (current_price - range_high) / atr
            if breakout_strength > 0.5:
                signal_value = min(breakout_strength, 1.0)
                confidence = 0.5
                breakout_type = "bullish"
                
                if was_consolidating:
                    confidence += 0.2
                if volume_spike:
                    confidence += 0.2
                    signal_value = min(signal_value * 1.2, 1.0)
        
        # Bearish breakout
        elif current_price < range_low and prev_price >= range_low:
            breakout_strength = (range_low - current_price) / atr
            if breakout_strength > 0.5:
                signal_value = -min(breakout_strength, 1.0)
                confidence = 0.5
                breakout_type = "bearish"
                
                if was_consolidating:
                    confidence += 0.2
                if volume_spike:
                    confidence += 0.2
                    signal_value = max(signal_value * 1.2, -1.0)
        
        # Determine signal
        if signal_value > 0.3:
            signal = Signal.BUY
        elif signal_value < -0.3:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD
        
        return StrategyResult(
            strategy_name=self.name,
            symbol=symbol,
            signal=signal,
            raw_signal=signal_value,
            confidence=min(confidence, 1.0),
            features_used={
                "range_high": range_high,
                "range_low": range_low,
                "atr": atr,
                "volume_spike": volume_spike,
                "breakout_type": breakout_type,
                "was_consolidating": was_consolidating
            },
            timestamp=datetime.now(timezone.utc)
        )
    
    def _no_signal(self, symbol: str) -> StrategyResult:
        return StrategyResult(
            strategy_name=self.name,
            symbol=symbol,
            signal=Signal.HOLD,
            raw_signal=0.0,
            confidence=0.0,
            features_used={},
            timestamp=datetime.now(timezone.utc)
        )

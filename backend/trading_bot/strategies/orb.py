"""
Opening Range Breakout (ORB) Strategy
Trades breakouts from the opening range
"""
import logging
import numpy as np
from typing import Dict
from datetime import datetime, timezone, time

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


class ORBStrategy(BaseStrategy):
    """
    Opening Range Breakout Strategy
    
    Logic:
    1. Define opening range (first 15-30 minutes)
    2. Wait for breakout above/below range
    3. Enter in breakout direction
    4. Use range as stop loss reference
    """
    
    name = "ORB"
    
    def __init__(
        self,
        opening_minutes: int = 30,
        breakout_buffer: float = 0.001,
        min_range_pct: float = 0.003,
        max_range_pct: float = 0.02
    ):
        super().__init__()
        self.opening_minutes = opening_minutes
        self.breakout_buffer = breakout_buffer
        self.min_range_pct = min_range_pct
        self.max_range_pct = max_range_pct
        
        self.opening_range_high = {}
        self.opening_range_low = {}
        self.breakout_occurred = {}
        
        logger.info("ORB strategy initialized")
    
    def calculate_opening_range(self, high: np.ndarray, low: np.ndarray, bars: int = 6) -> tuple:
        """Calculate opening range from first N bars"""
        if len(high) < bars:
            return None, None
        
        opening_high = np.max(high[:bars])
        opening_low = np.min(low[:bars])
        
        return opening_high, opening_low
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate ORB signal"""
        close = np.array(features.get('close', []))
        high = np.array(features.get('high', []))
        low = np.array(features.get('low', []))
        
        if len(close) < 10:
            return self._no_signal(symbol)
        
        # Calculate opening range
        or_high, or_low = self.calculate_opening_range(high, low)
        
        if or_high is None:
            return self._no_signal(symbol)
        
        current_price = close[-1]
        prev_price = close[-2] if len(close) > 1 else current_price
        
        # Calculate range metrics
        range_size = or_high - or_low
        range_pct = range_size / or_low
        range_mid = (or_high + or_low) / 2
        
        # Check if range is valid
        if range_pct < self.min_range_pct or range_pct > self.max_range_pct:
            return self._no_signal(symbol)
        
        signal_value = 0.0
        confidence = 0.0
        breakout_type = "none"
        
        # Bullish breakout
        breakout_level_high = or_high * (1 + self.breakout_buffer)
        if current_price > breakout_level_high and prev_price <= breakout_level_high:
            breakout_strength = (current_price - or_high) / range_size
            signal_value = min(0.7 + breakout_strength * 0.3, 1.0)
            confidence = 0.7
            breakout_type = "bullish"
            
            # Store for position management
            self.opening_range_high[symbol] = or_high
            self.opening_range_low[symbol] = or_low
            self.breakout_occurred[symbol] = "bullish"
        
        # Bearish breakout
        breakout_level_low = or_low * (1 - self.breakout_buffer)
        if current_price < breakout_level_low and prev_price >= breakout_level_low:
            breakout_strength = (or_low - current_price) / range_size
            signal_value = -min(0.7 + breakout_strength * 0.3, 1.0)
            confidence = 0.7
            breakout_type = "bearish"
            
            self.opening_range_high[symbol] = or_high
            self.opening_range_low[symbol] = or_low
            self.breakout_occurred[symbol] = "bearish"
        
        # Failed breakout / Reversal
        if symbol in self.breakout_occurred:
            if self.breakout_occurred[symbol] == "bullish" and current_price < range_mid:
                signal_value = -0.5
                confidence = 0.6
                breakout_type = "failed_bullish"
            elif self.breakout_occurred[symbol] == "bearish" and current_price > range_mid:
                signal_value = 0.5
                confidence = 0.6
                breakout_type = "failed_bearish"
        
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
            confidence=confidence,
            features_used={
                "or_high": or_high,
                "or_low": or_low,
                "range_pct": range_pct * 100,
                "breakout_type": breakout_type,
                "current_price": current_price
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

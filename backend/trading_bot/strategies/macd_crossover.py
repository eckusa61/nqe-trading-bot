"""
MACD Crossover Strategy
Trades MACD line and signal line crossovers with histogram confirmation
"""
import logging
import numpy as np
from typing import Dict
from datetime import datetime, timezone

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


class MACDCrossoverStrategy(BaseStrategy):
    """
    MACD Crossover Trading Strategy
    
    Logic:
    1. Calculate MACD line (fast EMA - slow EMA)
    2. Calculate Signal line (EMA of MACD)
    3. Calculate Histogram (MACD - Signal)
    4. Trade crossovers with histogram confirmation
    """
    
    name = "MACDCrossover"
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        histogram_threshold: float = 0.0
    ):
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.histogram_threshold = histogram_threshold
        logger.info("MACD Crossover strategy initialized")
    
    def calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average"""
        ema = np.zeros_like(data)
        multiplier = 2 / (period + 1)
        
        # Initialize with SMA
        ema[period-1] = np.mean(data[:period])
        
        # Calculate EMA
        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        
        return ema
    
    def calculate_macd(self, close: np.ndarray) -> tuple:
        """Calculate MACD, Signal, and Histogram"""
        fast_ema = self.calculate_ema(close, self.fast_period)
        slow_ema = self.calculate_ema(close, self.slow_period)
        
        macd_line = fast_ema - slow_ema
        signal_line = self.calculate_ema(macd_line, self.signal_period)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate MACD crossover signal"""
        close = np.array(features.get('close', []))
        
        min_periods = self.slow_period + self.signal_period + 5
        if len(close) < min_periods:
            return self._no_signal(symbol)
        
        # Calculate MACD
        macd_line, signal_line, histogram = self.calculate_macd(close)
        
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        current_histogram = histogram[-1]
        prev_macd = macd_line[-2]
        prev_signal = signal_line[-2]
        prev_histogram = histogram[-2]
        
        signal_value = 0.0
        confidence = 0.0
        crossover_type = "none"
        
        # Bullish crossover: MACD crosses above Signal
        if prev_macd <= prev_signal and current_macd > current_signal:
            crossover_type = "bullish"
            signal_value = 0.7
            confidence = 0.6
            
            # Stronger if histogram is positive and growing
            if current_histogram > prev_histogram:
                signal_value = 0.9
                confidence = 0.75
            
            # Extra strong if crossing above zero line
            if current_macd > 0:
                signal_value = min(signal_value + 0.1, 1.0)
                confidence = min(confidence + 0.1, 1.0)
        
        # Bearish crossover: MACD crosses below Signal
        elif prev_macd >= prev_signal and current_macd < current_signal:
            crossover_type = "bearish"
            signal_value = -0.7
            confidence = 0.6
            
            # Stronger if histogram is negative and falling
            if current_histogram < prev_histogram:
                signal_value = -0.9
                confidence = 0.75
            
            # Extra strong if crossing below zero line
            if current_macd < 0:
                signal_value = max(signal_value - 0.1, -1.0)
                confidence = min(confidence + 0.1, 1.0)
        
        # Trend continuation signals
        elif current_macd > current_signal and current_histogram > prev_histogram:
            signal_value = 0.3
            confidence = 0.4
            crossover_type = "bullish_continuation"
        
        elif current_macd < current_signal and current_histogram < prev_histogram:
            signal_value = -0.3
            confidence = 0.4
            crossover_type = "bearish_continuation"
        
        # Determine signal
        if signal_value > 0.2:
            signal = Signal.BUY
        elif signal_value < -0.2:
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
                "macd": current_macd,
                "signal_line": current_signal,
                "histogram": current_histogram,
                "crossover_type": crossover_type,
                "macd_above_zero": current_macd > 0,
                "histogram_growing": current_histogram > prev_histogram
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

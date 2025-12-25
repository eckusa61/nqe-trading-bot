"""
RSI Divergence Strategy
Detects bullish/bearish divergences between price and RSI
"""
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


class RSIDivergenceStrategy(BaseStrategy):
    """
    RSI Divergence Trading Strategy
    
    Logic:
    1. Calculate RSI
    2. Find price highs/lows and RSI highs/lows
    3. Detect divergences:
       - Bullish: Price makes lower low, RSI makes higher low
       - Bearish: Price makes higher high, RSI makes lower high
    4. Trade the divergence
    """
    
    name = "RSIDivergence"
    
    def __init__(
        self,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        divergence_lookback: int = 20,
        min_divergence: float = 5.0
    ):
        super().__init__()
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.divergence_lookback = divergence_lookback
        self.min_divergence = min_divergence
        logger.info("RSI Divergence strategy initialized")
    
    def calculate_rsi(self, close: np.ndarray) -> np.ndarray:
        """Calculate RSI"""
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.zeros_like(close)
        avg_loss = np.zeros_like(close)
        
        # Initial SMA
        avg_gain[self.rsi_period] = np.mean(gains[:self.rsi_period])
        avg_loss[self.rsi_period] = np.mean(losses[:self.rsi_period])
        
        # EMA style calculation
        for i in range(self.rsi_period + 1, len(close)):
            avg_gain[i] = (avg_gain[i-1] * (self.rsi_period - 1) + gains[i-1]) / self.rsi_period
            avg_loss[i] = (avg_loss[i-1] * (self.rsi_period - 1) + losses[i-1]) / self.rsi_period
        
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def find_peaks(self, data: np.ndarray, is_high: bool = True) -> List[int]:
        """Find local peaks/troughs"""
        peaks = []
        for i in range(2, len(data) - 2):
            if is_high:
                if data[i] > data[i-1] and data[i] > data[i-2] and \
                   data[i] > data[i+1] and data[i] > data[i+2]:
                    peaks.append(i)
            else:
                if data[i] < data[i-1] and data[i] < data[i-2] and \
                   data[i] < data[i+1] and data[i] < data[i+2]:
                    peaks.append(i)
        return peaks
    
    def detect_divergence(self, close: np.ndarray, rsi: np.ndarray) -> Tuple[str, float]:
        """Detect bullish or bearish divergence"""
        lookback_close = close[-self.divergence_lookback:]
        lookback_rsi = rsi[-self.divergence_lookback:]
        
        price_highs = self.find_peaks(lookback_close, is_high=True)
        price_lows = self.find_peaks(lookback_close, is_high=False)
        rsi_highs = self.find_peaks(lookback_rsi, is_high=True)
        rsi_lows = self.find_peaks(lookback_rsi, is_high=False)
        
        # Bullish divergence: lower price lows, higher RSI lows
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            if lookback_close[price_lows[-1]] < lookback_close[price_lows[-2]]:
                if lookback_rsi[rsi_lows[-1]] > lookback_rsi[rsi_lows[-2]]:
                    strength = lookback_rsi[rsi_lows[-1]] - lookback_rsi[rsi_lows[-2]]
                    if strength >= self.min_divergence:
                        return "bullish", strength
        
        # Bearish divergence: higher price highs, lower RSI highs
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            if lookback_close[price_highs[-1]] > lookback_close[price_highs[-2]]:
                if lookback_rsi[rsi_highs[-1]] < lookback_rsi[rsi_highs[-2]]:
                    strength = lookback_rsi[rsi_highs[-2]] - lookback_rsi[rsi_highs[-1]]
                    if strength >= self.min_divergence:
                        return "bearish", strength
        
        return "none", 0.0
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate RSI divergence signal"""
        close = np.array(features.get('close', []))
        
        if len(close) < self.rsi_period + self.divergence_lookback + 10:
            return self._no_signal(symbol)
        
        # Calculate RSI
        rsi = self.calculate_rsi(close)
        current_rsi = rsi[-1]
        
        # Detect divergence
        divergence_type, divergence_strength = self.detect_divergence(close, rsi)
        
        signal_value = 0.0
        confidence = 0.0
        
        if divergence_type == "bullish":
            signal_value = min(divergence_strength / 20.0, 1.0)
            confidence = 0.6
            
            # Stronger signal if RSI is oversold
            if current_rsi < self.oversold:
                signal_value = min(signal_value * 1.3, 1.0)
                confidence = 0.8
        
        elif divergence_type == "bearish":
            signal_value = -min(divergence_strength / 20.0, 1.0)
            confidence = 0.6
            
            # Stronger signal if RSI is overbought
            if current_rsi > self.overbought:
                signal_value = max(signal_value * 1.3, -1.0)
                confidence = 0.8
        
        # Simple RSI signals as backup
        elif current_rsi < self.oversold:
            signal_value = 0.3
            confidence = 0.4
        elif current_rsi > self.overbought:
            signal_value = -0.3
            confidence = 0.4
        
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
                "rsi": current_rsi,
                "divergence_type": divergence_type,
                "divergence_strength": divergence_strength,
                "oversold": current_rsi < self.oversold,
                "overbought": current_rsi > self.overbought
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

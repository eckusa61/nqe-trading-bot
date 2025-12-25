"""
VWAP Reversion Strategy
Trades mean reversion to VWAP (Volume Weighted Average Price)
"""
import logging
import numpy as np
from typing import Dict
from datetime import datetime, timezone

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


class VWAPReversionStrategy(BaseStrategy):
    """
    VWAP Reversion Trading Strategy
    
    Logic:
    1. Calculate VWAP
    2. Calculate standard deviation bands around VWAP
    3. Buy when price is significantly below VWAP
    4. Sell when price is significantly above VWAP
    """
    
    name = "VWAPReversion"
    
    def __init__(
        self,
        std_multiplier: float = 2.0,
        min_deviation: float = 0.005,
        reversion_target: float = 0.5
    ):
        super().__init__()
        self.std_multiplier = std_multiplier
        self.min_deviation = min_deviation
        self.reversion_target = reversion_target
        logger.info("VWAP Reversion strategy initialized")
    
    def calculate_vwap(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """Calculate VWAP"""
        typical_price = (high + low + close) / 3
        cumulative_tp_volume = np.cumsum(typical_price * volume)
        cumulative_volume = np.cumsum(volume)
        vwap = np.where(cumulative_volume > 0, cumulative_tp_volume / cumulative_volume, typical_price)
        return vwap
    
    def calculate_vwap_std(self, close: np.ndarray, vwap: np.ndarray, period: int = 20) -> np.ndarray:
        """Calculate rolling standard deviation from VWAP"""
        deviation = close - vwap
        std = np.zeros_like(close)
        for i in range(period - 1, len(close)):
            std[i] = np.std(deviation[i - period + 1:i + 1])
        return std
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate VWAP reversion signal"""
        close = np.array(features.get('close', []))
        high = np.array(features.get('high', []))
        low = np.array(features.get('low', []))
        volume = np.array(features.get('volume', []))
        
        if len(close) < 30:
            return self._no_signal(symbol)
        
        # Calculate VWAP
        vwap = self.calculate_vwap(high, low, close, volume)
        vwap_std = self.calculate_vwap_std(close, vwap)
        
        current_price = close[-1]
        current_vwap = vwap[-1]
        current_std = vwap_std[-1]
        
        # Calculate deviation
        deviation = (current_price - current_vwap) / current_vwap
        z_score = (current_price - current_vwap) / current_std if current_std > 0 else 0
        
        signal_value = 0.0
        confidence = 0.0
        state = "neutral"
        
        # Oversold - below VWAP
        if z_score < -self.std_multiplier and deviation < -self.min_deviation:
            signal_value = min(abs(z_score) / 3.0, 1.0)
            confidence = 0.6 + min(abs(z_score) / 10.0, 0.3)
            state = "oversold"
        
        # Overbought - above VWAP
        elif z_score > self.std_multiplier and deviation > self.min_deviation:
            signal_value = -min(abs(z_score) / 3.0, 1.0)
            confidence = 0.6 + min(abs(z_score) / 10.0, 0.3)
            state = "overbought"
        
        # Near VWAP - potential exit
        elif abs(z_score) < 0.5:
            signal_value = 0.0
            confidence = 0.5
            state = "at_vwap"
        
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
                "vwap": current_vwap,
                "price": current_price,
                "deviation_pct": deviation * 100,
                "z_score": z_score,
                "state": state
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
